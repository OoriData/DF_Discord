# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import math

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import (
    api_calls, handle_timeout, df_embed_author, add_tutorial_embed, validate_interaction, get_user_metadata,
    get_vehicle_emoji, get_cargo_emoji, create_paginated_select_options, split_description_into_embeds
)
from discord_app.map_rendering import add_map_to_embed
import                                discord_app.vendor_menus.vendor_menus
import                                discord_app.vendor_menus.buy_menus
import                                discord_app.nav_menus
import                                discord_app.main_menu_menus
import                                discord_app.convoy_menus
from discord_app.vendor_menus  import vehicles_md
from discord_app.df_state      import DFState


async def warehouse_menu(df_state: DFState, edit: bool = True):
    df_state.append_menu_to_back_stack(
        func=warehouse_menu, args={'edit': edit}
    )  # Add this menu to the back stack

    if df_state.warehouse_obj:
        df_state.warehouse_obj = await api_calls.get_warehouse(df_state.warehouse_obj['warehouse_id'])

        await warehoused(df_state, edit)
    else:
        await warehouseless(df_state, edit)

async def warehoused(df_state: DFState, edit: bool):
    header_embed = discord.Embed(description=f'# Warehouse in {df_state.sett_obj['name']}')
    header_embed = df_embed_author(header_embed, df_state)
    
    embeds = [header_embed]

    if df_state.warehouse_obj['cargo_storage']:
        cargo_md = await warehouse_cargo_md(df_state.warehouse_obj)
        split_description_into_embeds(
            content_string=cargo_md[:5000],
            embed_title='## Cargo',
            target_embeds_list=embeds
        )
    if df_state.warehouse_obj['vehicle_storage']:
        vehicles_md = await warehouse_vehicles_md(df_state.warehouse_obj)
        split_description_into_embeds(
            content_string=vehicles_md[:5000],
            embed_title='## Vehicles',
            target_embeds_list=embeds
        )

    footer_embed = discord.Embed()
    cargo_volume = sum(cargo.get('volume', 0) for cargo in df_state.warehouse_obj.get('cargo_storage', []))

    if df_state.user_obj['metadata']['mobile']:
        footer_embed.description = '\n' + '\n'.join([
            '',
            f'Cargo Storage 📦: **{cargo_volume:,.0f}** / {df_state.warehouse_obj['cargo_storage_capacity']:,.0f}L',
            f'Vehicle Storage 🅿️: **{len(df_state.warehouse_obj['vehicle_storage'])}** / {df_state.warehouse_obj['vehicle_storage_capacity']:,}'
        ])
    else:
        footer_embed.add_field(name='Cargo Storage 📦', value=f'**{cargo_volume:,}**\n/{df_state.warehouse_obj['cargo_storage_capacity']:,} liters')
        footer_embed.add_field(name='Vehicle Storage 🅿️', value=f'**{len(df_state.warehouse_obj['vehicle_storage'])}**\n/{df_state.warehouse_obj['vehicle_storage_capacity']:,}')
    embeds.append(footer_embed)

    view = WarehouseView(df_state)

    if edit:
        await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embeds=embeds, view=view)

async def warehouse_vehicles_md(warehouse_obj, verbose: bool = False) -> str:
    vehicle_list = []
    for vehicle in warehouse_obj['vehicle_storage']:
        vehicle_str = f'- {vehicle['name']} | *${vehicle['value']:,}*'

        if verbose:
            vehicle_str += '\n' + '\n'.join([
                f'  - Efficiency 🌿: **{vehicle['efficiency']:.0f}** / 100',
                f'  - Top Speed 🚀: **{vehicle['top_speed']:.0f}** / 100',
                f'  - Offroad Capability 🥾: **{vehicle['offroad_capability']:.0f}** / 100',
                f'  - Volume Capacity 📦: **{vehicle['cargo_capacity']:.0f}**L',
                f'  - Weight Capacity 🏋: **{vehicle['weight_capacity']:.0f}**kg'
            ])

        vehicle_list.append(vehicle_str)
    return '\n'.join(vehicle_list) if vehicle_list else '- None'

async def warehouse_cargo_md(warehouse_obj, verbose: bool = False) -> str:
    cargo_list = []
    for cargo in warehouse_obj['cargo_storage']:
        cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *${cargo['unit_price']:,.0f} each*'

        if verbose:
            for resource in ['fuel', 'water', 'food']:
                if cargo[resource]:
                    unit = ' meals' if resource == 'food' else 'L'
                    cargo_str += f'\n  - {resource.capitalize()}: {cargo[resource]:,.0f}{unit}'

            if cargo['recipient']:
                cargo['recipient_vendor'] = await api_calls.get_vendor(vendor_id=cargo['recipient'])
                cargo_str += f'\n  - Deliver to *{cargo['recipient_vendor']['name']}* | ***${cargo['unit_delivery_reward']:,.0f}*** *each*'
                margin = min(round((cargo['unit_delivery_reward'] / cargo['unit_price']) / 2), 24)  # limit emojis to 24
                cargo_str += f'\n    - Profit margin: {'💵 ' * margin}'

        cargo_list.append(cargo_str)
    return '\n'.join(cargo_list) if cargo_list else '- None'

async def warehouse_storage_md(warehouse_obj, verbose: bool = False) -> str:
    displayable_vehicles = await warehouse_vehicles_md(warehouse_obj, verbose)
    displayable_cargo = await warehouse_cargo_md(warehouse_obj, verbose)

    return '\n'.join([
        '### Cargo',
        f'{displayable_cargo}',
        '',
        '### Vehicles',
        f'{displayable_vehicles}'
    ])

def _calculate_warehouse_current_volume(warehouse_obj: dict) -> float:
    """ Helper to calculate current total volume of cargo in warehouse. """
    return sum(cargo.get('volume', 0) for cargo in warehouse_obj.get('cargo_storage', []))

def _get_cargo_by_class_id(item_source: list[dict], class_id: str) -> list[dict]:
    """ Helper to filter cargo items by class_id. """
    return [cargo for cargo in item_source if cargo.get('class_id') == class_id and cargo.get('quantity', 0) > 0]

class WarehouseView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        # Ensure warehouse_obj is up-to-date for capacity checks if coming from a previous menu
        # This is particularly important if an operation just changed its state.
        # However, warehouse_menu already re-fetches it.

        if df_state.convoy_obj:
            discord_app.nav_menus.add_nav_buttons(self, self.df_state)

            self.add_item(ExpandCargoButton(self.df_state))
            self.add_item(ExpandVehiclesButton(self.df_state))
            self.add_item(StoreCargoButton(self.df_state))
            self.add_item(RetrieveCargoButton(self.df_state))
            self.add_item(StoreVehiclesButton(self.df_state))
            self.add_item(RetrieveVehicleButton(self.df_state))

        else:  # Presumably we got here from the main menu, so use that button as a "back button"
            self.add_item(discord_app.nav_menus.NavMainMenuButton(df_state))

        self.add_item(SpawnButton(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class ExpandCargoButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Expand cargo storage',
            custom_id='expand_cargo_button',
            emoji='📦',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await expand_cargo_menu(self.df_state)

class ExpandVehiclesButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Expand vehicle storage',
            custom_id='expand_vehicles_button',
            emoji='🅿️',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await expand_vehicles_menu(self.df_state)

class StoreCargoButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Store cargo',
            disabled=False if self.df_state.convoy_obj['all_cargo'] else True,
            custom_id='store_cargo_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await store_cargo_menu(self.df_state)

class RetrieveCargoButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Retrieve cargo',
            disabled=False if self.df_state.warehouse_obj['cargo_storage'] else True,
            custom_id='retrieve_cargo_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await retrieve_cargo_menu(self.df_state)

class StoreVehiclesButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=3):
        self.df_state = df_state

        disabled = True
        if (
            self.df_state.convoy_obj['vehicles']
            and (len(self.df_state.warehouse_obj['vehicle_storage']) < self.df_state.warehouse_obj['vehicle_storage_capacity'])
        ):
            disabled = False

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Store vehicle',
            disabled=disabled,
            custom_id='store_vehicles_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await store_vehicle_menu(self.df_state)

class RetrieveVehicleButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=3):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Retrieve vehicle',
            disabled=False if self.df_state.warehouse_obj['vehicle_storage'] else True,
            custom_id='retrieve_vehicles_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await retrieve_vehicle_menu(self.df_state)

class SpawnButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=4):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.green,
            label='Initialize new convoy',
            disabled=False if self.df_state.warehouse_obj['vehicle_storage'] else True,
            custom_id='spawn_button',
            emoji='➕',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await spawn_convoy_menu(self.df_state)


async def expand_cargo_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=expand_cargo_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    embed.description = '**Cargo Storage Expansion**\n\n'
    embed.description += f'Current capacity: {df_state.warehouse_obj['cargo_storage_capacity']:,} liters\n'
    embed.description += f'Cost to expand: ${df_state.warehouse_obj['expansion_price']:,}'

    embeds = [embed]
    view = ExpandCargoView(df_state)
    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class ExpandCargoView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(ExpandCargoButtonConfirm(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class ExpandCargoButtonConfirm(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.green,
            label='Expand cargo storage',
            custom_id='expand_cargo_confirm_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.warehouse_obj = await api_calls.expand_warehouse(
                warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                user_id=self.df_state.user_obj['user_id'],
                cargo_capacity_upgrade=1
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        await warehouse_menu(self.df_state)


async def expand_vehicles_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=expand_vehicles_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    embed.description = '**Vehicle Storage Expansion**\n\n'
    embed.description += f'Current capacity: {df_state.warehouse_obj['vehicle_storage_capacity']:,} vehicles\n'
    embed.description += f'Cost to expand: ${df_state.warehouse_obj['expansion_price']:,}'

    embeds = [embed]
    view = ExpandVehiclesView(df_state)
    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class ExpandVehiclesView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(ExpandVehiclesButtonConfirm(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class ExpandVehiclesButtonConfirm(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.green,
            label='Expand vehicle storage',
            custom_id='expand_vehicles_confirm_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.warehouse_obj = await api_calls.expand_warehouse(
                warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                user_id=self.df_state.user_obj['user_id'],
                vehicle_capacity_upgrade=1
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        await warehouse_menu(self.df_state)


async def store_cargo_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=store_cargo_menu)  # Add this menu to the back stack

    cargo_volume = sum(cargo['volume'] * cargo['quantity'] for cargo in df_state.warehouse_obj['cargo_storage'])  # TODO: Think about implementing this stat in the backend

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = f'# Warehouse in {df_state.sett_obj['name']}'
    embed.description += f'\nCargo Storage 📦: **{cargo_volume:,}** / {df_state.warehouse_obj['cargo_storage_capacity']:,}L'

    embeds = [embed]

    view = StoreCargoView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class StoreCargoView(discord.ui.View):
    def __init__(self, df_state: DFState, store_quantity: int=1):
        self.df_state = df_state
        self.store_quantity = store_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        # self.add_item(CargoQuantityStoreButton(self.df_state, store_quantity=self.store_quantity, button_quantity=-10))
        self.add_item(StoreCargoSelect(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class StoreCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state
        placeholder = 'Cargo which can be stored'
        disabled = False

        vendor_mapping = {}

        # Build vendor mapping
        for r in self.df_state.map_obj['tiles']:
            for tile in r:
                for settlement in tile['settlements']:
                    for vendor in settlement['vendors']:
                        vendor_mapping[vendor['vendor_id']] = vendor['name']
        options = []
        for vehicle in df_state.convoy_obj['vehicles']:
            for cargo in vehicle['cargo']:
                if not cargo['intrinsic_part_id']:
                    # Get vendor name or fallback if None
                    vendor_name = f'| {vendor_mapping.get(cargo['recipient'], '')}'

                    options.append(discord.SelectOption(
                        label=f'{cargo['name']} | {vehicle['name']} {vendor_name}',
                        value=cargo['cargo_id'],
                        emoji=get_cargo_emoji(cargo)
                    ))

        if not options:
            placeholder = 'Convoy has no cargo which can be stored'
            disabled = True
            options = [discord.SelectOption(label='None', value='None')]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options[:25],
            disabled=disabled,
            custom_id='store_cargo_select',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        self.df_state.cargo_obj = next((
            c for c in self.df_state.convoy_obj['all_cargo']
            if c['cargo_id'] == self.values[0]
        ), None)

        await store_cargo_quantity_menu(self.df_state)


async def store_cargo_quantity_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=store_cargo_quantity_menu)  # Add this menu to the back stack

    embed = StoreCargoQuantityEmbed(df_state)
    embeds = [embed]
    view = StoreCargoQuantityView(df_state)
    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class StoreCargoQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, store_quantity: int=1):
        self.df_state = df_state
        self.store_quantity = store_quantity
        super().__init__()

        # self = df_embed_author(self, self.df_state)

        cart_unit_volume = self.df_state.cargo_obj.get('unit_volume', 0)
        store_cart_volume = self.store_quantity * cart_unit_volume

        self.description = '\n'.join([
            f'# Warehouse in {df_state.sett_obj['name']}',
            f'### Storing: {self.store_quantity} {self.df_state.cargo_obj['name']}(s)',
            f'*{self.df_state.cargo_obj.get('base_desc', 'No description.')}*',
            f'- Cart volume: **{store_cart_volume:,.1f}L**'
        ])

        if get_user_metadata(df_state, 'mobile'):
            self.description += '\n' + '\n'.join([
                f'- Convoy inventory: {self.df_state.cargo_obj['quantity']}',
                f'- Volume (per unit): {self.df_state.cargo_obj['unit_volume']}L',
                f'- Dry Weight (per unit): {self.df_state.cargo_obj['unit_dry_weight']}kg'
            ])  # TODO: Add warehouse capacity display here
        else:
            self.add_field(name='Inventory', value=self.df_state.cargo_obj['quantity'])
            self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['unit_volume']} liter(s)')
            self.add_field(name='Dry Weight (per unit)', value=f'{self.df_state.cargo_obj['unit_dry_weight']} kilogram(s)')
            # Add warehouse capacity display
            current_warehouse_volume = _calculate_warehouse_current_volume(self.df_state.warehouse_obj)
            warehouse_capacity = self.df_state.warehouse_obj['cargo_storage_capacity']
            self.add_field(name='Warehouse Free Space', value=f'{warehouse_capacity - current_warehouse_volume:,.0f}L / {warehouse_capacity:,.0f}L')

class StoreCargoQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, store_quantity: int=1):
        self.df_state = df_state
        self.store_quantity = store_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(CargoStoreQuantityButton(self.df_state, store_quantity=self.store_quantity, button_quantity=-10))
        self.add_item(CargoStoreQuantityButton(self.df_state, store_quantity=self.store_quantity, button_quantity=-1))
        self.add_item(CargoStoreQuantityButton(self.df_state, store_quantity=self.store_quantity, button_quantity=1))
        self.add_item(CargoStoreQuantityButton(self.df_state, store_quantity=self.store_quantity, button_quantity=10))
        self.add_item(CargoStoreQuantityButton(self.df_state, store_quantity=self.store_quantity, button_quantity='max'))

        self.add_item(CargoConfirmStoreButton(self.df_state, store_quantity=self.store_quantity, row=2))
        self.add_item(StoreAllCargoButton(self.df_state, row=2))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class CargoStoreQuantityButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            store_quantity: int,
            button_quantity: int | str,
            row: int = 1
    ):
        self.df_state = df_state
        self.store_quantity = store_quantity

        # Max that can be stored from this specific stack in convoy
        max_from_convoy_stack = self.df_state.cargo_obj['quantity']

        # Max that fits in warehouse by volume
        current_warehouse_volume = _calculate_warehouse_current_volume(self.df_state.warehouse_obj)
        warehouse_free_volume = self.df_state.warehouse_obj['cargo_storage_capacity'] - current_warehouse_volume
        unit_volume = self.df_state.cargo_obj.get('unit_volume', 1)  # Avoid division by zero if unit_volume is 0
        max_fits_in_warehouse = math.floor(warehouse_free_volume / unit_volume) if unit_volume > 0 else float('inf')

        effective_max_store = min(max_from_convoy_stack, max_fits_in_warehouse)

        if button_quantity == 'max':  # Handle "max" button logic
            self.button_quantity = max(0, effective_max_store - self.store_quantity)
            label = f'max ({self.button_quantity:+,})'
        else:
            self.button_quantity = int(button_quantity)
            label = f'{self.button_quantity:+,}'

        resultant_quantity = self.store_quantity + self.button_quantity

        disabled = self.should_disable_button(  # Determine if button should be disabled
            resultant_quantity, max_from_convoy_stack, warehouse_free_volume
        )

        if self.button_quantity == 0:  # Disable the button if the "max" button would add 0 quantity
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
            custom_id=f'{button_quantity}_store_button',
            row=row
        )

    def should_disable_button(self, resultant_quantity: int, max_from_convoy_stack: int, warehouse_free_volume: float):
        # Disable if the resulting quantity is out of valid bounds
        if resultant_quantity <= 0:
            return True

        # Cannot store more than the convoy has of this item
        if resultant_quantity > max_from_convoy_stack:
            return True

        # Cannot store more than fits in the warehouse
        unit_volume = self.df_state.cargo_obj.get('unit_volume', 0)
        if (resultant_quantity * unit_volume) > warehouse_free_volume + 0.001:  # Add epsilon for float comparisons
            return True

        return False

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return

        self.store_quantity += self.button_quantity  # Update sale quantity

        embed = StoreCargoQuantityEmbed(self.df_state, self.store_quantity)
        view = StoreCargoQuantityView(self.df_state, self.store_quantity)
        await interaction.response.edit_message(embed=embed, view=view)

class CargoConfirmStoreButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            store_quantity: int,
            row: int=1
    ):
        self.df_state = df_state
        self.store_quantity = store_quantity

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Store {self.store_quantity} {self.df_state.cargo_obj['name']}(s)',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.store_cargo_in_warehouse(
                warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                cargo_id=self.df_state.cargo_obj['cargo_id'],
                quantity=self.store_quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        # Re-fetch user_obj to get updated convoy list and money
        self.df_state.user_obj = await api_calls.get_user(self.df_state.user_obj['user_id'])
        # Re-fetch convoy_obj if it still exists
        self.df_state.convoy_obj = next((c for c in self.df_state.user_obj['convoys'] if c['convoy_id'] == self.df_state.convoy_obj['convoy_id']), None)
        # Re-fetch warehouse_obj for its updated inventory
        self.df_state.warehouse_obj = await api_calls.get_warehouse(self.df_state.warehouse_obj['warehouse_id'])

        await warehouse_menu(self.df_state)

class StoreAllCargoButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int = 1):
        self.df_state = df_state
        self.sell_list = []
        self.total_quantity_to_store = 0
        self.total_volume_to_store = 0

        disabled = True
        label = 'Store all (N/A)'

        if self.df_state.cargo_obj and self.df_state.convoy_obj:
            cargo_class_id = self.df_state.cargo_obj.get('class_id')
            self.sell_list = _get_cargo_by_class_id(self.df_state.convoy_obj.get('all_cargo', []), cargo_class_id)

            if self.sell_list:
                self.total_quantity_to_store = sum(c['quantity'] for c in self.sell_list)
                self.total_volume_to_store = sum(c['quantity'] * c['unit_volume'] for c in self.sell_list)

                current_warehouse_volume = _calculate_warehouse_current_volume(self.df_state.warehouse_obj)
                warehouse_free_volume = self.df_state.warehouse_obj['cargo_storage_capacity'] - current_warehouse_volume

                if self.total_quantity_to_store > 0 and self.total_volume_to_store <= warehouse_free_volume:
                    disabled = False
                label = f'Store all {self.total_quantity_to_store} {self.df_state.cargo_obj['name']}(s)'
            else:
                label = f'No {self.df_state.cargo_obj['name']} to store all'

        super().__init__(style=discord.ButtonStyle.red, label=label, disabled=disabled, custom_id='store_all_cargo_button', row=row)

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        if not self.sell_list or self.total_quantity_to_store == 0:
            await interaction.response.send_message("Nothing to store.", ephemeral=True)
            return

        for cargo_stack in self.sell_list:
            try:
                await api_calls.store_cargo_in_warehouse(
                    warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                    convoy_id=self.df_state.convoy_obj['convoy_id'],
                    cargo_id=cargo_stack['cargo_id'],
                    quantity=cargo_stack['quantity']  # Store the whole stack
                )
            except RuntimeError as e:
                await interaction.response.send_message(content=f"Error storing {cargo_stack['name']}: {e}", ephemeral=True)
                # Potentially stop or continue, for now, we continue

        # Re-fetch user_obj to get updated convoy list and money
        self.df_state.user_obj = await api_calls.get_user(self.df_state.user_obj['user_id'])
        # Re-fetch convoy_obj if it still exists
        self.df_state.convoy_obj = next((c for c in self.df_state.user_obj['convoys'] if c['convoy_id'] == self.df_state.convoy_obj['convoy_id']), None)
        # Re-fetch warehouse_obj for its updated inventory
        self.df_state.warehouse_obj = await api_calls.get_warehouse(self.df_state.warehouse_obj['warehouse_id'])
        await warehouse_menu(self.df_state)


async def retrieve_cargo_menu(df_state: DFState, page: int = 0):
    df_state.append_menu_to_back_stack(
        func=retrieve_cargo_menu, args={'page': page}
    )  # Add this menu to the back stack

    header_embed = discord.Embed(description=f'# Warehouse in {df_state.sett_obj['name']}')
    header_embed = df_embed_author(header_embed, df_state)

    embeds = [header_embed]

    split_description_into_embeds(
        content_string=await warehouse_cargo_md(df_state.warehouse_obj),
        target_embeds_list=embeds
    )

    cargo_volume = _calculate_warehouse_current_volume(df_state.warehouse_obj)
    footer_embed = discord.Embed(description=f'\nCargo Storage 📦: **{cargo_volume:,.0f}** / {df_state.warehouse_obj['cargo_storage_capacity']:,}L')
    embeds.append(footer_embed)

    view = RetrieveCargoView(df_state, page=page)
    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class RetrieveCargoView(discord.ui.View):
    def __init__(self, df_state: DFState, page: int = 0, retrieve_quantity: int = 1):
        self.df_state = df_state
        self.page = page
        self.retrieve_quantity = retrieve_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(RetrieveCargoSelect(self.df_state, page=self.page))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class RetrieveCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, page: int = 0, row: int = 1):
        self.df_state = df_state
        self.page = page

        placeholder = 'Cargo which can be retrieved'
        disabled = False

        vendor_mapping = {}
        for r in self.df_state.map_obj['tiles']:  # Build vendor mapping
            for tile in r:
                for settlement in tile['settlements']:
                    for vendor in settlement['vendors']:
                        vendor_mapping[vendor['vendor_id']] = vendor['name']

        all_cargo_options = []
        for cargo in df_state.warehouse_obj['cargo_storage']:
            vendor_name = f'| {vendor_mapping.get(cargo['recipient'], '')}'

            all_cargo_options.append(discord.SelectOption(
                label=f'{cargo['name']} {vendor_name}',
                value=cargo['cargo_id'],
                emoji=get_cargo_emoji(cargo)
            ))

        sorted_options = sorted(all_cargo_options, key=lambda opt: opt.label.lower())

        if not all_cargo_options:
            placeholder = 'Warehouse has no cargo which can be retrieved'
            disabled = True
            options = [discord.SelectOption(label='None', value='None')]
        elif len(all_cargo_options) > 25:  # More than 25 options
            options = create_paginated_select_options(sorted_options, self.page)  # Paginate
        else:
            options = sorted_options

        super().__init__(
            placeholder=f'{placeholder} (Page {self.page + 1})',
            options=options,
            disabled=disabled,
            custom_id='retrieve_cargo_select',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        if self.values[0] in ('prev_page', 'next_page'):
            self.page += -1 if self.values[0] == 'prev_page' else 1
            await retrieve_cargo_menu(self.df_state, page=self.page)
            return

        # Defaults to none if cargo item selected matches a cargo item in the convoy's inventory
        self.df_state.cargo_obj = next((
            c for c in self.df_state.warehouse_obj['cargo_storage']
            if c['cargo_id'] == self.values[0]
        ), None)

        await retrieve_cargo_quantity_menu(self.df_state)


async def retrieve_cargo_quantity_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=retrieve_cargo_quantity_menu)  # Add this menu to the back stack

    embed = CargoRetrieveQuantityEmbed(df_state)

    embeds = [embed]

    view = CargoRetrieveQuantityView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class CargoRetrieveQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, retrieve_quantity: int=1):
        self.df_state = df_state
        self.retrieve_quantity = retrieve_quantity
        super().__init__()

        # self = df_embed_author(self, self.df_state)

        cart_unit_volume = self.df_state.cargo_obj.get('unit_volume', 0)
        cart_unit_weight = self.df_state.cargo_obj.get('unit_weight', 0)
        retrieve_cart_volume = self.retrieve_quantity * cart_unit_volume
        retrieve_cart_weight = self.retrieve_quantity * cart_unit_weight

        self.description = '\n'.join([
            f'# Warehouse in {df_state.sett_obj['name']}',
            f'### Retrieving: {self.retrieve_quantity} {self.df_state.cargo_obj['name']}(s)',
            f'*{self.df_state.cargo_obj.get('base_desc', 'No description.')}*',
            f'- Cart volume: **{retrieve_cart_volume:,.1f}L**',
            f'  - {self.df_state.convoy_obj['total_free_space']:,.0f}L free space in convoy',
            f'- Cart weight: **{retrieve_cart_weight:,.1f}kg**',
            f'  - {self.df_state.convoy_obj['total_remaining_capacity']:,.0f}kg weight capacity in convoy',
        ])

        if get_user_metadata(df_state, 'mobile'):
            self.description += '\n' + '\n'.join([
                f'- Warehouse inventory: {self.df_state.cargo_obj['quantity']}',
                f'- Volume (per unit): {self.df_state.cargo_obj['unit_volume']}L',
                f'- Dry Weight (per unit): {self.df_state.cargo_obj['unit_dry_weight']}kg'
            ])
        else:
            self.add_field(name='Warehouse Inventory', value=self.df_state.cargo_obj['quantity'])
            self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['unit_volume']} liter(s)')
            self.add_field(name='Dry Weight (per unit)', value=f'{self.df_state.cargo_obj['unit_dry_weight']} kilogram(s)')
            # Add convoy capacity display
            self.add_field(name='Convoy Free Space', value=f'{self.df_state.convoy_obj['total_free_space']:,.0f}L')
            self.add_field(name='Convoy Rem. Capacity', value=f'{self.df_state.convoy_obj['total_remaining_capacity']:,.0f}kg')

class CargoRetrieveQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, retrieve_quantity: int=1):
        self.df_state = df_state
        self.retrieve_quantity = retrieve_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(CargoRetrieveQuantityButton(self.df_state, retrieve_quantity=self.retrieve_quantity, button_quantity=-10))
        self.add_item(CargoRetrieveQuantityButton(self.df_state, retrieve_quantity=self.retrieve_quantity, button_quantity=-1))
        self.add_item(CargoRetrieveQuantityButton(self.df_state, retrieve_quantity=self.retrieve_quantity, button_quantity=1))
        self.add_item(CargoRetrieveQuantityButton(self.df_state, retrieve_quantity=self.retrieve_quantity, button_quantity=10))
        self.add_item(CargoRetrieveQuantityButton(self.df_state, retrieve_quantity=self.retrieve_quantity, button_quantity='max'))

        self.add_item(CargoConfirmRetrieveButton(self.df_state, retrieve_quantity=self.retrieve_quantity, row=2))
        self.add_item(RetrieveAllCargoButton(self.df_state, row=2))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class CargoRetrieveQuantityButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            retrieve_quantity: int,
            button_quantity: int | str,
            row: int = 1
    ):
        self.df_state = df_state
        self.retrieve_quantity = retrieve_quantity

        # Max that can be retrieved from this specific stack in warehouse
        max_from_warehouse_stack = self.df_state.cargo_obj['quantity']

        # Max that fits in convoy
        unit_volume = self.df_state.cargo_obj.get('unit_volume', 1)  # Avoid division by zero
        unit_weight = self.df_state.cargo_obj.get('unit_weight', 1)  # Avoid division by zero

        max_fits_in_convoy_by_volume = math.floor(self.df_state.convoy_obj['total_free_space'] / unit_volume) if unit_volume > 0 else float('inf')
        max_fits_in_convoy_by_weight = math.floor(self.df_state.convoy_obj['total_remaining_capacity'] / unit_weight) if unit_weight > 0 else float('inf')

        max_convoy_can_take = min(max_fits_in_convoy_by_volume, max_fits_in_convoy_by_weight)

        effective_max_retrieve = min(max_from_warehouse_stack, max_convoy_can_take)

        if button_quantity == 'max':  # Handle "max" button logic
            self.button_quantity = max(0, effective_max_retrieve - self.retrieve_quantity)
            label = f'max ({self.button_quantity:+,})'

        else:
            self.button_quantity = int(button_quantity)
            label = f'{self.button_quantity:+,}'

        resultant_quantity = self.retrieve_quantity + self.button_quantity

        disabled = self.should_disable_button(  # Determine if button should be disabled
            resultant_quantity,
            max_from_warehouse_stack,
            self.df_state.convoy_obj['total_free_space'],
            self.df_state.convoy_obj['total_remaining_capacity']
        )

        if self.button_quantity == 0:  # Disable the button if the "max" button would add 0 quantity
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
            custom_id=f'{button_quantity}_retrieve_button',
            row=row
        )

    def should_disable_button(self, resultant_quantity: int, max_from_warehouse_stack: int, convoy_free_volume: float, convoy_free_weight: float):
        # Disable if the resulting quantity is out of valid bounds
        if resultant_quantity <= 0:
            return True

        # Cannot retrieve more than the warehouse has of this item
        if resultant_quantity > max_from_warehouse_stack:
            return True

        # Cannot retrieve more than fits in the convoy
        unit_volume = self.df_state.cargo_obj.get('unit_volume', 0)
        unit_weight = self.df_state.cargo_obj.get('unit_weight', 0)

        if (resultant_quantity * unit_volume) > convoy_free_volume + 0.001:  # Epsilon for float
            return True
        if (resultant_quantity * unit_weight) > convoy_free_weight + 0.001:  # Epsilon for float
            return True

        return False

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        self.retrieve_quantity += self.button_quantity  # Update cart quantity

        embed = CargoRetrieveQuantityEmbed(self.df_state, self.retrieve_quantity)
        view = CargoRetrieveQuantityView(self.df_state, self.retrieve_quantity)

        embeds = [embed]
        embeds = add_tutorial_embed(embeds, self.df_state)

        await interaction.response.edit_message(embeds=embeds, view=view)

class CargoConfirmRetrieveButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            retrieve_quantity: int,
            row: int=1
    ):
        self.df_state = df_state
        self.retrieve_quantity = retrieve_quantity

        label = f'Retrieve {self.retrieve_quantity} {self.df_state.cargo_obj['name']}(s)'
        disabled = False

        super().__init__(
            style=discord.ButtonStyle.green,
            label=label,
            disabled=disabled,
            custom_id='confirm_retrieve_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.retrieve_cargo_from_warehouse(
                warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                cargo_id=self.df_state.cargo_obj['cargo_id'],
                quantity=self.retrieve_quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        await warehouse_menu(self.df_state)

        self.df_state.user_obj = await api_calls.get_user(self.df_state.user_obj['user_id'])
        # Re-fetch convoy_obj if it still exists
        self.df_state.convoy_obj = next((c for c in self.df_state.user_obj['convoys'] if c['convoy_id'] == self.df_state.convoy_obj['convoy_id']), None)
        # Re-fetch warehouse_obj for its updated inventory
        self.df_state.warehouse_obj = await api_calls.get_warehouse(self.df_state.warehouse_obj['warehouse_id'])

        await warehouse_menu(self.df_state)

class RetrieveAllCargoButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int = 1):
        self.df_state = df_state
        self.retrieve_list = []
        self.total_quantity_to_retrieve = 0
        self.total_volume_to_retrieve = 0
        self.total_weight_to_retrieve = 0

        disabled = True
        label = 'Retrieve all (N/A)'

        if self.df_state.cargo_obj and self.df_state.convoy_obj:
            cargo_class_id = self.df_state.cargo_obj.get('class_id')
            self.retrieve_list = _get_cargo_by_class_id(self.df_state.warehouse_obj.get('cargo_storage', []), cargo_class_id)

            if self.retrieve_list:
                self.total_quantity_to_retrieve = sum(c['quantity'] for c in self.retrieve_list)
                self.total_volume_to_retrieve = sum(c['quantity'] * c['unit_volume'] for c in self.retrieve_list)
                self.total_weight_to_retrieve = sum(c['quantity'] * c['unit_weight'] for c in self.retrieve_list)

                convoy_free_volume = self.df_state.convoy_obj['total_free_space']
                convoy_free_weight = self.df_state.convoy_obj['total_remaining_capacity']

                if (self.total_quantity_to_retrieve > 0 and
                        self.total_volume_to_retrieve <= convoy_free_volume and
                        self.total_weight_to_retrieve <= convoy_free_weight):
                    disabled = False
                label = f'Retrieve all {self.total_quantity_to_retrieve} {self.df_state.cargo_obj['name']}(s)'
            else:
                label = f'No {self.df_state.cargo_obj['name']} to retrieve all'

        super().__init__(style=discord.ButtonStyle.red, label=label, disabled=disabled, custom_id='retrieve_all_cargo_button', row=row)

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        if not self.retrieve_list or self.total_quantity_to_retrieve == 0:
            await interaction.response.send_message('Nothing to retrieve.', ephemeral=True)
            return

        for cargo_stack in self.retrieve_list:
            try:
                await api_calls.retrieve_cargo_from_warehouse(
                    warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                    convoy_id=self.df_state.convoy_obj['convoy_id'],
                    cargo_id=cargo_stack['cargo_id'],
                    quantity=cargo_stack['quantity']  # Retrieve the whole stack
                )
            except RuntimeError as e:
                await interaction.response.send_message(content=f'Error retrieving {cargo_stack['name']}: {e}', ephemeral=True)
                # Potentially stop or continue

        # Re-fetch user_obj to get updated convoy list and money
        self.df_state.user_obj = await api_calls.get_user(self.df_state.user_obj['user_id'])
        # Re-fetch convoy_obj if it still exists
        self.df_state.convoy_obj = next((c for c in self.df_state.user_obj['convoys'] if c['convoy_id'] == self.df_state.convoy_obj['convoy_id']), None)
        # Re-fetch warehouse_obj for its updated inventory
        self.df_state.warehouse_obj = await api_calls.get_warehouse(self.df_state.warehouse_obj['warehouse_id'])
        await warehouse_menu(self.df_state)


async def store_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=store_vehicle_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    embed.description = vehicles_md(df_state.convoy_obj['vehicles'], verbose=True)

    embeds = [embed]
    view = StoreVehicleView(df_state)
    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class StoreVehicleView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(StoreVehicleSelect(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class StoreVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Select vehicle to store'
        disabled = False
        options = [
            discord.SelectOption(
                label=vehicle['name'],
                value=vehicle['vehicle_id'],
                emoji=get_vehicle_emoji(vehicle['shape'])
            )
            for vehicle in self.df_state.convoy_obj['vehicles']
            if all(c['intrinsic_part_id'] for c in vehicle['cargo'])  # Check if any of the cargo aren't intrinsic
        ]
        if not options:
            placeholder = 'No vehicle available (Vehicles must be empty)'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options[:25],
            disabled=disabled,
            custom_id='store_vehicle_select',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        vehicle_to_store = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        try:
            # API call to store the vehicle
            await api_calls.store_vehicle_in_warehouse(
                warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                vehicle_id=vehicle_to_store['vehicle_id']
            )
            # Re-fetch user_obj to get updated convoy list and money
            self.df_state.user_obj = await api_calls.get_user(self.df_state.user_obj['user_id'])
            # Re-fetch warehouse_obj for its updated inventory
            self.df_state.warehouse_obj = await api_calls.get_warehouse(self.df_state.warehouse_obj['warehouse_id'])

            # Check if the convoy still exists
            updated_convoy_obj = next((c for c in self.df_state.user_obj['convoys'] if c['convoy_id'] == self.df_state.convoy_obj['convoy_id']), None)
            self.df_state.convoy_obj = updated_convoy_obj

        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        if self.df_state.convoy_obj:
            await warehouse_menu(self.df_state)  # Refresh warehouse menu with updated convoy
        else:
            # Convoy was disbanded, go to main menu
            await discord_app.main_menu_menus.main_menu(
                interaction=self.df_state.interaction,
                user_cache=self.df_state.user_cache,
            )


async def retrieve_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=retrieve_vehicle_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    sorted_vehicles = sorted(df_state.warehouse_obj['vehicle_storage'], key=lambda x: x['name'], reverse=True)
    embed.description = vehicles_md(sorted_vehicles, verbose=True)

    embeds = [embed]

    view = RetrieveVehicleView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class RetrieveVehicleView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(RetrieveVehicleSelect(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class RetrieveVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Select vehicle to retrieve'
        disabled = False

        options = [
            discord.SelectOption(
                label=vehicle['name'],
                value=vehicle['vehicle_id'],
                emoji=get_vehicle_emoji(vehicle['shape'])
            )
            for vehicle in self.df_state.warehouse_obj['vehicle_storage']
        ]
        if not options:
            placeholder = 'No vehicles in warehouse'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options,
            custom_id='store_vehicle_select',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        vehicle_to_retrieve = next((
            v for v in self.df_state.warehouse_obj['vehicle_storage']
            if v['vehicle_id'] == self.values[0]
        ), None)
        try:
            # API call to retrieve the vehicle
            await api_calls.retrieve_vehicle_in_warehouse(
                warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                vehicle_id=vehicle_to_retrieve['vehicle_id']
            )
            # Re-fetch user_obj to get updated convoy list and money
            self.df_state.user_obj = await api_calls.get_user(self.df_state.user_obj['user_id'])
            # Re-fetch convoy_obj as it has been modified
            self.df_state.convoy_obj = next((c for c in self.df_state.user_obj['convoys'] if c['convoy_id'] == self.df_state.convoy_obj['convoy_id']), None)
             # Re-fetch warehouse_obj for its updated inventory
            self.df_state.warehouse_obj = await api_calls.get_warehouse(self.df_state.warehouse_obj['warehouse_id'])

        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        await warehouse_menu(self.df_state)


async def spawn_convoy_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=spawn_convoy_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    sorted_vehicles = sorted(df_state.warehouse_obj['vehicle_storage'], key=lambda x: x['name'], reverse=True)
    embed.description = vehicles_md(sorted_vehicles, verbose=True)

    embeds = [embed]

    view = SpawnConvoyView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class SpawnConvoyView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        if self.df_state.convoy_obj:
            discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(SpawnVehicleSelect(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class SpawnVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Vehicle to start convoy with'
        disabled = False
        options=[
            discord.SelectOption(label=vehicle['name'], value=vehicle['vehicle_id'])
            for vehicle in self.df_state.warehouse_obj['vehicle_storage']
        ]
        if not options:
            placeholder = 'No vehicles in warehouse'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options,
            custom_id='store_vehicle_select',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await interaction.response.send_modal(SpawnConvoyNameModal(self.df_state, self.values[0]))

class SpawnConvoyNameModal(discord.ui.Modal):
    def __init__(self, df_state: DFState, vehicle_id):
        self.df_state = df_state
        self.vehicle_id = vehicle_id

        super().__init__(title='Name your new convoy')

        self.convoy_name_input = discord.ui.TextInput(
            label='New convoy name',
            style=discord.TextStyle.short,
            required=True,
            default=f'{df_state.user_obj['username']}\'s convoy',
            max_length=48,
            custom_id='new_convoy_name'
        )
        self.add_item(self.convoy_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.spawn_convoy_from_warehouse(
                warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
                vehicle_id=self.vehicle_id,
                new_convoy_name=self.convoy_name_input.value
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        await discord_app.convoy_menus.convoy_menu(self.df_state)


async def warehouseless(df_state: DFState, edit: bool):
    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    embed.description = f'*You do not have a warehouse in {df_state.sett_obj['name']}. Buy one with the button below.*'

    embeds = [embed]
    embeds = add_tutorial_embed(embeds, df_state)

    view = NoWarehouseView(df_state)

    if edit:
        await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embeds=embeds, view=view)

class NoWarehouseView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyWarehouseButton(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class BuyWarehouseButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=f'Buy warehouse in {self.df_state.sett_obj['name']} | ${self.df_state.sett_obj['warehouse_price']:,}',
            disabled=False if self.df_state.convoy_obj['money'] > self.df_state.sett_obj['warehouse_price'] else True,
            custom_id='buy_warehouse_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            warehouse_id = await api_calls.new_warehouse(self.df_state.sett_obj['sett_id'], self.df_state.user_obj['user_id'])
            new_warehouse = await api_calls.get_warehouse(warehouse_id)
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        self.df_state.user_obj['warehouses'].append(new_warehouse)
        self.df_state.warehouse_obj = new_warehouse

        self.df_state.convoy_obj = await api_calls.get_convoy(self.df_state.convoy_obj['convoy_id'])  # Get convoy again to update money display. very wasteful and silly.

        await warehouse_menu(self.df_state)
