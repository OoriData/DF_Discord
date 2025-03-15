# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, handle_timeout, df_embed_author, add_tutorial_embed, get_user_metadata, validate_interaction, DF_LOGO_EMOJI, get_cargo_emoji
from discord_app.map_rendering import add_map_to_embed
from discord_app.vendor_views  import vendor_inv_md
import                                discord_app.nav_menus
import                                discord_app.vendor_views.vendor_menus
import                                discord_app.vehicle_menus
import                                discord_app.cargo_menus

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


async def buy_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=buy_menu)  # Add this menu to the back stack

    menu_embed = discord.Embed()

    for cargo in df_state.vendor_obj['cargo_inventory']:
        if cargo['recipient']:
            cargo['recipient_vendor'] = await api_calls.get_vendor(vendor_id=cargo['recipient'])
            cargo['recipient_location'] = next((
                s['name']
                for row in df_state.map_obj['tiles']
                for t in row
                for s in t['settlements']
                if s['sett_id'] == cargo['recipient_vendor']['sett_id']
            ), None)
    menu_embed.description = await vendor_inv_md(df_state.vendor_obj, verbose=True)

    menu_embed = df_embed_author(menu_embed, df_state)

    embeds = [menu_embed]
    embeds = add_tutorial_embed(embeds, df_state)

    buy_view = BuyView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=buy_view)

class BuyView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyResourceButton(self.df_state, 'fuel'))
        self.add_item(BuyResourceButton(self.df_state, 'water'))
        self.add_item(BuyResourceButton(self.df_state, 'food'))

        self.add_item(BuyVehicleSelect(self.df_state))

        self.add_item(BuyCargoSelect(self.df_state))

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                match tutorial_stage:
                    case 1:
                        item.disabled = item.custom_id not in (
                            'nav_back_button',
                            'nav_sett_button',
                            'select_vehicle'
                        )
                    case 2 | 4:
                        item.disabled = item.custom_id not in (
                            'nav_back_button',
                            'nav_sett_button',
                            'select_cargo'
                        )

    async def on_timeout(self):
        await handle_timeout(self.df_state)

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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction
        await buy_resource_menu(self.df_state, self.resource_type)

class BuyVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state
        
        placeholder = 'Vehicle Inventory'
        disabled = False

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL
        if tutorial_stage == 1:
            options=[
                discord.SelectOption(
                    label=f'{vehicle['name']} | ${vehicle['value']:,.0f}',
                    value=vehicle['vehicle_id'],
                    emoji=DF_LOGO_EMOJI if (  # Add the tutorial emoji if
                        vehicle['value'] < 5000  # The vehicle's value is less than 5000
                        and vehicle['base_cargo_capacity'] > 400  # The vehicle's value is greater than 500
                    ) else None  # Else, don't add the emoji
                )
                for vehicle in self.df_state.vendor_obj['vehicle_inventory']
            ]
        else:
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        self.df_state.vehicle_obj = next((
            v for v in self.df_state.vendor_obj['vehicle_inventory']
            if v['vehicle_id'] == self.values[0]
        ), None)

        await buy_vehicle_menu(self.df_state)

class BuyCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=3):
        self.df_state = df_state

        placeholder = 'Cargo Inventory'
        disabled = False

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')

        options = []
        for cargo in self.df_state.vendor_obj['cargo_inventory']:

            label = f'{cargo['name']} | ${cargo['price']:,.0f}'
            if cargo.get('recipient_vendor'):
                label += f' | {cargo['recipient_location']}'

            emoji = get_cargo_emoji(cargo)
            
            if (
                len(self.df_state.user_obj['convoys']) == 1 and
                cargo['name'] == 'Mail'
            ):
                emoji = DF_LOGO_EMOJI

            # Emoji based on tutorial stage
            if tutorial_stage == 2:
                if cargo['name'] in {'Water Jerry Cans', 'MRE Boxes'}:
                    emoji = DF_LOGO_EMOJI
            elif tutorial_stage == 4:
                if (
                    cargo['volume'] < self.df_state.convoy_obj['total_free_space'] and
                    cargo['weight'] < self.df_state.convoy_obj['total_remaining_capacity'] and
                    cargo['price'] < self.df_state.convoy_obj['money'] and
                    cargo['capacity'] is None
                ):
                    emoji = DF_LOGO_EMOJI

            options.append(discord.SelectOption(
                label=label,  # No emoji in label
                value=cargo['cargo_id'],
                emoji=emoji  # Emoji added here
            ))

        if not options:
            placeholder = 'Vendor has no cargo inventory'
            disabled = True
            options = [discord.SelectOption(label='None', value='None')]
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=disabled,
            custom_id='select_cargo',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        self.df_state.cargo_obj = next((
            c for c in self.df_state.vendor_obj['cargo_inventory']
            if c['cargo_id'] == self.values[0]
        ), None)

        await buy_cargo_menu(self.df_state)


async def buy_resource_menu(df_state: DFState, resource_type: str):
    df_state.append_menu_to_back_stack(func=buy_resource_menu, args={'resource_type': resource_type})  # Add this menu to the back stack

    embed = ResourceBuyQuantityEmbed(df_state, resource_type)
    view = ResourceBuyQuantityView(df_state, resource_type)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

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
            f'### Cart: {self.cart_quantity:,.2f} Liters/meals | ${cart_price:,.0f}'
        ])

class ResourceBuyQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, resource_type: str, cart_quantity: int=1):
        self.df_state = df_state
        self.resource_type = resource_type
        self.cart_quantity = cart_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, -10, self.resource_type))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, -1, self.resource_type))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 1, self.resource_type))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 10, self.resource_type))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 'max', self.resource_type))

        self.add_item(ResourceConfirmBuyButton(self.df_state, self.cart_quantity, self.resource_type, row=2))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class ResourceConfirmBuyButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            cart_quantity: int,
            resource_type: str | None = None,
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
            f'Purchased {self.cart_quantity:,.2f} Liters/meals of {self.resource_type} for ${cart_price:,.0f}'
        ])

        view = PostBuyView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


async def buy_cargo_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=buy_cargo_menu)  # Add this menu to the back stack

    embed = CargoBuyQuantityEmbed(df_state)

    embeds = [embed]
    embeds = add_tutorial_embed(embeds, df_state)

    view = CargoBuyQuantityView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class CargoBuyQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, cart_quantity: int=1):
        self.df_state = df_state
        self.cart_quantity = cart_quantity
        super().__init__()
        
        self = df_embed_author(self, self.df_state)
        
        cart_price = self.cart_quantity * self.df_state.cargo_obj['price']
        cart_volume = self.cart_quantity * self.df_state.cargo_obj['volume']
        
        resource_weights = {'fuel': 0.79, 'water': 1, 'food': 0.75}
        resource_weight = next(  # Check if cargo has any resources in it
            (weight for key, weight in resource_weights.items() if self.df_state.cargo_obj.get(key)),
            None  # Default to None, in case that cargo contains no resource
        )
        cart_weight = self.cart_quantity * self.df_state.cargo_obj['weight']  # Calc (empty) weight
        if resource_weight:  # Calc resource weight
            cart_weight += self.cart_quantity * self.df_state.cargo_obj['capacity'] * resource_weight

        desc = [
            f'## {self.df_state.vendor_obj['name']}',
            f'### Buying {self.df_state.cargo_obj['name']} for ${self.df_state.cargo_obj['price']:,.0f} per item',
            f'*{self.df_state.cargo_obj['base_desc']}*',
            '',
            f'- Cart volume: **{cart_volume:,.1f}L**',
            f'  - {self.df_state.convoy_obj['total_free_space']:,.0f}L free space in convoy',
            f'- Cart weight: **{cart_weight:,.1f}kg**',
            f'  - {self.df_state.convoy_obj['total_remaining_capacity']:,.0f}kg weight capacity in convoy',
        ]
        if self.df_state.cargo_obj['recipient']:
            delivery_reward = self.cart_quantity * self.df_state.cargo_obj['delivery_reward']
            desc.extend([
                '',
                f'💰 **Deliver to {self.df_state.cargo_obj['recipient_vendor']['name']} for a reward of ${delivery_reward:,.0f}**'
            ])
        desc.append(
            f'### Cart: {self.cart_quantity:,} {self.df_state.cargo_obj['name']}(s) | ${cart_price:,.0f}'
        )

        self.description = '\n'.join(desc)

        if get_user_metadata(df_state, 'mobile'):
            self.description += '\n' + '\n'.join([
                f'- Vendor Inventory: {self.df_state.cargo_obj['quantity']}',
                f'- Volume (per unit): {self.df_state.cargo_obj['volume']}L',
                f'- Weight (per unit): {self.df_state.cargo_obj['weight']}kg'
            ])
        else:
            self.add_field(name='Vendor Inventory', value=self.df_state.cargo_obj['quantity'])
            self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['volume']} liter(s)')
            self.add_field(name='Weight (per unit)', value=f'{self.df_state.cargo_obj['weight']} kilogram(s)')

class CargoBuyQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, cart_quantity: int=1):
        self.df_state = df_state
        self.cart_quantity = cart_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, -10, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, -1, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 1, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 10, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantityBuyButton(self.df_state, self.cart_quantity, 'max', cargo_for_sale=self.df_state.cargo_obj))

        self.add_item(CargoConfirmBuyButton(self.df_state, self.cart_quantity, row=2))
        if self.df_state.cargo_obj['recipient']:
            self.add_item(discord_app.cargo_menus.MapButton(self.df_state, self.df_state.cargo_obj['recipient_vendor'], row=2))

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                if item.custom_id not in {'-10_button', '-1_button', '1_button', '10_button', 'max_button'}:
                    match tutorial_stage:  # Use match-case to handle different tutorial stages
                        case 2:
                            if not self.df_state.cargo_obj['recipient']:  # if the cargo doesn't have a recipient
                                item.disabled = item.custom_id not in (
                                    'nav_back_button',
                                    'nav_sett_button',
                                    'buy_cargo_button'
                                )
                            else:  # Don't let players buy commerce cargo early
                                item.disabled = item.custom_id not in (
                                    'nav_back_button',
                                    'nav_sett_button'
                                )
                        case 4:
                            item.disabled = item.custom_id not in (
                                'nav_back_button',
                                'nav_sett_button',
                                'buy_cargo_button',
                                'map_button'
                            )

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class CargoConfirmBuyButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            cart_quantity: int,
            row: int=1
    ):
        self.df_state = df_state
        self.cart_quantity = cart_quantity

        cart_price = self.cart_quantity * self.df_state.cargo_obj['price']

        label = f'Buy {self.cart_quantity} {self.df_state.cargo_obj['name']}(s) | ${cart_price:,.0f}'
        disabled = False

        if get_user_metadata(self.df_state, 'tutorial') == 2:
            if self.df_state.cargo_obj['recipient']:  # if commerce cargo
                label = 'You must buy water and food cargo first!'
                disabled = True

        super().__init__(
            style=discord.ButtonStyle.green,
            label=label,
            disabled=disabled,
            custom_id='buy_cargo_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        
        cart_price = self.cart_quantity * self.df_state.cargo_obj['price']
        
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


class QuantityBuyButton(discord.ui.Button):  # XXX: Explode this button into like 4 different buttons, instead of just nesting a million if/elses
    def __init__(
            self,
            df_state: DFState,
            cart_quantity: int,
            button_quantity: int | str,
            resource_type: str | None = None,
            cargo_for_sale: dict | None = None,
            row: int = 1
    ):
        self.df_state = df_state
        self.cart_quantity = cart_quantity
        self.resource_type = resource_type
        self.cargo_for_sale = cargo_for_sale

        if self.cargo_for_sale:  # Determine max quantities
            cargo_obj = self.df_state.cargo_obj
            quantity = 0
            for vehicle in self.df_state.convoy_obj['vehicles']:
                # Determine max quantity by volume
                free_space = vehicle['free_space']
                max_by_volume = free_space / cargo_obj['volume']
                
                # Determine max quantity by weight
                weight_capacity = vehicle['remaining_capacity']
                max_by_weight = weight_capacity / cargo_obj['weight']

                # Determine max quantity by price
                convoy_money = self.df_state.convoy_obj['money']
                max_by_price = convoy_money / cargo_obj['price']

                quantity += int(min(max_by_volume, max_by_weight, max_by_price))

            max_convoy_capacity = quantity
            inventory_quantity = self.df_state.cargo_obj['quantity']
        else:
            max_convoy_capacity = self.df_state.convoy_obj[f'max_{self.resource_type}'] - self.df_state.convoy_obj[self.resource_type]
            inventory_quantity = self.df_state.vendor_obj[self.resource_type]

        if button_quantity == 'max':  # Handle "max" button logic
            self.button_quantity = min(max_convoy_capacity, inventory_quantity) - self.cart_quantity
            self.button_quantity = max(0, self.button_quantity)  # Ensure the quantity is 0 or greater
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

            cart_price = resultant_quantity * self.df_state.cargo_obj['price']
            
        else:
            if resultant_quantity > max_convoy_capacity:
                return True

            cart_price = resultant_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']

        if cart_price > self.df_state.convoy_obj['money']:
                return True

        return False

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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


async def buy_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=buy_vehicle_menu)  # Add this menu to the back stack

    part_list = []
    for part in df_state.vehicle_obj['parts']:
        if not part:  # If the part slot is empty
            part_list.append(f'- {part['slot'].replace('_', ' ').capitalize()}\n  - None')
            continue

        part_list.append(discord_app.cargo_menus.format_part(part))
    displayable_vehicle_parts = '\n'.join(part_list)

    vehicle_buy_confirm_embed = discord.Embed()
    vehicle_buy_confirm_embed = df_embed_author(vehicle_buy_confirm_embed, df_state)
    vehicle_buy_confirm_embed.description = '\n'.join([
        f'## {df_state.vendor_obj['name']}',
        f'### {df_state.vehicle_obj['name']} | ${df_state.vehicle_obj['value']:,.0f}',
        f'*{df_state.vehicle_obj['description']}*',
        '### Parts',
        displayable_vehicle_parts,
        '### Stats'
    ])
    vehicle_buy_confirm_embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, vehicle_buy_confirm_embed, df_state.vehicle_obj)

    embeds = [vehicle_buy_confirm_embed]
    embeds = add_tutorial_embed(embeds, df_state)

    vehicle_buy_confirm_view = VehicleBuyConfirmView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=vehicle_buy_confirm_view)

class VehicleBuyConfirmView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyVehicleButton(self.df_state))

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                item.disabled = item.custom_id not in (
                    'nav_back_button',
                    'nav_sett_button',
                    'buy_vehicle_button'
                )

    async def on_timeout(self):
        await handle_timeout(self.df_state)

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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
            f'*{self.df_state.vehicle_obj['description']}*'
        ])

        embeds = [embed]
        embeds = add_tutorial_embed(embeds, self.df_state)

        view = PostBuyView(self.df_state)

        await interaction.response.edit_message(embeds=embeds, view=view)


class PostBuyView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                match tutorial_stage:  # Use match-case to handle different tutorial stages
                    case 1 | 2 | 3 | 4:  # Enable 'nav_sett_button' only for stages 1-4, disable all others
                        item.disabled = item.custom_id not in (
                            'nav_back_button',
                            'nav_sett_button'
                        )
                    case 5:  # Enable 'send_convoy_button' for stage 5, disable all others
                        item.disabled = item.custom_id not in (
                            'nav_back_button',
                            'nav_convoy_button'
                        )

    async def on_timeout(self):
        await handle_timeout(self.df_state)


class TopUpButton(discord.ui.Button):
    def __init__(self, df_state: DFState, menu, menu_args=None, row: int=1):
        self.df_state = df_state
        self.menu = menu
        self.menu_args = menu_args if menu_args is not None else {}

        # Initialize with disabled state and empty values
        self.resource_vendors = {}
        self.top_up_price = 0
        label = 'Cannot top up: No vendors'
        disabled = True

        if self.df_state.sett_obj is not None and 'vendors' in self.df_state.sett_obj:  # Only proceed with resource calculations if settlement exists and has vendors
            resource_types = ['fuel', 'water', 'food']
            available_resources = []

            for resource_type in resource_types:
                # Calculate convoy's need for each resource
                convoy_need = self.df_state.convoy_obj[f'max_{resource_type}'] - self.df_state.convoy_obj[resource_type]
                if convoy_need > 0:
                    vendor = min(
                        (v for v in self.df_state.sett_obj['vendors'] if v.get(f'{resource_type}_price') is not None),
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
                else:
                    label = 'Convoy is already topped up'

            if available_resources:  # Update label and disabled state based on available resources
                available_resources_str = ', '.join(available_resources)
                if self.top_up_price != 0:
                    label = f'Top up {available_resources_str} | ${self.top_up_price:,.0f}'
                    disabled = self.top_up_price > self.df_state.convoy_obj['money']

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
            custom_id='top_up_button',
            emoji='🛒',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        if not interaction.response.is_done():
            await interaction.response.defer()

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

            receipt_embed = discord.Embed(description=f'### Topped up all resources for ${self.top_up_price:,.0f}')

            await self.menu(
                df_state=self.df_state,
                follow_on_embeds=[receipt_embed],
                **self.menu_args
            )

        except RuntimeError as e:
            # Handle error response
            await interaction.response.send_message(content=str(e), ephemeral=True)
