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


async def mechanic_menu(df_state: DFState):
    vehicle_list = []
    for vehicle in df_state.convoy_obj['vehicles']:
        vehicle_str = f'- {vehicle['name']} - ${vehicle['value']}'
        vehicle_list.append(vehicle_str)
    displayable_vehicles = '\n'.join(vehicle_list)

    mech_embed = discord.Embed(
        title=df_state.vendor_obj['name'],
        description=textwrap.dedent(f'''\
            **Select a vehicle for repairs/upgrades:**
            Vehicles:
            {displayable_vehicles}
        ''')
    )
    mech_embed = df_embed_author(mech_embed, df_state)
    
    vehicle_dropdown_view = MechVehicleDropdownView(df_state)

    df_state.previous_embed = mech_embed
    df_state.previous_view = vehicle_dropdown_view
    df_state.previous_attachments = []
    await df_state.interaction.response.edit_message(embed=mech_embed, view=vehicle_dropdown_view)


class MechVehicleDropdownView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, df_state)

        self.add_item(VehicleSelect(df_state))
    
    @discord.ui.button(label='Repair wear and AP for all vehicles', style=discord.ButtonStyle.green, custom_id='repair_all', disabled=True)
    async def repair_all_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction
        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass


class VehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        options=[
            discord.SelectOption(label=vehicle['name'], value=vehicle['vehicle_id'])
            for vehicle in df_state.convoy_obj['vehicles']
        ]
        
        super().__init__(
            placeholder='Which vehicle?',
            options=options,
            custom_id='select_vehicle',
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.vehicle_obj = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        mech_embed = discord.Embed()
        # mech_embed = df_embed_author(mech_embed, self.user_obj['convoys'][0], interaction.user)
        mech_embed.description = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## {self.df_state.vehicle_obj['name']}',
            f'*{self.df_state.vehicle_obj['base_desc']}*',
            '## Stats'
        ])
        mech_embed = discord_app.vehicle_views.df_embed_vehicle_stats(mech_embed, self.df_state.vehicle_obj)

        mech_view = MechView(self.df_state)

        self.df_state.previous_embed = mech_embed
        self.df_state.previous_view = mech_view
        self.df_state.previous_attachments = []
        await interaction.response.edit_message(embed=mech_embed, view=mech_view)


class MechView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

    @discord.ui.button(label='Repair', style=discord.ButtonStyle.green, custom_id='repair', row=1, disabled=True)
    async def repair_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction
        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass

    @discord.ui.button(label='Upgrade', style=discord.ButtonStyle.blurple, custom_id='upgrade', row=1)
    async def upgrade_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction

        part_list = []
        for category, part in self.df_state.vehicle_obj['parts'].items():
            if not part:  # If the part slot is empty
                part_list.append(f'- {category.replace('_', ' ').capitalize()}\n  - None')
                continue

            part_list.append(discord_app.cargo_views.format_part(part))
        displayable_vehicle_parts = '\n'.join(part_list)

        mech_vehicle_embed = discord.Embed()
        # mech_vehicle_embed = df_embed_author(mech_vehicle_embed, self.user_obj['convoys'][0], interaction.user)
        mech_vehicle_embed.description = '\n'.join([
            f'## {self.df_state.vehicle_obj['name']}',
            f'*{self.df_state.vehicle_obj['base_desc']}*',
            '## Parts',
            displayable_vehicle_parts,
            '## Stats'
        ])
        mech_vehicle_embed = discord_app.vehicle_views.df_embed_vehicle_stats(mech_vehicle_embed, self.df_state.vehicle_obj)

        mech_vehicle_view = MechVehicleView(self.df_state)

        self.df_state.previous_embed = mech_vehicle_embed
        self.df_state.previous_view = mech_vehicle_view
        self.df_state.previous_attachments = []
        await interaction.response.edit_message(embed=mech_vehicle_embed, view=mech_vehicle_view)

    @discord.ui.button(label='Strip', style=discord.ButtonStyle.red, custom_id='strip', row=1, disabled=True)
    async def strip_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction
        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass

    @discord.ui.button(label='Recycle', style=discord.ButtonStyle.red, custom_id='recycle', row=1, disabled=True)
    async def recycle_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction
        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass


class MechVehicleView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        # Disable the Convoy button if there's no cargo with a 'part' value
        if not any(cargo.get('part') for cargo in self.df_state.convoy_obj['all_cargo']):
            self.install_part_from_convoy_button.disabled = True

        # Disable the Vendor button if there's no cargo with a 'part' value
        if not any(cargo.get('part') for cargo in self.df_state.vendor_obj['cargo_inventory']):
            self.install_part_from_vendor_button.disabled = True

    async def handle_part_lists(self, interaction: discord.Interaction, cargo_source, is_vendor):
        self.df_state.interaction = interaction

        part_cargos_to_display = []
        for cargo in cargo_source:
            if cargo.get('part'):
                try:
                    check_dict = await api_calls.check_part_compatibility(self.df_state.vehicle_obj['vehicle_id'], cargo['cargo_id'])
                    cargo['part'] = check_dict['part']
                    cargo['part']['installation_price'] = check_dict['installation_price']
                    
                    # Only assign kit_price if the cargo is from a vendor
                    if is_vendor:
                        cargo['part']['kit_price'] = cargo['base_price']
                    
                    part_cargos_to_display.append(cargo)
                except RuntimeError as e:
                    print(f'part does not fit: {e}')
                    continue
        
        part_list = []
        for cargo in part_cargos_to_display:
            part_list.append(discord_app.cargo_views.format_part(cargo['part']))
        displayable_vehicle_parts = '\n'.join(part_list)

        cargo_selection_embed = discord.Embed()
        # cargo_selection_embed = df_embed_author(cargo_selection_embed, self.user_obj['convoys'][0], interaction.user)
        cargo_selection_embed.description = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## {self.df_state.vehicle_obj["name"]}',
            f'*{self.df_state.vehicle_obj["base_desc"]}*',
            '### Compatible parts available for purchase and installation' if is_vendor else '### Compatible parts available for installation',
            f'{displayable_vehicle_parts}',
            '### Stats'
        ])
        cargo_selection_embed = discord_app.vehicle_views.df_embed_vehicle_stats(cargo_selection_embed, self.df_state.vehicle_obj)

        cargo_selection_view = CargoSelectView(self.df_state)

        self.df_state.previous_embed = cargo_selection_embed
        self.df_state.previous_view = cargo_selection_view
        self.df_state.previous_attachments = []
        await interaction.response.edit_message(embed=cargo_selection_embed, view=cargo_selection_view)

    @discord.ui.button(label='Install part from Convoy inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_convoy', row=1)
    async def install_part_from_convoy_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction

        convoy_cargo = self.df_state.convoy_obj['all_cargo']
        await self.handle_part_lists(interaction, convoy_cargo, is_vendor=False)

    @discord.ui.button(label='Install part from Vendor inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_vendor', row=1)
    async def install_part_from_vendor_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction

        vendor_cargo = self.df_state.vendor_obj['cargo_inventory']
        await self.handle_part_lists(interaction, vendor_cargo, is_vendor=True)


class CargoSelectView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        self.add_item(CargoSelect(self.df_state))


class CargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        options=[
            discord.SelectOption(label=cargo['name'], value=cargo['cargo_id'])
            for cargo in self.df_state.vendor_obj['cargo_inventory']
            if cargo.get('part')
        ]
        
        super().__init__(
            placeholder='Which part?',
            options=options,
            custom_id='select_part',
        )


    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        all_inventories = self.df_state.vendor_obj['cargo_inventory'] + self.df_state.convoy_obj['all_cargo']
        self.df_state.cargo_obj = next((
            c for c in all_inventories
            if c['cargo_id'] == self.values[0]
        ), None)
        selected_part = self.df_state.cargo_obj['part']

        current_part = None
        for category, part in self.df_state.vehicle_obj['parts'].items():
            if category == selected_part['category']:
                current_part = part
        if not current_part:
            current_part = None

        confirm_embed = discord.Embed()
        # confirm_embed = df_embed_author(confirm_embed, self.user_obj['convoys'][0], interaction.user)
        confirm_embed.description = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## {self.df_state.vehicle_obj['name']}\n'
            f'*{self.df_state.vehicle_obj['base_desc']}*\n'
            f'### Current Part\n'
            f'{discord_app.cargo_views.format_part(current_part) if current_part else '- None'}\n'
            f'### New Part\n'
            f'{discord_app.cargo_views.format_part(selected_part)}\n'
            '## Stats'
        ])
        confirm_embed = discord_app.vehicle_views.df_embed_vehicle_stats(confirm_embed, self.df_state.vehicle_obj, selected_part)

        install_confirm_view = InstallConfirmView(self.df_state)

        self.df_state.previous_embed = confirm_embed
        self.df_state.previous_view = install_confirm_view
        self.df_state.previous_attachments = []
        await interaction.response.edit_message(embed=confirm_embed, view=install_confirm_view)


class InstallConfirmView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

    @discord.ui.button(label='Install part', style=discord.ButtonStyle.green, custom_id='confirm_install_part', row=1)
    async def confirm_install_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction

        convoy_after = await api_calls.add_part(
            vendor_id=self.df_state.vendor_obj['vendor_id'],
            convoy_id=self.df_state.convoy_obj['convoy_id'],
            vehicle_id=self.df_state.vehicle_obj['vehicle_id'],
            part_cargo_id=self.df_state.cargo_obj['cargo_id']
        )

        self.df_state.vehicle_obj = next((
            v for v in convoy_after['vehicles']
            if v['vehicle_id'] == self.df_state.vehicle_obj['vehicle_id']
        ), None)

        post_install_embed = discord.Embed()
        # post_install_embed = df_embed_author(post_install_embed, self.user_obj['convoys'][0], interaction.user)
        post_install_embed.description = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## {self.df_state.vehicle_obj['name']}',
            f'*{self.df_state.vehicle_obj['base_desc']}*',
            '## Stats'
        ])
        post_install_embed = discord_app.vehicle_views.df_embed_vehicle_stats(post_install_embed, self.df_state.vehicle_obj)

        post_install_view = PostInstallView(self.df_state)

        await interaction.response.send_message(embed=post_install_embed, view=post_install_view)


class PostInstallView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()
