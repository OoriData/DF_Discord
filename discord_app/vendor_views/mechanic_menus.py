# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, handle_timeout, df_embed_author, validate_interaction
from discord_app.map_rendering import add_map_to_embed
import discord_app.nav_menus
import discord_app.vehicle_menus
import discord_app.cargo_menus

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


async def mechanic_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=mechanic_menu)  # Add this menu to the back stack

    vehicle_list = []
    for vehicle in df_state.convoy_obj['vehicles']:
        vehicle_str = f'- {vehicle['name']} - ${vehicle['value']}'
        vehicle_list.append(vehicle_str)
    displayable_vehicles = '\n'.join(vehicle_list)

    embed = discord.Embed(
        title=df_state.vendor_obj['name'],
        description=textwrap.dedent(f'''\
            **Select a vehicle for repairs/upgrades:**
            Vehicles:
            {displayable_vehicles}
        ''')
    )
    embed = df_embed_author(embed, df_state)

    view = MechVehicleDropdownView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class MechVehicleDropdownView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

        self.add_item(VehicleSelect(df_state))

    @discord.ui.button(label='Repair wear and AP for all vehicles', style=discord.ButtonStyle.green, custom_id='repair_all', row=1, disabled=True)
    async def repair_all_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass

    async def on_timeout(self):
        await handle_timeout(self.df_state)

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
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction

        self.df_state.vehicle_obj = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        await mech_vehicle_menu(self.df_state)


async def mech_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=mech_vehicle_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        '## Stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj)

    view = MechView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class MechView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

    @discord.ui.button(label='Repair', style=discord.ButtonStyle.green, custom_id='repair', row=1, disabled=True)
    async def repair_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass

    @discord.ui.button(label='Upgrade', style=discord.ButtonStyle.blurple, custom_id='upgrade', row=1)
    async def upgrade_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        await upgrade_vehicle_menu(self.df_state)

    @discord.ui.button(label='Remove Part', style=discord.ButtonStyle.blurple, custom_id='remove', row=1)
    async def remove_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        await remove_part_vehicle_menu(self.df_state)

    @discord.ui.button(label='Scrap', style=discord.ButtonStyle.red, custom_id='scrap', row=1)
    async def scrap_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        await scrap_vehicle_menu(self.df_state)

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def upgrade_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=upgrade_vehicle_menu)  # Add this menu to the back stack

    displayable_vehicle_parts = '\n'.join(
        discord_app.cargo_menus.format_part(part) for part in df_state.vehicle_obj['parts']
    )

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        '## Parts',
        displayable_vehicle_parts,
        '## Stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj)

    view = UpgradeVehicleView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class UpgradeVehicleView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

        # Disable the Convoy button if there's no cargo with a 'parts' value
        if not any(cargo.get('parts') for cargo in self.df_state.convoy_obj['all_cargo']):
            self.install_part_from_convoy_button.disabled = True

        # Disable the Vendor button if there's no cargo with a 'parts' value
        if not any(cargo.get('parts') for cargo in self.df_state.vendor_obj['cargo_inventory']):
            self.install_part_from_vendor_button.disabled = True

    @discord.ui.button(label='Install part from Convoy inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_convoy', row=1)
    async def install_part_from_convoy_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        await part_inventory_menu(self.df_state, is_vendor=False)

    @discord.ui.button(label='Install part from Vendor inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_vendor', row=1)
    async def install_part_from_vendor_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        await part_inventory_menu(self.df_state, is_vendor=True)

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def part_inventory_menu(df_state: DFState, is_vendor: bool=False):
    df_state.append_menu_to_back_stack(func=part_inventory_menu, args={'is_vendor': is_vendor})  # Add this menu to the back stack

    cargo_inventory = df_state.vendor_obj['cargo_inventory'] if is_vendor else df_state.convoy_obj['all_cargo']

    part_cargos_to_display = []
    for cargo in cargo_inventory:
        if cargo.get('parts'):
            try:
                cargo['parts'] = await api_calls.check_part_compatibility(df_state.vehicle_obj['vehicle_id'], cargo['cargo_id'])

                part_cargos_to_display.append(cargo)
            except RuntimeError as e:
                # print(f'part does not fit: {e}')
                continue

    displayable_vehicle_parts = '\n'.join(
        discord_app.cargo_menus.format_part(part) for part in part_cargos_to_display
    )

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['base_desc']}*',
        '### Compatible parts available for purchase and installation' if is_vendor else '### Compatible parts available for installation',
        displayable_vehicle_parts,
        '### Stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj)

    view = PartSelectView(df_state, part_cargos_to_display)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class PartSelectView(discord.ui.View):
    def __init__(self, df_state: DFState, part_cargos_to_display):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

        self.add_item(UpgradePartSelect(self.df_state, part_cargos_to_display))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class UpgradePartSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, part_cargos_to_display):
        self.df_state = df_state
        self.part_cargos_to_display = part_cargos_to_display

        placeholder = 'Which part to install?'
        disabled = False
        options = [
            discord.SelectOption(label=cargo['name'], value=cargo['cargo_id'])
            for cargo in self.part_cargos_to_display
            if cargo.get('parts')
        ]

        if not options:
            placeholder = 'No compatible parts to install'
            disabled = True
            options = [discord.SelectOption(label='none', value='none')]

        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id='select_part',
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction

        all_inventories = self.df_state.vendor_obj['cargo_inventory'] + self.df_state.convoy_obj['all_cargo']
        self.df_state.cargo_obj = next((
            c for c in all_inventories
            if c['cargo_id'] == self.values[0]
        ), None)

        await part_install_confirm_menu(self.df_state)


async def part_install_confirm_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=part_install_confirm_menu)  # Add this menu to the back stack

    current_parts = []
    for part in df_state.vehicle_obj['parts']:
        if part['slot'] in [cargo_part['slot'] for cargo_part in df_state.cargo_obj['parts']]:
            current_parts.append(part)

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        '### Current Part',
        discord_app.cargo_menus.format_part(current_parts) if current_parts else '- None',
        '### New Parts',
        discord_app.cargo_menus.format_part(df_state.cargo_obj),
        '## Stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj, df_state.cargo_obj)

    view = InstallConfirmView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class InstallConfirmView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

    @discord.ui.button(label='Install part', style=discord.ButtonStyle.green, custom_id='confirm_install_part', row=1)
    async def confirm_install_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction

        self.df_state.convoy_obj = await api_calls.add_part(
            vendor_id=self.df_state.vendor_obj['vendor_id'],
            convoy_id=self.df_state.convoy_obj['convoy_id'],
            vehicle_id=self.df_state.vehicle_obj['vehicle_id'],
            part_cargo_id=self.df_state.cargo_obj['cargo_id']
        )

        self.df_state.vehicle_obj = next((  # Get the updated vehicle from the returned convoy obj
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.df_state.vehicle_obj['vehicle_id']
        ), None)

        displayable_vehicle_parts = '\n'.join(
            discord_app.cargo_menus.format_part(part) for part in self.df_state.vehicle_obj['parts']
        )

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## {self.df_state.vehicle_obj['name']}',
            f'*{self.df_state.vehicle_obj['description']}*',
            '## Parts',
            displayable_vehicle_parts,
            '## Stats'
        ])
        embed = discord_app.vehicle_menus.df_embed_vehicle_stats(self.df_state, embed, self.df_state.vehicle_obj)

        view = PostMechView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def remove_part_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=remove_part_vehicle_menu)  # Add this menu to the back stack

    removable_parts = [part for part in df_state.vehicle_obj['parts'] if part['removable']]

    displayable_vehicle_parts = '\n'.join(discord_app.cargo_menus.format_part(part) for part in removable_parts)

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        '## Removable parts',
        displayable_vehicle_parts,
        '## Stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj)

    view = RemovePartView(df_state, removable_parts)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class RemovePartView(discord.ui.View):
    def __init__(self, df_state: DFState, removable_parts):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

        self.add_item(RemovePartSelect(self.df_state, removable_parts))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class RemovePartSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, removable_parts):
        self.df_state = df_state
        self.removable_parts = removable_parts

        placeholder = 'Which part to remove?'
        disabled = False
        options = [discord.SelectOption(label=part['name'], value=part['part_id']) for part in self.removable_parts]

        if not options:
            placeholder = 'No removable parts'
            disabled = True
            options = [discord.SelectOption(label='none', value='none')]

        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id='select_part',
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction

        self.df_state.part_obj = next((
            p for p in self.df_state.vehicle_obj['parts']
            if p['part_id'] == self.values[0]
        ), None)

        await part_remove_confirm_menu(self.df_state)


async def part_remove_confirm_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=part_remove_confirm_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        '### Part to remove:',
        discord_app.cargo_menus.format_part(df_state.part_obj),
        '## Stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj, df_state.cargo_obj)

    view = RemoveConfirmView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class RemoveConfirmView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

    @discord.ui.button(label='Remove part', style=discord.ButtonStyle.red, custom_id='confirm_remove_part', row=1)
    async def confirm_install_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction

        self.df_state.convoy_obj = await api_calls.remove_part(
            vendor_id=self.df_state.vendor_obj['vendor_id'],
            convoy_id=self.df_state.convoy_obj['convoy_id'],
            vehicle_id=self.df_state.vehicle_obj['vehicle_id'],
            part_id=self.df_state.part_obj['part_id']
        )

        self.df_state.vehicle_obj = next((  # Get the updated vehicle from the returned convoy obj
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.df_state.vehicle_obj['vehicle_id']
        ), None)

        displayable_vehicle_parts = '\n'.join(
            discord_app.cargo_menus.format_part(part) for part in self.df_state.vehicle_obj['parts']
        )

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## {self.df_state.vehicle_obj['name']}',
            f'*{self.df_state.vehicle_obj['description']}*',
            '## Parts',
            displayable_vehicle_parts,
            '## Stats'
        ])
        embed = discord_app.vehicle_menus.df_embed_vehicle_stats(self.df_state, embed, self.df_state.vehicle_obj)

        view = PostMechView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def scrap_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=scrap_vehicle_menu)  # Add this menu to the back stack

    scrap_check = await api_calls.check_scrap(df_state.vehicle_obj['vehicle_id'])
    scrap_price = scrap_check['salvage_price']
    salvage_part_cargo = scrap_check['salvage_part_cargo']

    displayable_salvage_part_cargo = []
    for cargo in salvage_part_cargo:
        part_strs = [discord_app.cargo_menus.format_part(part) for part in cargo['parts']]
        displayable_salvage_part_cargo.append('\n'.join([
            f'### {cargo['base_name']}',
            f'*{cargo['base_desc']}*',
            '\n'.join(part_strs)
        ]))

    scrap_check['displayable'] = '\n'.join(displayable_salvage_part_cargo)

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## Scrapping {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        f'### Cost to scrap vehicle: ${scrap_price:,.0f}',
        '## Cargo that will be salvaged while scrapping this vehicle',
        scrap_check['displayable'],
        '## Stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj)

    view = ScrapVehicleView(df_state, scrap_check)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class ScrapVehicleView(discord.ui.View):
    def __init__(self, df_state: DFState, scrap_check):
        self.df_state = df_state
        self.scrap_check = scrap_check
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(ScrapVehicleButton(self.df_state, self.scrap_check))

class ScrapVehicleButton(discord.ui.Button):
    def __init__(self, df_state: DFState, scrap_check):
        self.df_state = df_state
        self.scrap_price = scrap_check['salvage_price']
        self.salvage_part_cargo = scrap_check['salvage_part_cargo']
        self.displayable_salvage_part_cargo = scrap_check['displayable']

        if (
            all(c['intrinsic_part_id'] for c in self.df_state.vehicle_obj['cargo'])  # Has only intrisic cargo
            and self.df_state.convoy_obj['money'] >= self.scrap_price                # Convoy has the money
        ):
            label = f'Scrap {self.df_state.vehicle_obj['name']} | ${self.scrap_price:,.0f}'
            disabled = False
        else:
            label = f'{self.df_state.vehicle_obj['name']} contains cargo | ${self.scrap_price:,.0f}'
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.red,
            label=label,
            disabled=disabled,
            custom_id='confirm_scrap_vehicle',
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        self.df_state.convoy_obj = await api_calls.vendor_scrap_vehicle(
            vendor_id=self.df_state.vendor_obj['vendor_id'],
            convoy_id=self.df_state.convoy_obj['convoy_id'],
            vehicle_id=self.df_state.vehicle_obj['vehicle_id']
        )

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## Part cargo salvaged from {self.df_state.vehicle_obj['name']}',
            self.displayable_salvage_part_cargo,
        ])

        self.df_state.vehicle_obj = None

        view = PostMechView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)

    async def on_timeout(self):
        await handle_timeout(self.df_state)


class PostMechView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

    async def on_timeout(self):
        await handle_timeout(self.df_state)
