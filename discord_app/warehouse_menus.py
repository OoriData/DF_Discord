# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, handle_timeout, df_embed_author, add_tutorial_embed, validate_interaction, get_user_metadata, get_vehicle_emoji, get_cargo_emoji
from discord_app.map_rendering import add_map_to_embed
import                                discord_app.vendor_views.vendor_menus
import                                discord_app.vendor_views.buy_menus
import                                discord_app.nav_menus
import                                discord_app.main_menu_menus
import                                discord_app.convoy_menus
from discord_app.vendor_views  import vehicles_md
from discord_app.df_state      import DFState


async def warehouse_menu(df_state: DFState, edit: bool=True):
    df_state.append_menu_to_back_stack(func=warehouse_menu)  # Add this menu to the back stack

    if df_state.warehouse_obj:
        df_state.warehouse_obj = await api_calls.get_warehouse(df_state.warehouse_obj['warehouse_id'])
        
        await warehoused(df_state, edit)
    else:
        await warehouseless(df_state, edit)

async def warehoused(df_state: DFState, edit: bool):
    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    embed.description = f'# Warehouse in {df_state.sett_obj['name']}'
    embed.description += '\n' + await warehouse_storage_md(df_state.warehouse_obj, verbose=True)

    cargo_volume = sum(cargo['volume'] * cargo['quantity'] for cargo in df_state.warehouse_obj['cargo_storage'])  # TODO: Think about implementing this stat in the backend

    if df_state.user_obj['metadata']['mobile']:
        embed.description += '\n' + '\n'.join([
            '',
            f'Cargo Storage 📦: **{cargo_volume:,}** / {df_state.warehouse_obj['cargo_storage_capacity']:,}L',
            f'Vehicle Storage 🅿️: **{len(df_state.warehouse_obj['vehicle_storage'])}** / {df_state.warehouse_obj['vehicle_storage_capacity']:,}'
        ])
    else:
        embed.add_field(name='Cargo Storage 📦', value=f'**{cargo_volume:,}**\n/{df_state.warehouse_obj['cargo_storage_capacity']:,} liters')
        embed.add_field(name='Vehicle Storage 🅿️', value=f'**{len(df_state.warehouse_obj['vehicle_storage'])}**\n/{df_state.warehouse_obj['vehicle_storage_capacity']:,}')

    embed.description = embed.description[:4096]  # Limit the length of the description to ensure it is within the limit

    embeds = [embed]

    view = WarehouseView(df_state)

    if edit:
        await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embeds=embeds, view=view)

async def warehouse_storage_md(warehouse_obj, verbose: bool = False) -> str:
    vehicle_list = []
    for vehicle in warehouse_obj['vehicle_storage']:
        vehicle_str = f'- {vehicle['name']} | *${vehicle['value']:,}*'

        if verbose:
            vehicle_str += '\n' + '\n'.join([
                f'  - Top Speed: **{vehicle['top_speed']}** / 100',
                f'  - Efficiency: **{vehicle['efficiency']}** / 100',
                f'  - Offroad Capability: **{vehicle['offroad_capability']}** / 100',
                f'  - Volume Capacity: **{vehicle['cargo_capacity']}**L',
                f'  - Weight Capacity: **{vehicle['weight_capacity']}**kg'
            ])

        vehicle_list.append(vehicle_str)
    displayable_vehicles = '\n'.join(vehicle_list) if vehicle_list else '- None'

    cargo_list = []
    for cargo in warehouse_obj['cargo_storage']:
        cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *${cargo['price']:,} each*'

        if verbose:
            for resource in ['fuel', 'water', 'food']:
                if cargo[resource]:
                    unit = ' meals' if resource == 'food' else 'L'
                    cargo_str += f'\n  - {resource.capitalize()}: {cargo[resource]:,.0f}{unit}'

            if cargo['recipient']:
                cargo['recipient_vendor'] = await api_calls.get_vendor(vendor_id=cargo['recipient'])
                cargo_str += f'\n  - Deliver to *{cargo['recipient_vendor']['name']}* | ***${cargo['delivery_reward']:,.0f}*** *each*'
                margin = min(round(cargo['delivery_reward'] / cargo['price']), 24)  # limit emojis to 24
                cargo_str += f'\n  - Profit margin: {'💵 ' * margin}'

        cargo_list.append(cargo_str)
    displayable_cargo = '\n'.join(cargo_list) if cargo_list else '- None'

    return '\n'.join([
        '**Cargo:**',
        f'{displayable_cargo}',
        '',
        '**Vehicles:**',
        f'{displayable_vehicles}'
    ])

class WarehouseView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        self.df_state.warehouse_obj = await api_calls.expand_warehouse(
            warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
            user_id=self.df_state.user_obj['user_id'],
            cargo_capacity_upgrade=1
        )

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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        self.df_state.warehouse_obj = await api_calls.expand_warehouse(
            warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
            user_id=self.df_state.user_obj['user_id'],
            vehicle_capacity_upgrade=1
        )

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
                    vendor_name = f"| {vendor_mapping.get(cargo['recipient'], '')}"

                    options.append(discord.SelectOption(
                        label=f'{cargo["name"]} | {vehicle["name"]} {vendor_name}',
                        value=cargo['cargo_id'],
                        emoji=get_cargo_emoji(cargo)
                    ))

        if not options:
            placeholder = 'Convoy has no cargo which can be stored'
            disabled = True
            options = [discord.SelectOption(label='None', value='None')]

        super().__init__(
            placeholder=placeholder,
            options=options[:25],
            disabled=disabled,
            custom_id='store_cargo_select',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        
        store_volume = self.store_quantity * self.df_state.cargo_obj['volume']

        self.description = '\n'.join([
            f'# Warehouse in {df_state.sett_obj['name']}',
            f'### Storing: {self.store_quantity} {self.df_state.cargo_obj['name']}(s)',
            f'*{self.df_state.cargo_obj['base_desc']}*',
            f'- Storing volume: {store_volume:,}L'
        ])

        if get_user_metadata(df_state, 'mobile'):
            self.description += '\n' + '\n'.join([
                f'- Convoy inventory: {self.df_state.cargo_obj['quantity']}',
                f'- Volume (per unit): {self.df_state.cargo_obj['volume']}L',
                f'- Weight (per unit): {self.df_state.cargo_obj['weight']}kg'
            ])
        else:
            self.add_field(name='Inventory', value=self.df_state.cargo_obj['quantity'])
            self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['volume']} liter(s)')
            self.add_field(name='Weight (per unit)', value=f'{self.df_state.cargo_obj['weight']} kilogram(s)')

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

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class CargoStoreQuantityButton(discord.ui.Button):  # XXX: Explode this button into like 4 different buttons, instead of just nesting a million if/elses
    def __init__(
            self,
            df_state: DFState,
            store_quantity: int,
            button_quantity: int | str,
            row: int = 1
    ):
        self.df_state = df_state
        self.store_quantity = store_quantity

        inventory_quantity = self.df_state.cargo_obj['quantity']

        if button_quantity == 'max':  # Handle "max" button logic
            self.button_quantity = inventory_quantity - self.store_quantity
            self.button_quantity = max(0, self.button_quantity)  # Ensure the quantity is 0
            label = f'max ({self.button_quantity:+,})'
        else:
            self.button_quantity = int(button_quantity)
            label = f'{self.button_quantity:+,}'

        resultant_quantity = self.store_quantity + self.button_quantity

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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        
        await warehouse_menu(self.df_state)


async def retrieve_cargo_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=store_cargo_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = f'# Warehouse in {df_state.sett_obj['name']}'
    cargo_volume = sum(cargo['volume'] * cargo['quantity'] for cargo in df_state.warehouse_obj['cargo_storage'])  # TODO: Think about implementing this stat in the backend

    embed.description += f'\nCargo Storage 📦: **{cargo_volume:,}** / {df_state.warehouse_obj['cargo_storage_capacity']:,}L'

    embeds = [embed]
    view = RetrieveCargoView(df_state)
    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class RetrieveCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Cargo which can be retrieved'
        disabled = False

        vendor_mapping = {}
        for r in self.df_state.map_obj['tiles']:  # Build vendor mapping
            for tile in r:
                for settlement in tile['settlements']:
                    for vendor in settlement['vendors']:
                        vendor_mapping[vendor['vendor_id']] = vendor['name']

        options = []
        for cargo in df_state.warehouse_obj['cargo_storage']:
            vendor_name = f"| {vendor_mapping.get(cargo['recipient'], '')}"

            options.append(discord.SelectOption(
                label=f'{cargo["name"]} {vendor_name}',
                value=cargo['cargo_id'],
                emoji=get_cargo_emoji(cargo)
            ))

        if not options:
            placeholder = 'Warehouse has no cargo which can be retrieved'
            disabled = True
            options = [discord.SelectOption(label='None', value='None')]

        super().__init__(
            placeholder=placeholder,
            options=options[:25],
            disabled=disabled,
            custom_id='retrieve_cargo_select',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        # Defaults to none if cargo item selected matches a cargo item in the convoy's inventory
        self.df_state.cargo_obj = next((
            c for c in self.df_state.warehouse_obj['cargo_storage']
            if c['cargo_id'] == self.values[0]
        ), None)

        await retrieve_cargo_quantity_menu(self.df_state)

class RetrieveCargoView(discord.ui.View):
    def __init__(self, df_state: DFState, retrieve_quantity: int=1):
        self.df_state = df_state
        self.retrieve_quantity = retrieve_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(RetrieveCargoSelect(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def retrieve_cargo_quantity_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=store_cargo_quantity_menu)  # Add this menu to the back stack

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
        
        retrieve_volume = self.retrieve_quantity * self.df_state.cargo_obj['volume']

        self.description = '\n'.join([
            f'# Warehouse in {df_state.sett_obj['name']}',
            f'### Retrieving: {self.retrieve_quantity} {self.df_state.cargo_obj['name']}(s)',
            f'*{self.df_state.cargo_obj['base_desc']}*',
            f'- Retrieving volume: {retrieve_volume:,}L'
        ])

        if get_user_metadata(df_state, 'mobile'):
            self.description += '\n' + '\n'.join([
                f'- Convoy inventory: {self.df_state.cargo_obj['quantity']}',
                f'- Volume (per unit): {self.df_state.cargo_obj['volume']}L',
                f'- Weight (per unit): {self.df_state.cargo_obj['weight']}kg'
            ])
        else:
            self.add_field(name='Inventory', value=self.df_state.cargo_obj['quantity'])
            self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['volume']} liter(s)')
            self.add_field(name='Weight (per unit)', value=f'{self.df_state.cargo_obj['weight']} kilogram(s)')

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

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class CargoRetrieveQuantityButton(discord.ui.Button):  # XXX: Explode this button into like 4 different buttons, instead of just nesting a million if/elses
    def __init__(
            self,
            df_state: DFState,
            retrieve_quantity: int,
            button_quantity: int | str,
            row: int = 1
    ):
        self.df_state = df_state
        self.retrieve_quantity = retrieve_quantity

        cargo_obj = self.df_state.cargo_obj
        quantity = 0
        for vehicle in self.df_state.convoy_obj['vehicles']:
            # Determine max quantity by volume
            free_space = vehicle['free_space']
            max_by_volume = free_space / cargo_obj['volume']
            
            # Determine max quantity by weight
            weight_capacity = vehicle['remaining_capacity']
            max_by_weight = weight_capacity / cargo_obj['weight']

            quantity += int(min(max_by_volume, max_by_weight))

        max_convoy_capacity = quantity
        inventory_quantity = self.df_state.cargo_obj['quantity']

        if button_quantity == 'max':  # Handle "max" button logic
            self.button_quantity = min(max_convoy_capacity, inventory_quantity) - self.retrieve_quantity
            self.button_quantity = max(0, self.button_quantity)  # Ensure the quantity is 0 or greater
            label = f'max ({self.button_quantity:+,})'
        else:
            self.button_quantity = int(button_quantity)
            label = f'{self.button_quantity:+,}'

        resultant_quantity = self.retrieve_quantity + self.button_quantity

        disabled = self.should_disable_button(  # Determine if button should be disabled
            resultant_quantity, inventory_quantity, max_convoy_capacity
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

    def should_disable_button(self, resultant_quantity, inventory_quantity, max_convoy_capacity):
        # Disable if the resulting quantity is out of valid bounds
        if resultant_quantity <= 0:
            return True
        
        if resultant_quantity > inventory_quantity:
            return True
        
        max_by_volume = self.df_state.convoy_obj['total_free_space'] / self.df_state.cargo_obj['volume']
        max_by_weight = self.df_state.convoy_obj['total_remaining_capacity'] / self.df_state.cargo_obj['weight']
        if resultant_quantity > max_by_volume or resultant_quantity > max_by_weight:
            return True
        
        if resultant_quantity > max_convoy_capacity:
            return True


        return False

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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

        super().__init__(
            placeholder=placeholder,
            options=options[:25],
            disabled=disabled,
            custom_id='store_vehicle_select',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        vehicle_to_store = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        self.df_state.convoy_obj = await api_calls.store_vehicle_in_warehouse(
            warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
            convoy_id=self.df_state.convoy_obj['convoy_id'],
            vehicle_id=vehicle_to_store['vehicle_id']
        )
        self.df_state.warehouse_obj = await api_calls.get_warehouse(self.df_state.warehouse_obj['warehouse_id'])

        if self.df_state.convoy_obj:
            await warehouse_menu(self.df_state)
        else:
            await discord_app.main_menu_menus.main_menu(
                interaction=self.df_state.interaction,
                df_map=self.df_state.map_obj
            )


async def retrieve_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=retrieve_vehicle_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    embed.description = vehicles_md(df_state.warehouse_obj['vehicle_storage'], verbose=True)

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
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id='store_vehicle_select',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        vehicle_to_retrieve = next((
            v for v in self.df_state.warehouse_obj['vehicle_storage']
            if v['vehicle_id'] == self.values[0]
        ), None)

        self.df_state.convoy_obj = await api_calls.retrieve_vehicle_in_warehouse(
            warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
            convoy_id=self.df_state.convoy_obj['convoy_id'],
            vehicle_id=vehicle_to_retrieve['vehicle_id']
        )
        self.df_state.warehouse_obj = await api_calls.get_warehouse(self.df_state.warehouse_obj['warehouse_id'])

        await warehouse_menu(self.df_state)


async def spawn_convoy_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=spawn_convoy_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    embed.description = vehicles_md(df_state.warehouse_obj['vehicle_storage'], verbose=True)

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
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id='store_vehicle_select',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
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

        self.df_state.convoy_obj = await api_calls.spawn_convoy_from_warehouse(
            warehouse_id=self.df_state.warehouse_obj['warehouse_id'],
            vehicle_id=self.vehicle_id,
            new_convoy_name=self.convoy_name_input.value
        )

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
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        warehouse_id = await api_calls.new_warehouse(self.df_state.sett_obj['sett_id'], self.df_state.user_obj['user_id'])
        new_warehouse = await api_calls.get_warehouse(warehouse_id)
        self.df_state.user_obj['warehouses'].append(new_warehouse)
        self.df_state.warehouse_obj = new_warehouse

        self.df_state.convoy_obj = await api_calls.get_convoy(self.df_state.convoy_obj['convoy_id'])  # Get convoy again to update money display. very wasteful and silly.
        
        await warehouse_menu(self.df_state)
