# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap
import                                math

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, df_embed_author, add_tutorial_embed
from discord_app.map_rendering import add_map_to_embed
import discord_app.nav_menus
import discord_app.vendor_views.vendor_views
import discord_app.vehicle_views
import discord_app.cargo_views

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


class TopUpButton(discord.ui.Button):
    def __init__(self, df_state: DFState, vendors, row: int=1):
        self.df_state = df_state
        self.vendors = vendors

        self.resource_vendors = {}
        self.top_up_price = 0

        resource_types = ['fuel', 'water', 'food']
        available_resources = []

        for resource_type in resource_types:
            # Calculate convoy's need for each resource
            convoy_need = self.df_state.convoy_obj[f'max_{resource_type}'] - self.df_state.convoy_obj[resource_type]
            if convoy_need > 0:
                # Find the vendor with the lowest price for this resource
                vendor = min(
                    (v for v in vendors if v.get(f'{resource_type}_price') is not None),
                    key=lambda v: v[f'{resource_type}_price'],
                    default=None
                )
                if vendor:
                    # Calculate top-up cost and track vendor info for each resource
                    self.top_up_price += convoy_need * vendor[f'{resource_type}_price']
                    self.resource_vendors[resource_type] = {
                        'vendor_id': vendor['vendor_id'],
                        'price': vendor[f'{resource_type}_price'],
                        'convoy_need': convoy_need
                    }
                    available_resources.append(resource_type)

        # Display available resources in the button label
        available_resources_str = ', '.join(available_resources)
        
        if self.top_up_price == 0:  # If nothing to top up
            label = 'Convoy is already topped up'
            disabled = True
        else:
            label = f'Top up {available_resources_str} | ${self.top_up_price:,.0f}'
            disabled = self.top_up_price > self.df_state.convoy_obj['money']  # Disable button if convoy doesn't have enough money

        # Initialize the button with calculated values
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
            custom_id='top_up_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        try:
            # Attempt to top up each resource from its respective vendor
            for resource_type, vendor_info in self.resource_vendors.items():
                self.df_state.convoy_obj = await api_calls.buy_resource(
                    vendor_id=vendor_info['vendor_id'],
                    convoy_id=self.df_state.convoy_obj['convoy_id'],
                    resource_type=resource_type,
                    quantity=vendor_info['convoy_need']
                )
            
            # Success response
            embed = discord.Embed(description=f'Topped up all resources for ${self.top_up_price:,.0f}')
            embed = df_embed_author(embed, self.df_state)

            embeds = [embed]
            embeds = add_tutorial_embed(embeds, self.df_state)

            view = discord.ui.View()
            discord_app.nav_menus.add_nav_buttons(view, self.df_state)

            user_metadata = self.df_state.convoy_obj.get('user_metadata')  # TUTORIAL BUTTON DISABLING
            tutorial_stage = user_metadata.get('tutorial') if user_metadata else None
            if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
                for item in view.children:
                    item.disabled = item.custom_id != 'nav_sett_button'

            await interaction.response.edit_message(embeds=embeds, view=view)

        except RuntimeError as e:
            # Handle error response
            await interaction.response.send_message(content=str(e), ephemeral=True)


async def buy_menu(df_state: DFState):
    resources_list = []
    if df_state.vendor_obj['fuel']:
        resources_list.append(f'- Fuel: {df_state.vendor_obj['fuel']} Liters\n  - *${df_state.vendor_obj['fuel_price']:,.0f} per Liter*')
    if df_state.vendor_obj['water']:
        resources_list.append(f'- Water: {df_state.vendor_obj['water']} Liters\n  - *${df_state.vendor_obj['water_price']:,.0f} per Liter*')
    if df_state.vendor_obj['food']:
        resources_list.append(f'- Food: {df_state.vendor_obj['food']} Servings\n  - *${df_state.vendor_obj['food_price']:,.0f} per Serving*')
    displayable_resources = '\n'.join(resources_list) if resources_list else '- None'

    vehicle_list = []
    for vehicle in df_state.vendor_obj['vehicle_inventory']:
        vehicle_str = f'- {vehicle['name']} | *${vehicle['value']:,}*'
        vehicle_list.append(vehicle_str)
    displayable_vehicles = '\n'.join(vehicle_list) if vehicle_list else '- None'

    cargo_list = []
    for cargo in df_state.vendor_obj['cargo_inventory']:
        cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *${cargo['base_price']:,} each*'

        if cargo['recipient']:
            cargo['recipient_vendor'] = await api_calls.get_vendor(vendor_id=cargo['recipient'])
            cargo_str += f'\n  - Deliver to *{cargo['recipient_vendor']['name']}* | ***${cargo['delivery_reward']:,.0f}*** *each*'
            margin = round(cargo['delivery_reward'] / cargo['base_price'])
            cargo_str += f'\n  - Profit margin: {'💵 ' * margin}'
            tile_distance = math.sqrt((cargo['recipient_vendor']['x'] - df_state.vendor_obj['x']) ** 2 + (cargo['recipient_vendor']['y'] - df_state.vendor_obj['y']) ** 2)
            distance_km = 50 * tile_distance
            distance_miles = 30 * tile_distance
            cargo_str += f'\n  - Distance: {distance_km:,.0f} km ({distance_miles:,.0f} miles)'

        cargo_list.append(cargo_str)
    displayable_cargo = '\n'.join(cargo_list) if cargo_list else '- None'

    menu_embed = discord.Embed()
    menu_embed.description='\n'.join([
        f'## {df_state.vendor_obj['name']}',
        '### Available for Purchase:',
        '**Resources:**',
        f'{displayable_resources}',
        '',
        '**Vehicles:**',
        f'{displayable_vehicles}',
        '',
        '**Cargo:**',
        f'{displayable_cargo}'
    ])

    menu_embed = df_embed_author(menu_embed, df_state)

    embeds = [menu_embed]
    embeds = add_tutorial_embed(embeds, df_state)

    buy_view = BuyView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=buy_view)


class BuyView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyResourceButton(self.df_state, 'fuel'))
        self.add_item(BuyResourceButton(self.df_state, 'water'))
        self.add_item(BuyResourceButton(self.df_state, 'food'))

        self.add_item(BuyVehicleSelect(self.df_state))

        self.add_item(BuyCargoSelect(self.df_state))

        user_metadata = self.df_state.convoy_obj.get('user_metadata')  # TUTORIAL BUTTON DISABLING
        tutorial_stage = user_metadata.get('tutorial') if user_metadata else None
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                match tutorial_stage:
                    case 1:
                        item.disabled = item.custom_id != 'select_vehicle'
                    case 2 | 4:
                        item.disabled = item.custom_id != 'select_cargo'

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()


class BuyResourceButton(discord.ui.Button):
    def __init__(self, df_state: DFState, resource_type: str, row: int=1):
        self.df_state = df_state
        self.resource_type = resource_type

        disabled = True
        if self.df_state.vendor_obj[resource_type]:
            disabled = False

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=f'Buy {resource_type}',
            disabled=disabled,
            custom_id=f'buy_{resource_type}_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        
        embed = ResourceBuyQuantityEmbed(self.df_state, self.resource_type)
        view = ResourceBuyQuantityView(self.df_state, self.resource_type)

        await interaction.response.edit_message(embed=embed, view=view)


class ResourceBuyQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, resource_type: str, cart_quantity: int=1):
        self.df_state = df_state
        self.resource_type = resource_type
        self.cart_quantity = cart_quantity
        super().__init__()
        
        self = df_embed_author(self, self.df_state)

        cart_price = self.cart_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']
        
        self.description = '\n'.join([
            f'## {df_state.vendor_obj['name']}',
            f'### Buying {self.resource_type} for ${self.df_state.vendor_obj[f'{self.resource_type}_price']:,.0f} per Liter/Serving',
            f'{self.df_state.convoy_obj['name']}\'s capacity for {self.resource_type}: {self.df_state.convoy_obj[f'max_{self.resource_type}']}',
            f'### Cart: {self.cart_quantity:,.2f} Liters/Servings | ${cart_price:,.0f}'
        ])


class ResourceBuyQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, resource_type: str, cart_quantity: int=1):
        self.df_state = df_state
        self.resource_type = resource_type
        self.cart_quantity = cart_quantity
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, -10, self.resource_type))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, -1, self.resource_type))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 1, self.resource_type))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 10, self.resource_type))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 'max', self.resource_type))

        self.add_item(ResourceConfirmBuyButton(self.df_state, self.cart_quantity, self.resource_type, row=2))

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()


class QuantityBuyButton(discord.ui.Button):  # XXX: Explode this button into like 4 different buttons, instead of just nesting a million if/elses
    def __init__(
            self,
            df_state: DFState,
            cart_quantity: int,
            button_quantity: int | str,
            resource_type: str = None,
            cargo_for_sale: dict = None,
            row: int = 1
    ):
        self.df_state = df_state
        self.cart_quantity = cart_quantity
        self.resource_type = resource_type
        self.cargo_for_sale = cargo_for_sale

        if self.cargo_for_sale:  # Determine max quantities
            max_by_volume = self.df_state.convoy_obj['total_free_space'] / self.df_state.cargo_obj['volume']
            max_by_weight = self.df_state.convoy_obj['total_remaining_capacity'] / self.df_state.cargo_obj['weight']
            max_convoy_capacity = int(min(max_by_volume, max_by_weight))
            inventory_quantity = self.df_state.cargo_obj['quantity']
        else:
            max_convoy_capacity = self.df_state.convoy_obj[f'max_{self.resource_type}'] - self.df_state.convoy_obj[self.resource_type]
            inventory_quantity = self.df_state.vendor_obj[self.resource_type]

        if button_quantity == 'max':  # Handle "max" button logic
            self.button_quantity = min(max_convoy_capacity, inventory_quantity) - self.cart_quantity
            if self.button_quantity <= 0:
                self.button_quantity = 0  # Ensure the quantity is 0
            label = f'max ({self.button_quantity:+,})' if self.cargo_for_sale else f'max ({self.button_quantity:+,.2f})'
        else:
            self.button_quantity = int(button_quantity)
            label = f'{self.button_quantity:+,}'

        resultant_quantity = self.cart_quantity + self.button_quantity

        disabled = self.should_disable_button(  # Determine if button should be disabled
            resultant_quantity, inventory_quantity, max_convoy_capacity
        )

        if self.button_quantity == 0:  # Disable the button if the "max" button would add 0 quantity
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
            custom_id=f'{button_quantity}_button',
            row=row
        )

    def should_disable_button(self, resultant_quantity, inventory_quantity, max_convoy_capacity):
        # Disable if the resulting quantity is out of valid bounds
        if resultant_quantity <= 0:
            return True
        
        if resultant_quantity > inventory_quantity:
            return True
        
        if self.cargo_for_sale:
            max_by_volume = self.df_state.convoy_obj['total_free_space'] / self.df_state.cargo_obj['volume']
            max_by_weight = self.df_state.convoy_obj['total_remaining_capacity'] / self.df_state.cargo_obj['weight']
            if resultant_quantity > max_by_volume or resultant_quantity > max_by_weight:
                return True

            cart_price = resultant_quantity * self.df_state.cargo_obj['base_price']
            
        else:
            if resultant_quantity > max_convoy_capacity:
                return True

            cart_price = resultant_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']

        if cart_price > self.df_state.convoy_obj['money']:
                return True

        return False

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.cart_quantity += self.button_quantity  # Update cart quantity

        if self.resource_type:  # Update embed and view depending on resource type
            embed = ResourceBuyQuantityEmbed(self.df_state, self.resource_type, self.cart_quantity)
            view = ResourceBuyQuantityView(self.df_state, self.resource_type, self.cart_quantity)
        else:
            embed = CargoBuyQuantityEmbed(self.df_state, self.cart_quantity)
            view = CargoBuyQuantityView(self.df_state, self.cart_quantity)

        embeds = [embed]
        embeds = add_tutorial_embed(embeds, self.df_state)

        await interaction.response.edit_message(embeds=embeds, view=view)


class ResourceConfirmBuyButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            cart_quantity: int,
            resource_type: str=None,
            row: int=1
    ):
        self.df_state = df_state
        self.cart_quantity = cart_quantity
        self.resource_type = resource_type

        cart_price = self.cart_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Buy {self.cart_quantity:,.2f}L of {self.resource_type} | ${cart_price:,.0f}',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.buy_resource(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                resource_type=self.resource_type,
                quantity=self.cart_quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        
        cart_price = self.cart_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']
        
        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'## {self.df_state.vendor_obj['name']}',
            f'Purchased {self.cart_quantity:,.2f} Liters/Servings of {self.resource_type} for ${cart_price:,.0f}'
        ])

        view = PostBuyView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


class BuyVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state
        
        placeholder = 'Vehicle Inventory'
        disabled = False
        options=[
            discord.SelectOption(label=f'{vehicle['name']} | ${vehicle['value']:,.0f}', value=vehicle['vehicle_id'])
            for vehicle in self.df_state.vendor_obj['vehicle_inventory']
        ]
        if not options:
            placeholder = 'Vendor has no vehicle inventory'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=disabled,
            custom_id='select_vehicle',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.vehicle_obj = next((
            v for v in self.df_state.vendor_obj['vehicle_inventory']
            if v['vehicle_id'] == self.values[0]
        ), None)

        part_list = []
        for category, part in self.df_state.vehicle_obj['parts'].items():
            if not part:  # If the part slot is empty
                part_list.append(f'- {category.replace('_', ' ').capitalize()}\n  - None')
                continue

            part_list.append(discord_app.cargo_views.format_part(part))
        displayable_vehicle_parts = '\n'.join(part_list)

        vehicle_buy_confirm_embed = discord.Embed()
        vehicle_buy_confirm_embed = df_embed_author(vehicle_buy_confirm_embed, self.df_state)
        vehicle_buy_confirm_embed.description = '\n'.join([
            f'## {self.df_state.vendor_obj['name']}',
            f'### {self.df_state.vehicle_obj['name']} | ${self.df_state.vehicle_obj['value']:,.0f}',
            f'*{self.df_state.vehicle_obj['base_desc']}*',
            '### Parts',
            displayable_vehicle_parts,
            '### Stats'
        ])
        vehicle_buy_confirm_embed = discord_app.vehicle_views.df_embed_vehicle_stats(vehicle_buy_confirm_embed, self.df_state.vehicle_obj)

        embeds = [vehicle_buy_confirm_embed]
        embeds = add_tutorial_embed(embeds, self.df_state)

        vehicle_buy_confirm_view = VehicleBuyConfirmView(self.df_state)

        await interaction.response.edit_message(embeds=embeds, view=vehicle_buy_confirm_view)


class VehicleBuyConfirmView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyVehicleButton(self.df_state))

        user_metadata = self.df_state.convoy_obj.get('user_metadata')  # TUTORIAL BUTTON DISABLING
        tutorial_stage = user_metadata.get('tutorial') if user_metadata else None
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                    item.disabled = item.custom_id != 'buy_vehicle_button'

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()


class BuyVehicleButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.vehicle_obj['value'] < self.df_state.convoy_obj['money']:
            disabled = False
        else:
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Buy {self.df_state.vehicle_obj['name']} | ${self.df_state.vehicle_obj['value']:,.0f}',
            disabled=disabled,
            custom_id='buy_vehicle_button',
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.buy_vehicle(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                vehicle_id=self.df_state.vehicle_obj['vehicle_id']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'Your convoy\'s new vehicle: {self.df_state.vehicle_obj['name']}',
            f'*{self.df_state.vehicle_obj['base_desc']}*'
        ])

        embeds = [embed]
        embeds = add_tutorial_embed(embeds, self.df_state)

        view = PostBuyView(self.df_state)

        await interaction.response.edit_message(embeds=embeds, view=view)


class BuyCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=3):
        self.df_state = df_state

        placeholder = 'Cargo Inventory'
        disabled = False
        options=[
            discord.SelectOption(label=f'{cargo['name']} | ${cargo['base_price']:,.0f}', value=cargo['cargo_id'])
            for cargo in self.df_state.vendor_obj['cargo_inventory']
        ]
        if not options:
            placeholder = 'Vendor has no cargo inventory'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=disabled,
            custom_id='select_cargo',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.cargo_obj = next((
            c for c in self.df_state.vendor_obj['cargo_inventory']
            if c['cargo_id'] == self.values[0]
        ), None)

        embed = CargoBuyQuantityEmbed(self.df_state)

        embeds = [embed]
        embeds = add_tutorial_embed(embeds, self.df_state)

        view = CargoBuyQuantityView(self.df_state)

        await interaction.response.edit_message(embeds=embeds, view=view)


class CargoBuyQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, cart_quantity: int=1):
        self.df_state = df_state
        self.cart_quantity = cart_quantity
        super().__init__()
        
        self = df_embed_author(self, self.df_state)
        
        cart_price = self.cart_quantity * self.df_state.cargo_obj['base_price']
        cart_volume = self.cart_quantity * self.df_state.cargo_obj['volume']
        cart_weight = self.cart_quantity * self.df_state.cargo_obj['weight']

        desc = [
            f'## {self.df_state.vendor_obj['name']}',
            f'### Buying {self.df_state.cargo_obj['name']} for ${self.df_state.cargo_obj['base_price']:,.0f} per item',
            f'*{self.df_state.cargo_obj['base_desc']}*',
            f'- Cart volume: {cart_volume:,}L / {self.df_state.convoy_obj['total_free_space']:,}L free space in convoy',
            f'- Cart weight: {cart_weight:,}kg / {self.df_state.convoy_obj['total_remaining_capacity']}kg capacity in convoy',
        ]
        if self.df_state.cargo_obj['recipient']:
            delivery_reward = self.cart_quantity * self.df_state.cargo_obj['delivery_reward']
            desc.extend([
                '',
                f'**Deliver to {self.df_state.cargo_obj['recipient_vendor']['name']} for a reward of ${delivery_reward:,.0f}**'
            ])
        desc.append(
            f'### Cart: {self.cart_quantity:,} {self.df_state.cargo_obj['name']}(s) | ${cart_price:,.0f}'
        )

        self.description = '\n'.join(desc)
        self.add_field(name='Inventory', value=self.df_state.cargo_obj['quantity'])
        self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['volume']} liter(s)')
        self.add_field(name='Weight (per unit)', value=f'{self.df_state.cargo_obj['weight']} kilogram(s)')


class CargoBuyQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, cart_quantity: int=1):
        self.df_state = df_state
        self.cart_quantity = cart_quantity
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, -10, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, -1, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 1, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 10, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 'max', cargo_for_sale=self.df_state.cargo_obj))

        self.add_item(CargoConfirmBuyButton(self.df_state, self.cart_quantity, row=2))
        if self.df_state.cargo_obj['recipient']:
            self.add_item(discord_app.cargo_views.MapButton(self.df_state.convoy_obj, self.df_state.cargo_obj['recipient_vendor'], row=2))

        user_metadata = self.df_state.convoy_obj.get('user_metadata')  # TUTORIAL BUTTON DISABLING
        tutorial_stage = user_metadata.get('tutorial') if user_metadata else None
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                match tutorial_stage:  # Use match-case to handle different tutorial stages
                    case 2:
                        item.disabled = not (item.custom_id == '1_button' or item.custom_id == 'buy_cargo_button')
                    case 4:
                        item.disabled = not (item.custom_id == 'max_button' or item.custom_id == 'buy_cargo_button' or item.custom_id == 'map_button')

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()


class CargoConfirmBuyButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            cart_quantity: int,
            row: int=1
    ):
        self.df_state = df_state
        self.cart_quantity = cart_quantity

        cart_price = self.cart_quantity * self.df_state.cargo_obj['base_price']

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Buy {self.cart_quantity} {self.df_state.cargo_obj['name']}(s) | ${cart_price:,.0f}',
            custom_id='buy_cargo_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        
        try:
            self.df_state.convoy_obj = await api_calls.buy_cargo(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                cargo_id=self.df_state.cargo_obj['cargo_id'],
                quantity=self.cart_quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        
        cart_price = self.cart_quantity * self.df_state.cargo_obj['base_price']
        
        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        desc = [
            f'## {self.df_state.vendor_obj['name']}',
            f'Purchased {self.cart_quantity} {self.df_state.cargo_obj['name']}(s) for ${cart_price:,.0f}'
        ]
        if self.df_state.cargo_obj['recipient']:
            delivery_reward = self.cart_quantity * self.df_state.cargo_obj['delivery_reward']
            desc.append(f'Deliver to {self.df_state.cargo_obj['recipient_vendor']['name']} for a reward of $**{delivery_reward:,.0f}**')
        embed.description = '\n'.join(desc)

        embeds = [embed]
        embeds = add_tutorial_embed(embeds, self.df_state)

        view = PostBuyView(self.df_state)

        await interaction.response.edit_message(embeds=embeds, view=view)


class PostBuyView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        user_metadata = self.df_state.convoy_obj.get('user_metadata')  # TUTORIAL BUTTON DISABLING
        tutorial_stage = user_metadata.get('tutorial') if user_metadata else None
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                match tutorial_stage:  # Use match-case to handle different tutorial stages
                    case 1 | 2 | 3 | 4:  # Enable 'nav_sett_button' only for stages 1-4, disable all others
                        item.disabled = item.custom_id != 'nav_sett_button'
                    case 5:  # Enable 'send_convoy_button' for stage 5, disable all others
                        item.disabled = item.custom_id != 'nav_convoy_button'

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()
