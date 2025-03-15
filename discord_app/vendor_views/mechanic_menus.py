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

    @discord.ui.button(label='Strip', style=discord.ButtonStyle.red, custom_id='strip', row=1, disabled=True)
    async def strip_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction
        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass

    @discord.ui.button(label='Recycle', style=discord.ButtonStyle.red, custom_id='recycle', row=1, disabled=True)
    async def recycle_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction
        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def upgrade_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=upgrade_vehicle_menu)  # Add this menu to the back stack

    part_list = []
    for part in df_state.vehicle_obj['parts']:
        if not part:  # If the part slot is empty
            part_list.append(f'- {part['slot'].replace('_', ' ').capitalize()}\n  - None')
            continue

        part_list.append(discord_app.cargo_menus.format_part(part))
    displayable_vehicle_parts = '\n'.join(part_list)

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

        # Disable the Convoy button if there's no cargo with a 'part' value
        if not any(cargo.get('part') for cargo in self.df_state.convoy_obj['all_cargo']):
            self.install_part_from_convoy_button.disabled = True

        # Disable the Vendor button if there's no cargo with a 'part' value
        if not any(cargo.get('part') for cargo in self.df_state.vendor_obj['cargo_inventory']):
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

    cargo_source = df_state.vendor_obj['cargo_inventory'] if is_vendor else df_state.convoy_obj['all_cargo']

    part_cargos_to_display = []
    for cargo in cargo_source:
        if cargo.get('part'):
            try:
                check_dict = await api_calls.check_part_compatibility(df_state.vehicle_obj['vehicle_id'], cargo['cargo_id'])
                cargo['part'] = check_dict['part']
                cargo['part']['installation_price'] = check_dict['installation_price']
                
                if is_vendor:  # Only assign kit_price if the cargo is from a vendor
                    cargo['part']['kit_price'] = cargo['price']
                
                part_cargos_to_display.append(cargo)
            except RuntimeError as e:
                # print(f'part does not fit: {e}')
                continue
    
    part_list = []
    for cargo in part_cargos_to_display:
        part_list.append(discord_app.cargo_menus.format_part(cargo))
    displayable_vehicle_parts = '\n'.join(part_list)

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## {df_state.vehicle_obj["name"]}',
        f'*{df_state.vehicle_obj["base_desc"]}*',
        '### Compatible parts available for purchase and installation' if is_vendor else '### Compatible parts available for installation',
        f'{displayable_vehicle_parts}',
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

        self.add_item(PartSelect(self.df_state, part_cargos_to_display))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class PartSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, part_cargos_to_display):
        self.df_state = df_state
        self.part_cargos_to_display = part_cargos_to_display

        options=[
            discord.SelectOption(label=cargo['name'], value=cargo['cargo_id'])
            for cargo in part_cargos_to_display
            if cargo.get('part')
        ]
        
        super().__init__(
            placeholder='Which part?',
            options=options,
            custom_id='select_part',
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

    current_part = None
    for part in df_state.vehicle_obj['parts']:
        if part['slot'] == df_state.cargo_obj['part']['slot']:
            current_part = part
    if not current_part:
        current_part = None

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        '### Current Part',
        f'{discord_app.cargo_menus.format_part(current_part) if current_part else '- None'}',
        '### New Part',
        f'{discord_app.cargo_menus.format_part(df_state.cargo_obj)}',
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

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## {self.df_state.vehicle_obj['name']}',
            f'*{self.df_state.vehicle_obj['description']}*',
            '## Stats'
        ])
        embed = discord_app.vehicle_menus.df_embed_vehicle_stats(self.df_state, embed, self.df_state.vehicle_obj)

        view = PostInstallView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class PostInstallView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

    async def on_timeout(self):
        await handle_timeout(self.df_state)
