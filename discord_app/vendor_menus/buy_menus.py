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
from discord_app.vendor_menus  import vendor_inv_embeds, wet_price
import                                discord_app.nav_menus
import                                discord_app.vendor_menus.vendor_menus
import                                discord_app.vehicle_menus
import                                discord_app.cargo_menus

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


async def buy_menu(df_state: DFState):
    if not df_state.vendor_obj:
        await discord_app.vendor_menus.vendor_menus.vendor_menu(df_state)
    df_state.append_menu_to_back_stack(func=buy_menu)  # Add this menu to the back stack

    df_state.vendor_obj['vehicle_inventory'] = sorted(
        df_state.vendor_obj['vehicle_inventory'],
        key=lambda x: x['value']
    )
    df_state.vendor_obj['cargo_inventory'] = sorted(
        df_state.vendor_obj['cargo_inventory'],
        key=lambda x: x['unit_price']
    )

    buy_embed = discord.Embed()
    buy_embed = df_embed_author(buy_embed, df_state)
    buy_embed.description = f'## {df_state.vendor_obj['name']}'

    embeds = await vendor_inv_embeds(df_state, [buy_embed], verbose=True)

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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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

        # sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Alr sorted by menu that calls this select
        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=disabled,
            custom_id='select_vehicle',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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

        # sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Alr sorted by menu that calls this select
        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=disabled,
            custom_id='select_cargo',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        self.df_state.cargo_obj = next((
            c for c in self.df_state.vendor_obj['cargo_inventory']
            if c['cargo_id'] == self.values[0]
        ), None)

        await buy_cargo_menu(self.df_state)


async def buy_resource_menu(df_state: DFState, resource_type: str):
    if not df_state.vendor_obj:
        await discord_app.vendor_menus.vendor_menus.vendor_menu(df_state)
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
            f'### Cart: {self.cart_quantity:,.3f} Liters/meals | ${cart_price:,.0f}'
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
            label=f'Buy {self.cart_quantity:,.3f}L of {self.resource_type} | ${cart_price:,.0f}',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.buy_resource(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                resource_type=self.resource_type,
                quantity=self.cart_quantity,
                user_id=self.df_state.user_obj['user_id']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        cart_price = self.cart_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'## {self.df_state.vendor_obj['name']}',
            f'Purchased {self.cart_quantity:,.3f} Liters/meals of {self.resource_type} for ${cart_price:,.0f}'
        ])

        view = PostBuyView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


async def buy_cargo_menu(df_state: DFState):
    if not df_state.vendor_obj:
        await discord_app.vendor_menus.vendor_menus.vendor_menu(df_state)
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.buy_cargo(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                cargo_id=self.df_state.cargo_obj['cargo_id'],
                quantity=self.cart_quantity,
                user_id=self.df_state.user_obj['user_id']
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
            label = f'max ({self.button_quantity:+,})' if self.cargo_for_sale else f'max ({self.button_quantity:+,.3f})'
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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
    if not df_state.vendor_obj:
        await discord_app.vendor_menus.vendor_menus.vendor_menu(df_state)
    df_state.append_menu_to_back_stack(func=buy_vehicle_menu)  # Add this menu to the back stack

    part_list = []
    for part in df_state.vehicle_obj['parts']:
        if not part:  # If the part slot is empty
            part_list.append(f'- {part['slot'].replace('_', ' ').capitalize()}\n  - None')
            continue

        part_list.append(discord_app.cargo_menus.format_part(part, verbose=False))
    displayable_vehicle_parts = '\n'.join(part_list)

    vehicle_buy_confirm_embed = discord.Embed()
    vehicle_buy_confirm_embed = df_embed_author(vehicle_buy_confirm_embed, df_state)
    vehicle_buy_confirm_embed.description = '\n'.join([
        f'## {df_state.vendor_obj['name']}',
        f'### {df_state.vehicle_obj['name']} | ${df_state.vehicle_obj['value']:,.0f}',
        f'*{df_state.vehicle_obj['description']}*',
        '### Parts',
        displayable_vehicle_parts,
        f'### {df_state.vehicle_obj['name']} stats'
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.buy_vehicle(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                vehicle_id=self.df_state.vehicle_obj['vehicle_id'],
                user_id=self.df_state.user_obj['user_id']
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
                                 Structure: { 'resource_type': {'vendor_id': …, 'price': …, 'quantity': …} }
        total_top_up_cost (int): The total calculated cost for topping up resources.
    """
    def __init__(self, df_state: DFState, menu: callable, menu_args: dict | None = None, row: int = 1):
        """
        Initializes the TopUpButton.

        Calculates the optimal top-up plan based on resource needs, vendor prices,
        convoy capacity, and sets the button's label, state (enabled/disabled),
        and appearance accordingly.
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

        # Default button state
        button_label = 'Cannot top up: No vendors'
        button_disabled = True
        button_style = discord.ButtonStyle.blurple
        button_emoji = '🛒'
        
        # These will be populated by _calculate_top_up_plan
        self.resource_vendors = {}
        self.total_top_up_cost = 0
        
        # Calculate plan and determine button state
        has_vendors = self._has_vendors()
        if has_vendors:
            # Get the top-up plan and determine button state
            planned_resources, self.total_top_up_cost, self.resource_vendors, is_overload = self._calculate_top_up_plan()
            button_label, button_disabled, button_style, button_emoji = self._determine_button_state(
                planned_resources, self.total_top_up_cost, is_overload
            )
        else:
            button_label = 'No vendors available for top up'
            button_disabled = True

        # Final Button Setup
        super().__init__(
            style=button_style,
            label=button_label,
            disabled=button_disabled,
            custom_id='top_up_button',
            emoji=button_emoji,
            row=row
        )

    def _has_vendors(self) -> bool:
        """ Check if the settlement has vendors. """
        return bool(
            self.df_state.sett_obj and
            'vendors' in self.df_state.sett_obj and
            self.df_state.sett_obj['vendors']
        )

    def _get_resource_priority_order(self) -> list[str]:
        """
        Determines the order in which resources should be topped up, prioritizing those with the lowest fill percentage.
        """
        convoy = self.df_state.convoy_obj

        def fill_percentage(resource_type: str) -> float:
            current = convoy.get(resource_type, 0)
            maximum = max(convoy.get(f'max_{resource_type}', 1), 1)  # Avoid division by zero
            return current / maximum

        # Sort resource types by their fill percentage (ascending)
        return sorted(self.resource_types, key=fill_percentage)

    def _find_cheapest_vendor_for_resource(self, resource_type: str) -> dict | None:
        """ Finds the vendor offering the lowest price for a given resource type. """
        price_key = f'{resource_type}_price'
        valid_vendors = [
            v for v in self.df_state.sett_obj.get('vendors', [])
            if v.get(price_key) is not None
        ]

        if not valid_vendors:
            return None

        return min(valid_vendors, key=lambda v: v[price_key])

    def _calculate_top_up_plan(self) -> tuple[list[str], int, dict, bool]:
        """
        Calculates the optimal resource top-up plan.

        Returns:
            - list[str]: The resources included in the plan
            - int: Total cost
            - dict: Purchase details for each resource
            - bool: Whether this is an overload condition
        """
        convoy = self.df_state.convoy_obj
        weights = self.df_state.misc.get('resource_weights', {})
        
        # Track if we need resources but lack weight capacity
        is_weight_limited = convoy.get('total_remaining_capacity', 0) <= 0.001
        any_resource_needed = False
        
        remaining_weight = convoy.get('total_remaining_capacity', 0)
        sorted_resource_types = self._get_resource_priority_order()
        
        planned_resources = []
        total_cost = 0
        resource_purchase_details = {}
        
        # First check if we have a potential overload scenario
        for resource_type in self.resource_types:
            current_amount = convoy.get(resource_type, 0)
            max_capacity = convoy.get(f'max_{resource_type}', 0)
            if max_capacity - current_amount > 0.001:
                any_resource_needed = True
                break
        
        is_overload = any_resource_needed and is_weight_limited
        
        # If it's an overload condition, we still want to prepare the purchase plan
        # as if we had the weight capacity, to enable the button
        if is_overload:
            # Use a simulated weight capacity
            simulated_weight = 1000  # A large value to allow planning
            
            for resource_type in sorted_resource_types:
                current_amount = convoy.get(resource_type, 0)
                max_capacity = convoy.get(f'max_{resource_type}', 0)
                needed_quantity = max(0, max_capacity - current_amount)
                
                if needed_quantity <= 0:
                    continue
                
                cheapest_vendor = self._find_cheapest_vendor_for_resource(resource_type)
                if not cheapest_vendor:
                    continue
                
                price = cheapest_vendor[f'{resource_type}_price']
                
                planned_resources.append(resource_type)
                resource_purchase_details[resource_type] = {
                    'vendor_id': cheapest_vendor['vendor_id'],
                    'price': price,
                    'quantity': needed_quantity
                }
                
                # Calculate cost for informational purposes
                total_cost += int(needed_quantity * price)
            
            return planned_resources, total_cost, resource_purchase_details, is_overload
        
        # Normal calculation path when we have weight capacity
        for resource_type in sorted_resource_types:
            if remaining_weight <= 0:
                break
                
            current_amount = convoy.get(resource_type, 0)
            max_capacity = convoy.get(f'max_{resource_type}', 0)
            needed_quantity = max(0, max_capacity - current_amount)
            
            if needed_quantity <= 0:
                continue
                
            cheapest_vendor = self._find_cheapest_vendor_for_resource(resource_type)
            if not cheapest_vendor:
                continue
                
            weight_per_unit = max(weights.get(resource_type, 1.0), 0.001)
            max_units_by_weight = math.floor(remaining_weight / weight_per_unit)
            
            actual_quantity = min(needed_quantity, max_units_by_weight)
            if actual_quantity <= 0:
                continue
                
            price = cheapest_vendor[f'{resource_type}_price']
            cost = actual_quantity * price
            
            planned_resources.append(resource_type)
            resource_purchase_details[resource_type] = {
                'vendor_id': cheapest_vendor['vendor_id'],
                'price': price,
                'quantity': actual_quantity
            }
            
            total_cost += int(cost)
            remaining_weight -= actual_quantity * weight_per_unit
            
        return planned_resources, total_cost, resource_purchase_details, False

    def _determine_button_state(
            self,
            planned_resources: list[str],
            total_cost: int,
            is_overload: bool
    ) -> tuple[str, bool, discord.ButtonStyle, str]:
        """ Determines the button's label and state based on the top-up plan. """
        convoy = self.df_state.convoy_obj
        can_afford = total_cost <= convoy.get('money', 0)
        
        # Default style and emoji
        style = discord.ButtonStyle.blurple
        emoji = '🛒'
        
        if is_overload and planned_resources:
            # Overload condition - user can try but will likely get an error
            label = f'Top up {', '.join(planned_resources)} (Overload!) | ${total_cost:,.0f}'
            style = discord.ButtonStyle.red
            emoji = '⚠️'
            disabled = False  # Enable the button to let them try
        elif planned_resources:
            # Normal case with resources to purchase
            label = f'Top up {', '.join(planned_resources)} | ${total_cost:,.0f}'
            disabled = not can_afford
            if disabled:
                label += ' (Insufficient Funds)'
        else:
            # No resources to purchase
            label = 'Convoy is already topped up'
            disabled = True
            
        return label, disabled, style, emoji

    async def callback(self, interaction: discord.Interaction):
        """ Executed when the button is clicked. Performs the resource purchases and updates the menu. """
        # Validation
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction
        
        # Defer response immediately
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        # Verify there's something to buy
        if not self.resource_vendors:
            await interaction.followup.send('Nothing to top up or purchase plan invalid.', ephemeral=True)
            return
            
        try:
            topped_up_details = []
            
            # Execute purchases
            for resource_type, purchase_info in self.resource_vendors.items():
                vendor_id = purchase_info['vendor_id']
                quantity = purchase_info['quantity']
                price = purchase_info['price']
                
                if quantity <= 0:
                    continue
                    
                # API call to buy the resource
                updated_convoy_obj = await api_calls.buy_resource(
                    vendor_id=vendor_id,
                    convoy_id=self.df_state.convoy_obj['convoy_id'],
                    resource_type=resource_type,
                    quantity=quantity,
                    user_id=self.df_state.user_obj['user_id']
                )
                
                # Update state
                self.df_state.convoy_obj = updated_convoy_obj
                
                # Add to receipt
                meta = self.resource_metadata.get(resource_type, {'emoji': '📦', 'unit': 'unit'})
                topped_up_details.append(
                    f'- {meta['emoji']} {quantity:.0f} {resource_type.capitalize()} for '
                    f'${price:,.0f} per {meta['unit']}'
                )
                
            # Success feedback
            receipt_embed = discord.Embed(
                color=discord.Color.green(),
                title='Top-Up Successful',
                description='\n'.join([
                    f'### Topped up resources for ${self.total_top_up_cost:,.0f}',
                    *topped_up_details
                ])
            )
            
            # Update menu
            await self.menu(
                df_state=self.df_state,
                follow_on_embeds=[receipt_embed],
                **self.menu_args
            )
            
        except RuntimeError as e:
            # Error handling
            error_embed = discord.Embed(
                color=discord.Color.red(),
                title='Top-Up Failed',
                description=f'An error occurred: {e}'
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            
        except Exception as e:
            print
            await interaction.followup.send('An unexpected error occurred. Please try again later.', ephemeral=True)
