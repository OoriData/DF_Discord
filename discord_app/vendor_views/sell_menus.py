# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, df_embed_author
from discord_app.map_rendering import add_map_to_embed
import discord_app.nav_menus
import discord_app.vehicle_views
import discord_app.cargo_views

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


async def sell_menu(df_state: DFState):
    resources_list = []
    if df_state.vendor_obj['fuel']:
        resources_list.append(f'- Fuel: {df_state.convoy_obj['fuel']} Liters\n  - *${df_state.vendor_obj['fuel_price']} per Liter*')
    if df_state.vendor_obj['water']:
        resources_list.append(f'- Water: {df_state.convoy_obj['water']} Liters\n  - *${df_state.vendor_obj['water_price']} per Liter*')
    if df_state.vendor_obj['food']:
        resources_list.append(f'- Food: {df_state.convoy_obj['food']} Servings\n  - *${df_state.vendor_obj['food_price']} per Serving*')
    displayable_resources = '\n'.join(resources_list) if resources_list else '- None'

    vehicle_list = []
    for vehicle in df_state.convoy_obj['vehicles']:
        vehicle_str = f'- {vehicle['name']} | *${vehicle['value']:,}*'
        if not all(c['intrinsic'] for c in vehicle['cargo']):
            vehicle_str += '\n  - *contains cargo, cannot be sold*'
        vehicle_list.append(vehicle_str)
    displayable_vehicles = '\n'.join(vehicle_list) if vehicle_list else '- None'

    cargo_list = []
    for vehicle in df_state.convoy_obj['vehicles']:
        for cargo in vehicle['cargo']:
            if cargo['intrinsic']:
                continue

            cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *{vehicle['name']}* | *${cargo['base_price']:,} each*'

            if cargo['recipient']:
                cargo['recipient_vendor'] = await api_calls.get_vendor(vendor_id=cargo['recipient'])
                cargo_str += f'\n  - Deliver to *{cargo['recipient_vendor']['name']}* | ${cargo['delivery_reward']:,}'

            cargo_list.append(cargo_str)
    displayable_cargo = '\n'.join(cargo_list) if cargo_list else '- None'

    embed = discord.Embed()
    embed.description='\n'.join([
        f'## {df_state.vendor_obj['name']}',
        '### Available to sell from convoy:',
        '**Resources:**',
        f'{displayable_resources}',
        '',
        '**Vehicles:**',
        f'{displayable_vehicles}',
        '',
        '**Cargo:**',
        f'{displayable_cargo}'
    ])

    embed = df_embed_author(embed, df_state)

    view = SellView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)


class SellView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(SellResourceButton(self.df_state, 'fuel'))
        self.add_item(SellResourceButton(self.df_state, 'water'))
        self.add_item(SellResourceButton(self.df_state, 'food'))

        self.add_item(SellVehicleSelect(self.df_state))

        self.add_item(SellCargoSelect(self.df_state))

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


class SellResourceButton(discord.ui.Button):
    def __init__(self, df_state: DFState, resource_type: str, row: int=1):
        self.df_state = df_state
        self.resource_type = resource_type

        disabled = True
        if self.df_state.vendor_obj[resource_type]:
            disabled = False

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=f'Sell {resource_type}',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        
        embed = ResourceSellQuantityEmbed(self.df_state, self.resource_type)
        view = ResourceSellQuantityView(self.df_state, self.resource_type)

        await interaction.response.edit_message(embed=embed, view=view)


class ResourceSellQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, resource_type: str, sale_quantity: int=1):
        self.df_state = df_state
        self.resource_type = resource_type
        self.sale_quantity = sale_quantity
        super().__init__()
        
        self = df_embed_author(self, self.df_state)

        sale_price = self.sale_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']
        
        self.description = '\n'.join([
            f'## {df_state.vendor_obj['name']}',
            f'### Selling {self.resource_type} for ${self.df_state.vendor_obj[f'{self.resource_type}_price']:,} per Liter/Serving',
            f'{self.df_state.convoy_obj['name']}\'s {self.resource_type}: {self.df_state.convoy_obj[self.resource_type]} Liters/Servings',
            f'### Sale: {self.sale_quantity:,.2f} Liters/Servings | ${sale_price:,.0f}'
        ])


class ResourceSellQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, resource_type: str, sale_quantity: int=1):
        self.df_state = df_state
        self.resource_type = resource_type
        self.sale_quantity = sale_quantity
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, -10, self.resource_type))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, -1, self.resource_type))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 1, self.resource_type))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 10, self.resource_type))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 'max', self.resource_type))

        self.add_item(ResourceConfirmSellButton(self.df_state, self.sale_quantity, self.resource_type, row=2))

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


class ResourceConfirmSellButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            sale_quantity: int,
            resource_type: str=None,
            row: int=1
    ):
        self.df_state = df_state
        self.sale_quantity = sale_quantity
        self.resource_type = resource_type

        sale_price = self.sale_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Buy {self.sale_quantity:,.2f}L of {self.resource_type} | ${sale_price:,.0f}',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.sell_resource(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                resource_type=self.resource_type,
                quantity=self.sale_quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        
        sale_price = self.sale_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']
        
        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'## {self.df_state.vendor_obj['name']}',
            f'Sold {self.sale_quantity:,.2f} Liters/Servings of {self.resource_type} for ${sale_price:,.0f}'
        ])

        view = PostSellView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


class QuantitySellButton(discord.ui.Button):  # XXX: Explode this button into like 4 different buttons, instead of just nesting a million if/elses
    def __init__(
            self,
            df_state: DFState,
            sale_quantity: int,
            button_quantity: int | str,
            resource_type: str = None,
            cargo_for_sale: dict = None,
            row: int = 1
    ):
        self.df_state = df_state
        self.sale_quantity = sale_quantity
        self.resource_type = resource_type
        self.cargo_for_sale = cargo_for_sale

        if self.cargo_for_sale:  # Determine max quantities
            inventory_quantity = self.df_state.cargo_obj['quantity']
        else:
            inventory_quantity = self.df_state.convoy_obj[self.resource_type]

        if button_quantity == 'max':  # Handle "max" button logic
            self.button_quantity = inventory_quantity - self.sale_quantity
            if self.button_quantity <= 0:
                self.button_quantity = 0  # Ensure the quantity is 0
            label = f'max ({self.button_quantity:+,})' if self.cargo_for_sale else f'max ({self.button_quantity:+,.2f})'
        else:
            self.button_quantity = int(button_quantity)
            label = f'{self.button_quantity:+,}'

        resultant_quantity = self.sale_quantity + self.button_quantity

        disabled = self.should_disable_button(  # Determine if button should be disabled
            resultant_quantity, inventory_quantity
        )

        if self.button_quantity == 0:  # Disable the button if the "max" button would add 0 quantity
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
            row=row
        )

    def should_disable_button(self, resultant_quantity, inventory_quantity):
        # Disable if the resulting quantity is out of valid bounds
        if resultant_quantity <= 0:
            return True
        
        if resultant_quantity > inventory_quantity:
            return True

        return False

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.sale_quantity += self.button_quantity  # Update sale quantity

        if self.resource_type:  # Update embed and view depending on resource type
            embed = ResourceSellQuantityEmbed(self.df_state, self.resource_type, self.sale_quantity)
            view = ResourceSellQuantityView(self.df_state, self.resource_type, self.sale_quantity)
        else:
            embed = CargoSellQuantityEmbed(self.df_state, self.sale_quantity)
            view = CargoSellQuantityView(self.df_state, self.sale_quantity)

        await interaction.response.edit_message(embed=embed, view=view)


class SellVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state

        placeholder = 'Vehicles which can be sold'
        disabled = False
        options=[]
        for vehicle in self.df_state.convoy_obj['vehicles']:
            if all(c['intrinsic'] for c in vehicle['cargo']):  # Check if any of the items in the 'cargo' list of the 'vehicle' have the 'intrinsic' key set to False.
                options.append(discord.SelectOption(label=f'{vehicle['name']} | ${vehicle['value']:,}', value=vehicle['vehicle_id']))
        if not options:
            placeholder = 'Convoy has no sellable vehicles'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]
        if not self.df_state.vendor_obj['vehicle_inventory']:
            placeholder = 'Vendor does not buy vehicles'
            disabled = True
        
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
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        part_list = []
        for category, part in self.df_state.vehicle_obj['parts'].items():
            if not part:  # If the part slot is empty
                part_list.append(f'- {category.replace('_', ' ').capitalize()}\n  - None')
                continue

            part_list.append(discord_app.cargo_views.format_part(part))
        displayable_vehicle_parts = '\n'.join(part_list)

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'## {self.df_state.vendor_obj['name']}',
            f'### {self.df_state.vehicle_obj['name']} | ${self.df_state.vehicle_obj['value']:,}',
            f'*{self.df_state.vehicle_obj['base_desc']}*',
            '### Parts',
            displayable_vehicle_parts,
            '### Stats'
        ])
        embed = discord_app.vehicle_views.df_embed_vehicle_stats(embed, self.df_state.vehicle_obj)

        view = VehicleSellConfirmView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


class VehicleSellConfirmView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=120)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyVehicleButton(self.df_state))

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

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Sell {self.df_state.vehicle_obj['name']} | ${self.df_state.vehicle_obj['value']:,}',
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.sell_vehicle(
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
            f'Your convoy sold {self.df_state.vehicle_obj['name']} for ${self.df_state.vehicle_obj['value']:,}',
            f'*{self.df_state.vehicle_obj['base_desc']}*'
        ])

        view = PostSellView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


class SellCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=3):
        self.df_state = df_state

        placeholder = 'Cargo which can be sold'
        disabled = False
        options=[]
        for vehicle in df_state.convoy_obj['vehicles']:
            for cargo in vehicle['cargo']:
                if not cargo['intrinsic']:
                    options.append(discord.SelectOption(label=f'{cargo['name']} | {vehicle['name']} | ${cargo['base_price']:,}', value=cargo['cargo_id']))
        if not options:
            placeholder = 'Convoy has no sellable cargo'
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
            c for c in self.df_state.convoy_obj['all_cargo']
            if c['cargo_id'] == self.values[0]
        ), None)

        embed = CargoSellQuantityEmbed(self.df_state)

        view = CargoSellQuantityView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


class CargoSellQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, sale_quantity: int=1):
        self.df_state = df_state
        self.sale_quantity = sale_quantity
        super().__init__()
        
        self = df_embed_author(self, self.df_state)
        
        sale_volume = self.sale_quantity * self.df_state.cargo_obj['volume']
        sale_weight = self.sale_quantity * self.df_state.cargo_obj['weight']

        desc = [f'## {self.df_state.vendor_obj['name']}']
        if self.df_state.cargo_obj['recipient'] == self.df_state.vendor_obj['vendor_id']:
            desc.append(f'### Delivering {self.df_state.cargo_obj['name']} for a reward of ${self.df_state.cargo_obj['delivery_reward']:,} per item')
            sale_price = self.sale_quantity * self.df_state.cargo_obj['delivery_reward']
        else:
            desc.append(f'### Selling {self.df_state.cargo_obj['name']} for ${self.df_state.cargo_obj['base_price']:,} per item')
            sale_price = self.sale_quantity * self.df_state.cargo_obj['base_price']
        desc.extend([
            f'*{self.df_state.cargo_obj['base_desc']}*',
            f'- Sale volume: {sale_volume:,}L',
            f'- Sale weight: {sale_weight:,}kg',
            f'### Sale: {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) | ${sale_price:,}'
        ])

        self.description = '\n'.join(desc)
        self.add_field(name='Inventory', value=self.df_state.cargo_obj['quantity'])
        self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['volume']} liter(s)')
        self.add_field(name='Weight (per unit)', value=f'{self.df_state.cargo_obj['weight']} kilogram(s)')


class CargoSellQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, sale_quantity: int=1):
        self.df_state = df_state
        self.sale_quantity = sale_quantity
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, -10, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, -1, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 1, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 10, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 'max', cargo_for_sale=self.df_state.cargo_obj))

        self.add_item(CargoConfirmSellButton(self.df_state, self.sale_quantity, row=2))

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


class CargoConfirmSellButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            sale_quantity: int,
            row: int=1
    ):
        self.df_state = df_state
        self.sale_quantity = sale_quantity

        if self.df_state.cargo_obj['recipient'] == self.df_state.vendor_obj['vendor_id']:
            sale_price = self.sale_quantity * self.df_state.cargo_obj['delivery_reward']
        else:
            sale_price = self.sale_quantity * self.df_state.cargo_obj['base_price']

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Sell {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) | ${sale_price}',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        
        try:
            self.df_state.convoy_obj = await api_calls.sell_cargo(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                cargo_id=self.df_state.cargo_obj['cargo_id'],
                quantity=self.sale_quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        
        sale_price = self.sale_quantity * self.df_state.cargo_obj['base_price']
        
        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        desc = [f'## {self.df_state.vendor_obj['name']}']
        if self.df_state.cargo_obj['recipient'] == self.df_state.vendor_obj['vendor_id']:
            delivery_reward = self.sale_quantity * self.df_state.cargo_obj['delivery_reward']
            desc.append(f'Delivered {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) for ${delivery_reward}')
        else:
            desc.append(f'Sold {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) for ${sale_price}')
        embed.description = '\n'.join(desc)

        view = PostSellView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


class PostSellView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

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
