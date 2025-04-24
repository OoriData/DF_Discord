# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                math

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import (
    api_calls, handle_timeout, df_embed_author, add_tutorial_embed, get_user_metadata, validate_interaction,
    DF_LOGO_EMOJI, get_cargo_emoji, get_vehicle_emoji
)
from discord_app.map_rendering import add_map_to_embed
from discord_app.vendor_views  import vendor_inv_md, wet_price
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

    df_state.vendor_obj['vehicle_inventory'] = sorted(df_state.vendor_obj['vehicle_inventory'], key=lambda x: x['name'])
    df_state.vendor_obj['cargo_inventory'] = sorted(df_state.vendor_obj['cargo_inventory'], key=lambda x: x['name'])

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
                discord.SelectOption(
                    label=f'{vehicle['name']} | ${vehicle['value']:,.0f}',
                    value=vehicle['vehicle_id'],
                    emoji=get_vehicle_emoji(vehicle['shape'])
                )
                for vehicle in self.df_state.vendor_obj['vehicle_inventory']
            ]
        if not options:
            placeholder = 'Vendor has no vehicle inventory'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options,
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
            wet_unit_price = wet_price(cargo, self.df_state.vendor_obj)

            label = f'{cargo['name']} | ${wet_unit_price:,.0f}'
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
                    cargo['unit_volume'] < self.df_state.convoy_obj['total_free_space'] and
                    cargo['unit_dry_weight'] < self.df_state.convoy_obj['total_remaining_capacity'] and
                    cargo['unit_price'] < self.df_state.convoy_obj['money'] and
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

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options,
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
    if not df_state.vendor_obj:
        await discord_app.vendor_views.vendor_menus.vendor_menu(df_state)
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

        cart_price = wet_price(self.df_state.cargo_obj, self.df_state.vendor_obj, self.cart_quantity)

        cart_volume = self.cart_quantity * self.df_state.cargo_obj['unit_volume']
        cart_weight = self.cart_quantity * self.df_state.cargo_obj['unit_weight']

        desc = [
            f'## {self.df_state.vendor_obj['name']}',
            f'### Buying {self.df_state.cargo_obj['name']} for ${cart_price / self.cart_quantity:,.0f} per item',
            f'*{self.df_state.cargo_obj['base_desc']}*',
            '',
            f'- Cart volume: **{cart_volume:,.1f}L**',
            f'  - {self.df_state.convoy_obj['total_free_space']:,.0f}L free space in convoy',
            f'- Cart weight: **{cart_weight:,.1f}kg**',
            f'  - {self.df_state.convoy_obj['total_remaining_capacity']:,.0f}kg weight capacity in convoy',
        ]
        if self.df_state.cargo_obj['recipient']:
            cart_delivery_reward = self.cart_quantity * self.df_state.cargo_obj['unit_delivery_reward']
            desc.extend([
                '',
                f'💰 **Deliver to {self.df_state.cargo_obj['recipient_vendor']['name']} for a reward of ${cart_delivery_reward:,.0f}**'
            ])
        desc.append(
            f'### Cart: {self.cart_quantity:,} {self.df_state.cargo_obj['name']}(s) | ${cart_price:,.0f}'
        )

        self.description = '\n'.join(desc)

        if get_user_metadata(df_state, 'mobile'):
            self.description += '\n' + '\n'.join([
                f'- Vendor Inventory: {self.df_state.cargo_obj['quantity']}',
                f'- Volume (per unit): {self.df_state.cargo_obj['unit_volume']}L',
                f'- Dry Weight (per unit): {self.df_state.cargo_obj['unit_dry_weight']}kg'
            ])
        else:
            self.add_field(name='Vendor Inventory', value=self.df_state.cargo_obj['quantity'])
            self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['unit_volume']} liter(s)')
            self.add_field(name='Dry Weight (per unit)', value=f'{self.df_state.cargo_obj['unit_dry_weight']} kilogram(s)')

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

        cart_price = wet_price(self.df_state.cargo_obj, self.df_state.vendor_obj, self.cart_quantity)

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

        cart_price = wet_price(self.df_state.cargo_obj, self.df_state.vendor_obj, self.cart_quantity)

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        desc = [
            f'## {self.df_state.vendor_obj['name']}',
            f'Purchased {self.cart_quantity} {self.df_state.cargo_obj['name']}(s) for ${cart_price:,.0f}'
        ]
        if self.df_state.cargo_obj['recipient']:
            delivery_reward = self.cart_quantity * self.df_state.cargo_obj['unit_delivery_reward']
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
                max_by_volume = free_space / cargo_obj['unit_volume']

                # Determine max quantity by weight
                weight_capacity = vehicle['remaining_capacity']
                max_by_weight = weight_capacity / cargo_obj['unit_weight']

                # Determine max quantity by price
                convoy_money = self.df_state.convoy_obj['money']
                max_by_price = convoy_money / cargo_obj['unit_price']

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
            max_by_volume = self.df_state.convoy_obj['total_free_space'] / self.df_state.cargo_obj['unit_volume']
            max_by_weight = self.df_state.convoy_obj['total_remaining_capacity'] / self.df_state.cargo_obj['unit_weight']
            if resultant_quantity > max_by_volume or resultant_quantity > max_by_weight:
                return True

            cart_price = wet_price(self.df_state.cargo_obj, self.df_state.vendor_obj, self.cart_quantity)

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
    """
    A Discord UI button that allows users to top up convoy resources (fuel, water, food)
    from the cheapest available vendors in the current settlement, considering convoy
    capacity and available funds.

    Attributes:
        df_state (DFState): The current state object containing convoy, settlement, and other relevant data.
        menu (callable): The function to call to refresh or display the parent menu after the action is performed.
        menu_args (dict): Arguments to pass to the menu function.
        resource_vendors (dict): Stores the details of vendors and quantities for each resource planned for purchase.
                                 Structure: { 'resource_type': {'vendor_id': ..., 'price': ..., 'quantity': ...} }
        total_top_up_cost (int): The total calculated cost for topping up resources.
    """
    def __init__(self, df_state: DFState, menu: callable, menu_args: dict | None = None, row: int = 1):
        """
        Initializes the TopUpButton.

        Calculates the optimal top-up plan based on resource needs, vendor prices,
        convoy capacity, and sets the button's label, state (enabled/disabled),
        and appearance accordingly.

        Args:
            df_state: The application's state object.
            menu: The callback function to invoke for updating the UI menu.
            menu_args: Optional dictionary of arguments for the menu function.
            row: The row number for button placement in the Discord view.
        """
        self.df_state = df_state
        self.menu = menu
        self.menu_args = menu_args if menu_args is not None else {}

        self.resource_types = ['fuel', 'water', 'food']
        self.resource_metadata = {
            'fuel': {'emoji': '⛽️', 'unit': 'liter'},
            'water': {'emoji': '💧', 'unit': 'liter'},
            'food': {'emoji': '🥪', 'unit': 'meal'}
        }

        # --- State Initialization ---
        # These will be populated by _calculate_top_up_plan
        self.resource_vendors: dict[str, dict] = {}
        self.total_top_up_cost: int = 0
        # Default button state
        button_label = 'Cannot top up: No vendors'
        button_disabled = True

        # --- Core Logic Execution ---
        # Check prerequisites for topping up
        if self._can_attempt_top_up():
            # Calculate the top-up plan (which vendors, how much, cost)
            planned_resources, self.total_top_up_cost, self.resource_vendors = self._calculate_top_up_plan()

            # Determine the button's final label and enabled/disabled state based on the plan
            button_label, button_disabled = self._determine_button_state(
                planned_resources=planned_resources,
                total_cost=self.total_top_up_cost,
                has_vendors=True # We know vendors exist if we got this far
            )
        else:
            # Determine button state when prerequisites aren't met (no settlement/vendors)
            button_label, button_disabled = self._determine_button_state(
                planned_resources=[],
                total_cost=0,
                has_vendors=bool(self.df_state.sett_obj and 'vendors' in self.df_state.sett_obj)
            )

        # --- Final Button Setup ---
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=button_label,
            disabled=button_disabled,
            custom_id='top_up_button', # Make sure this ID is unique if multiple buttons exist
            emoji='🛒',
            row=row
        )

    def _can_attempt_top_up(self) -> bool:
        """Checks if the basic conditions for attempting a top-up are met."""
        # Requires a settlement object with a list of vendors.
        return bool(
            self.df_state.sett_obj and
            'vendors' in self.df_state.sett_obj and
            self.df_state.sett_obj['vendors'] # Ensure the list isn't empty
        )

    def _get_resource_priority_order(self) -> list[str]:
        """
        Determines the order in which resources should be topped up,
        prioritizing those with the lowest fill percentage.
        """
        convoy = self.df_state.convoy_obj

        def fill_percentage(resource_type: str) -> float:
            current = convoy.get(resource_type, 0)
            maximum = max(convoy.get(f'max_{resource_type}', 1), 1) # Avoid division by zero
            return current / maximum

        # Sort resource types by their fill percentage (ascending)
        return sorted(self.resource_types, key=fill_percentage)

    def _find_cheapest_vendor_for_resource(self, resource_type: str) -> dict | None:
        """Finds the vendor offering the lowest price for a given resource type."""
        price_key = f'{resource_type}_price'
        valid_vendors = [
            v for v in self.df_state.sett_obj.get('vendors', [])
            if v.get(price_key) is not None # Check if vendor sells this resource
        ]

        if not valid_vendors:
            return None # No vendor sells this resource

        # Find the vendor with the minimum price for this resource
        return min(valid_vendors, key=lambda v: v[price_key])

    def _calculate_top_up_plan(self) -> tuple[list[str], int, dict]:
        """
        Calculates the optimal resource top-up plan based on need, vendor prices,
        and convoy weight capacity.

        Returns:
            A tuple containing:
            - list[str]: The names of resources included in the top-up plan.
            - int: The total calculated cost of the top-up plan.
            - dict: A dictionary detailing the vendor, price, and quantity for each
                    resource in the plan. Structure:
                    { 'resource_type': {'vendor_id': ..., 'price': ..., 'quantity': ...} }
        """
        convoy = self.df_state.convoy_obj
        weights = self.df_state.misc.get('resource_weights', {})

        # Get initial state
        remaining_weight = convoy.get('total_remaining_capacity', 0)
        sorted_resource_types = self._get_resource_priority_order()

        # Variables to store the plan details
        planned_resources = []
        total_cost = 0
        resource_purchase_details = {} # Replaces self.resource_vendors during calculation

        # Iterate through resources by priority
        for resource_type in sorted_resource_types:
            # Check if we still have capacity
            if remaining_weight <= 0:
                break # Stop if convoy is full by weight

            # Calculate how much of the resource the convoy needs
            current_amount = convoy.get(resource_type, 0)
            max_capacity = convoy.get(f'max_{resource_type}', 0)
            needed_quantity = max(0, max_capacity - current_amount)

            # Skip if this resource is already full
            if needed_quantity <= 0:
                continue

            # Find the best vendor for this resource
            cheapest_vendor = self._find_cheapest_vendor_for_resource(resource_type)
            if not cheapest_vendor:
                continue # Skip if no vendor sells this resource

            # Determine purchase limits based on weight
            weight_per_unit = weights.get(resource_type, 1.0) # Default weight if not specified
            if weight_per_unit <= 0: # Avoid division by zero or infinite purchase
                weight_per_unit = 1.0

            max_units_by_weight = math.floor(remaining_weight / weight_per_unit)

            # Determine the actual quantity to buy (minimum of need and capacity)
            actual_quantity_to_buy = min(needed_quantity, max_units_by_weight)

            # Skip if we can't buy any (due to weight constraints)
            if actual_quantity_to_buy <= 0:
                continue

            # Calculate cost and update plan
            price = cheapest_vendor[f'{resource_type}_price']
            cost_for_resource = actual_quantity_to_buy * price

            # Add to plan if cost is positive (don't add free items if logic changes)
            if cost_for_resource >= 0: # Allow free items if price is 0
                total_cost += cost_for_resource
                planned_resources.append(resource_type)
                resource_purchase_details[resource_type] = {
                    'vendor_id': cheapest_vendor['vendor_id'],
                    'price': price,
                    'quantity': actual_quantity_to_buy # Use 'quantity' for clarity
                }

                # Update remaining weight capacity
                remaining_weight -= actual_quantity_to_buy * weight_per_unit

        return planned_resources, int(round(total_cost)), resource_purchase_details

    def _determine_button_state(
            self,
            planned_resources: list[str],
            total_cost: int,
            has_vendors: bool
    ) -> tuple[str, bool]:
        """
        Determines the button's label and enabled/disabled state based on the
        calculated top-up plan and convoy status.

        Args:
            planned_resources: List of resource types included in the plan.
            total_cost: The total cost of the planned top-up.
            has_vendors: Boolean indicating if vendors exist in the settlement.

        Returns:
            A tuple containing:
            - str: The button label.
            - bool: The button disabled state (True for disabled, False for enabled).
        """
        convoy = self.df_state.convoy_obj
        can_afford = total_cost <= convoy.get('money', 0)

        if planned_resources and total_cost > 0:
            # Case 1: Resources can be bought, and they cost something.
            label = f'Top up {", ".join(planned_resources)} | ${total_cost:,.0f}'
            disabled = not can_afford # Disable if cannot afford
            if disabled:
                 label += ' (Insufficient Funds)' # Add reason if disabled
        elif planned_resources and total_cost == 0:
            # Case 2: Resources can be 'bought' (potentially free?), convoy has space.
            label = f'Top up {", ".join(planned_resources)} | $0' # Indicate free top-up
            disabled = False # Always enable if free and possible
        elif total_cost == 0 and not planned_resources:
            # Case 3: Nothing to buy, cost is zero. Implies convoy is full of needed resources.
            label = 'Convoy is already topped up'
            disabled = True
        elif not has_vendors:
            # Case 4: No vendors available in the settlement.
            label = 'No vendors available for top up'
            disabled = True
        # Note: The original code had a check for `remaining_weight <= 0` leading to "Convoy is full".
        # This case is now implicitly handled. If remaining_weight was 0 initially or became 0,
        # `planned_resources` might be empty or incomplete. If it's empty, Case 3 applies.
        # If it's incomplete but > 0 cost, Case 1 applies. If it's empty because needs were met
        # before running out of weight, Case 3 applies. A specific "Convoy is full" message
        # might be less informative than "Already topped up" or showing what *can* be bought.
        # If you specifically need "Convoy is full" when weight is the sole limiter even if
        # needs aren't met, more complex state tracking from _calculate_top_up_plan is needed.
        else:
            # Case 5: Fallback - Cannot top up for other reasons (e.g., needs met,
            # but weight full before considering all items, or specific items unavailable).
            # This state might be reached if weight is full but *some* resources are still needed
            # but cannot be bought due to weight, and no other resources were plannable.
            # Or if vendors only sell items the convoy doesn't need.
            label = 'Cannot top up' # General unavailability
            disabled = True

        return label, disabled

    async def callback(self, interaction: discord.Interaction):
        """
        Executed when the button is clicked.

        Validates the interaction, performs the resource purchase API calls based
        on the plan calculated in __init__, sends a receipt, and updates the menu.
        Handles potential errors during the purchase process.
        """
        # --- Interaction Validation and Deferral ---
        # Use the provided validation function. Ensure it handles state checks if needed.
        # If validate_interaction could modify df_state, consider its placement carefully.
        # await validate_interaction(interaction=interaction, df_state=self.df_state) # Uncomment if needed
        self.df_state.interaction = interaction # Store interaction for potential use

        # Defer the interaction response immediately to prevent timeouts,
        # especially as API calls can take time.
        if not interaction.response.is_done():
            await interaction.response.defer()

        # --- Check if there's anything to buy ---
        if not self.resource_vendors or self.total_top_up_cost < 0: # Cost < 0 check as safeguard
            # This should ideally not happen if the button wasn't disabled, but good practice.
            await interaction.followup.send('Nothing to top up or an error occurred in planning.', ephemeral=True)
            return

        # --- Execute Purchases ---
        try:
            topped_up_details = [] # For building the receipt message

            # Iterate through the pre-calculated plan
            for resource_type, purchase_info in self.resource_vendors.items():
                vendor_id = purchase_info['vendor_id']
                quantity = purchase_info['quantity']
                price = purchase_info['price']

                # Check if quantity is valid before calling API
                if quantity <= 0:
                    # Log this unexpected state if possible
                    print(f'Warning: Skipped buying {resource_type} due to zero quantity in plan.')
                    continue

                # --- API Call ---
                # Assuming api_calls.buy_resource performs the transaction and returns
                # the *updated* convoy object state. If it only returns success/failure,
                # you might need a separate call to refresh df_state.convoy_obj afterwards.
                updated_convoy_obj = await api_calls.buy_resource(
                    vendor_id=vendor_id,
                    convoy_id=self.df_state.convoy_obj['convoy_id'],
                    resource_type=resource_type,
                    quantity=quantity
                )
                # --- State Update ---
                # CRITICAL: Update the state object with the result from the API call.
                self.df_state.convoy_obj = updated_convoy_obj

                # --- Receipt Message Preparation ---
                meta = self.resource_metadata.get(resource_type, {'emoji': '📦', 'unit': 'unit'}) # Fallback metadata
                topped_up_details.append(
                    f'- {meta['emoji']} {quantity} {resource_type.capitalize()} for '
                    f'${price:,.0f} per {meta['unit']}' # Show per unit price
                )

            # --- Success Feedback ---
            receipt_embed = discord.Embed(
                color=discord.Color.green(),
                title='Top-Up Successful',
                description='\n'.join([
                    f'### Topped up all resources for ${self.total_top_up_cost:,.0f}',
                    *topped_up_details
                    ])
                )

            # --- Update Original Menu/View ---
            # Call the menu function passed during initialization to refresh the UI.
            # Pass the updated df_state and the receipt embed.
            await self.menu(
                df_state=self.df_state,
                follow_on_embeds=[receipt_embed], # Use a consistent kwarg name
                **self.menu_args
            )

        except RuntimeError as e: # Catch specific errors from api_calls if possible
            # --- Error Handling ---
            error_embed = discord.Embed(
                color=discord.Color.red(),
                title='Top-Up Failed',
                description=f'An error occurred: {e}'
            )
            # Use followup because we deferred earlier. Send ephemeral so only user sees error.
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            # Optionally, you might want to refresh the menu even on failure
            # to show the potentially unchanged state, depending on UX preference.
            # await self.menu(df_state=self.df_state, **self.menu_args)

        except Exception as e: # Catch unexpected errors
            # Log the full error for debugging
            # print(f'An unexpected error occurred during top-up callback: {e}')
            # Inform the user generically
            await interaction.followup.send('An unexpected error occurred. Please try again later.', ephemeral=True)
