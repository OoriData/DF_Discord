# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap
import                                math

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, df_embed_author, add_tutorial_embed, get_user_metadata, DF_LOGO_EMOJI
from discord_app.map_rendering import add_map_to_embed
import                                discord_app.vendor_views.vendor_views
import                                discord_app.vendor_views.buy_menus
import                                discord_app.nav_menus
import                                discord_app.main_menu_views
import                                discord_app.convoy_views
from discord_app.vendor_views  import vehicles_md
from discord_app.df_state      import DFState


async def warehouse_storage_md(warehouse_obj, verbose: bool = False) -> str:
    vehicle_list = []
    for vehicle in warehouse_obj['vehicle_storage']:
        vehicle_str = f'- {vehicle['name']} | *${vehicle['value']:,}*'

        if verbose:
            vehicle_str += '\n' + '\n'.join([
                f'  - Top Speed: **{vehicle['top_speed']}** / 100',
                f'  - Fuel Efficiency: **{vehicle['fuel_efficiency']}** / 100',
                f'  - Offroad Capability: **{vehicle['offroad_capability']}** / 100',
                f'  - Volume Capacity: **{vehicle['cargo_capacity']}**L',
                f'  - Weight Capacity: **{vehicle['weight_capacity']}**kg'
            ])

        vehicle_list.append(vehicle_str)
    displayable_vehicles = '\n'.join(vehicle_list) if vehicle_list else '- None'

    cargo_list = []
    for cargo in warehouse_obj['cargo_storage']:
        cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *${cargo['base_price']:,} each*'

        if verbose:
            for resource in ['fuel', 'water', 'food']:
                if cargo[resource]:
                    unit = ' meals' if resource == 'food' else 'L'
                    cargo_str += f'\n  - {resource.capitalize()}: {cargo[resource]:,.0f}{unit}'

            if cargo['recipient']:
                cargo['recipient_vendor'] = await api_calls.get_vendor(vendor_id=cargo['recipient'])
                cargo_str += f'\n  - Deliver to *{cargo['recipient_vendor']['name']}* | ***${cargo['delivery_reward']:,.0f}*** *each*'
                margin = round(cargo['delivery_reward'] / cargo['base_price'])
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


async def warehouse_menu(df_state: DFState, edit: bool=True):
    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    if df_state.warehouse_obj:
        embed.description = f'# Warehouse in {df_state.sett_obj['name']}'
        embed.description += '\n' + await warehouse_storage_md(df_state.warehouse_obj, verbose=True)

        if df_state.user_obj['metadata']['mobile']:
            embed.description += '\n' + '\n'.join([
                '',
                f'Cargo Storage 📦: **{len(df_state.warehouse_obj['cargo_storage'])}**/{df_state.warehouse_obj['cargo_storage_capacity']}L',
                f'Vehicle Storage 🅿️: **{len(df_state.warehouse_obj['vehicle_storage'])}**/{df_state.warehouse_obj['vehicle_storage_capacity']}'
            ])
        else:
            embed.add_field(name='Cargo Storage 📦', value=f'**{len(df_state.warehouse_obj['cargo_storage'])}**\n/{df_state.warehouse_obj['cargo_storage_capacity']} liters')
            embed.add_field(name='Vehicle Storage 🅿️', value=f'**{len(df_state.warehouse_obj['vehicle_storage'])}**\n/{df_state.warehouse_obj['vehicle_storage_capacity']}')

        # view = SettView(df_state, df_state.sett_obj['vendors'])
        view = WarehouseView(df_state)
    else:
        embed.description = f'*You do not have a warehouse in {df_state.sett_obj['name']}. Buy one with the button below.*'
        view = NoWarehouseView(df_state)

    embeds = [embed]
    embeds = add_tutorial_embed(embeds, df_state)

    if edit:
        await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=embed, view=view)


class NoWarehouseView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyWarehouseButton(self.df_state))

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
        self.df_state.interaction = interaction

        warehouse_id = await api_calls.new_warehouse(self.df_state.sett_obj['sett_id'], self.df_state.user_obj['user_id'])
        new_warehouse = await api_calls.get_warehouse(warehouse_id)
        self.df_state.user_obj['warehouses'].append(new_warehouse)
        self.df_state.warehouse_obj = new_warehouse

        self.df_state.convoy_obj = await api_calls.get_convoy(self.df_state.convoy_obj['convoy_id'])  # Get convoy again to update money display. very wasteful and silly.
        
        await warehouse_menu(self.df_state)


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
        
        else:
            self.add_item(discord_app.nav_menus.NavMainMenuButton(df_state))

        self.add_item(SpawnButton(self.df_state))

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


class ExpandCargoButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Expand cargo storage',
            disabled=True,
            custom_id='expand_cargo_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        # open expansion menu
        # await warehouse_menu(self.df_state)


class ExpandVehiclesButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Expand vehicle storage',
            disabled=True,
            custom_id='expand_vehicles_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        # open expansion menu
        # await warehouse_menu(self.df_state)


class StoreCargoButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Store cargo',
            disabled=True,
            # disabled=False if self.df_state.convoy_obj['all_cargo'] else True,
            custom_id='store_cargo_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        # open expansion menu
        # await warehouse_menu(self.df_state)


class RetrieveCargoButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Retrieve cargo',
            disabled=True,
            # disabled=False if self.df_state.warehouse_obj['cargo_storage'] else True,
            custom_id='retrieve_cargo_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        # open expansion menu
        # await warehouse_menu(self.df_state)


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
        self.df_state.interaction = interaction

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)

        embed.description = vehicles_md(self.df_state.convoy_obj['vehicles'], verbose=True)

        embeds = [embed]

        view = StoreVehicleView(self.df_state)

        await self.df_state.interaction.response.edit_message(embeds=embeds, view=view)


class StoreVehicleView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(StoreVehicleSelect(self.df_state))

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


class StoreVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Select vehicle to store'
        disabled = False
        options=[
            discord.SelectOption(label=vehicle['name'], value=vehicle['vehicle_id'])
            for vehicle in self.df_state.convoy_obj['vehicles']
        ]
        if not options:
            placeholder = 'No vehicles in convoy'
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
            await discord_app.main_menu_views.main_menu(
                interaction=self.df_state.interaction,
                df_map=self.df_state.map_obj
            )


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
        self.df_state.interaction = interaction

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)

        embed.description = vehicles_md(self.df_state.warehouse_obj['vehicle_storage'], verbose=True)

        embeds = [embed]

        view = RetrieveVehicleView(self.df_state)

        await self.df_state.interaction.response.edit_message(embeds=embeds, view=view)


class RetrieveVehicleView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(RetrieveVehicleSelect(self.df_state))

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


class RetrieveVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Select vehicle to retrieve'
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


class SpawnButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=4):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.green,
            label='Initialize new convoy',
            disabled=False if self.df_state.warehouse_obj['vehicle_storage'] else True,
            custom_id='spawn_button',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)

        embed.description = vehicles_md(self.df_state.warehouse_obj['vehicle_storage'], verbose=True)

        embeds = [embed]

        view = SpawnConvoyView(self.df_state)

        await self.df_state.interaction.response.edit_message(embeds=embeds, view=view)


class SpawnConvoyView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        if self.df_state.convoy_obj:
            discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(SpawnVehicleSelect(self.df_state))

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

        await discord_app.convoy_views.convoy_menu(self.df_state)
