# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import (
    api_calls, handle_timeout, df_embed_author, validate_interaction, get_vehicle_emoji, split_description_into_embeds
)
from discord_app.vendor_menus  import enrich_parts_compatibility, format_parts_compatibility, format_basic_cargo
import discord_app.nav_menus
import discord_app.vehicle_menus
import discord_app.cargo_menus

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


async def mechanic_menu(df_state: DFState):
    if not df_state.vendor_obj:
        await discord_app.vendor_views.vendor_menus.vendor_menu(df_state)
    df_state.append_menu_to_back_stack(func=mechanic_menu)  # Add this menu to the back stack

    mech_embed = discord.Embed()
    mech_embed = df_embed_author(mech_embed, df_state)
    mech_embed.description = f'## {df_state.vendor_obj['name']}'

    embeds = [mech_embed]

    convoy_parts = []
    for cargo in df_state.convoy_obj['all_cargo']:
        if cargo.get('parts'):
            cargo_str = f'- **{cargo['name']}**'

            await enrich_parts_compatibility(df_state.convoy_obj, cargo)
            cargo_str += format_parts_compatibility(df_state.convoy_obj, cargo)

            convoy_parts.append(cargo_str)
    if convoy_parts:
        embeds.append(discord.Embed(description='\n'.join([
            '## Upgrade parts from convoy inventory',
            '\n'.join(convoy_parts),
        ])))

    vendor_parts = []
    for cargo in df_state.vendor_obj['cargo_inventory']:
        if cargo.get('parts'):
            cargo_str = format_basic_cargo(cargo)

            await enrich_parts_compatibility(df_state.convoy_obj, cargo)
            cargo_str += format_parts_compatibility(df_state.convoy_obj, cargo)

            vendor_parts.append(cargo_str)
    if vendor_parts:
        embeds.append(discord.Embed(description='\n'.join([
            '## Upgrade parts from vendor inventory',
            '\n'.join(vendor_parts),
        ])))

    vehicle_list = []
    for vehicle in df_state.convoy_obj['vehicles']:
        vehicle_hard_cap = vehicle['hard_stat_cap']
        vehicle_str = '\n'.join([
            f'- **{vehicle['name']}** | *${vehicle['value']:,.0f}*',
            f'  - 🌿 {vehicle['raw_efficiency']}  |  🚀 {vehicle['raw_top_speed']}  |  🥾 {vehicle['raw_offroad_capability']}',
            f'  - 📦 {vehicle['cargo_capacity']:,.0f} L  |  🏋️ {vehicle['weight_capacity']:,.0f} kg'
        ])
        vehicle_list.append(vehicle_str)

    embeds.append(discord.Embed(description='\n'.join([
        '### Select a vehicle for repairs/upgrades',
        '\n'.join(vehicle_list),
    ])))

    view = MechVehicleDropdownView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

class MechVehicleDropdownView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)

        self.add_item(VehicleSelect(df_state))

    @discord.ui.button(label='Repair wear and AP for all vehicles', style=discord.ButtonStyle.green, custom_id='repair_all', row=1, disabled=True)
    async def repair_all_button(self, interaction: discord.Interaction, button: discord.Button):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class VehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        options=[
            discord.SelectOption(
                label=vehicle['name'],
                value=vehicle['vehicle_id'],
                emoji=get_vehicle_emoji(vehicle['shape'])
            )
            for vehicle in df_state.convoy_obj['vehicles']
        ]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder='Which vehicle?',
            options=sorted_options,
            custom_id='select_vehicle',
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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
        f'### {df_state.vehicle_obj['name']} stats'
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        # await interaction.response.send_message('this don\'t do nothin yet!')
        pass

    @discord.ui.button(label='Upgrade', style=discord.ButtonStyle.blurple, custom_id='upgrade', row=1)
    async def upgrade_button(self, interaction: discord.Interaction, button: discord.Button):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await upgrade_vehicle_menu(self.df_state)

    @discord.ui.button(label='Remove Part', style=discord.ButtonStyle.blurple, custom_id='remove', row=1)
    async def remove_button(self, interaction: discord.Interaction, button: discord.Button):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await remove_part_vehicle_menu(self.df_state)

    @discord.ui.button(label='Scrap', style=discord.ButtonStyle.red, custom_id='scrap', row=1)
    async def scrap_button(self, interaction: discord.Interaction, button: discord.Button):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await scrap_vehicle_menu(self.df_state)

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def upgrade_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=upgrade_vehicle_menu)  # Add this menu to the back stack

    header_embed = df_embed_author(discord.Embed(), df_state)
    header_embed.description = '\n'.join([
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
    ])

    embeds = [header_embed]

    split_description_into_embeds(
        content_string='\n'.join(
            discord_app.cargo_menus.format_part(part, verbose=False) for part in df_state.vehicle_obj['parts']
        ),
        embed_title=f'## {df_state.vehicle_obj['name']} parts',
        target_embeds_list=embeds,
    )

    footer_embed = discord.Embed(description=f'## {df_state.vehicle_obj['name']} stats')
    footer_embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, footer_embed, df_state.vehicle_obj)
    embeds.append(footer_embed)

    view = UpgradeVehicleView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view)

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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await part_inventory_menu(self.df_state, is_vendor=False)

    @discord.ui.button(label='Install part from Vendor inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_vendor', row=1)
    async def install_part_from_vendor_button(self, interaction: discord.Interaction, button: discord.Button):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await part_inventory_menu(self.df_state, is_vendor=True)

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def part_inventory_menu(df_state: DFState, is_vendor: bool=False):
    df_state.append_menu_to_back_stack(func=part_inventory_menu, args={'is_vendor': is_vendor})  # Add this menu to the back stack

    if is_vendor:
        source_inventory = df_state.vendor_obj['cargo_inventory']
    else:
        # Filter for parts cargo from convoy's all_cargo
        source_inventory = [c for c in df_state.convoy_obj['all_cargo'] if c.get('parts')]

    incompatible_part_cargo_strs = []
    compatible_part_cargo_list = []  # Stores cargo dicts that are compatible

    for current_cargo_item in source_inventory:
        # For vendor inventory, ensure it's a part. Convoy inventory is pre-filtered.
        if is_vendor and not current_cargo_item.get('parts'):
            continue

        # Ensure 'compatibilities' key is present by calling enrich_parts_compatibility.
        # This modifies 'current_cargo_item' in-place.
        await enrich_parts_compatibility(df_state.convoy_obj, current_cargo_item)

        # Get the compatibility result for the currently selected vehicle
        vehicle_specific_compatibilities = current_cargo_item['compatibilities'].get(df_state.vehicle_obj['vehicle_id'])

        if isinstance(vehicle_specific_compatibilities, RuntimeError):
            incompatible_part_cargo_strs.append('\n'.join([
                f'- {current_cargo_item['name']}',
                f'  - ❌ *{vehicle_specific_compatibilities!s}*'
            ]))
        elif vehicle_specific_compatibilities:  # Check if the list of configurations is not empty
            compatible_part_cargo_list.append(current_cargo_item)
        else:
            # No compatible configurations for this specific vehicle
            incompatible_part_cargo_strs.append('\n'.join([
                f'- {current_cargo_item['name']}',
                f'  - ❌ *No compatible configurations for {df_state.vehicle_obj['name']}*'
            ]))

    displayable_incompatible_parts = '\n'.join(incompatible_part_cargo_strs) if incompatible_part_cargo_strs else '- None'

    displayable_compatible_parts = '\n\n'.join(
        discord_app.cargo_menus.format_part(c_cargo) for c_cargo in compatible_part_cargo_list
    )


    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj.get('description', '')}*',
        '### Incompatible parts',
        displayable_incompatible_parts if incompatible_part_cargo_strs else '- None',
        '### Compatible parts available for purchase and installation' if is_vendor else '### Compatible parts available for installation',
        displayable_compatible_parts if compatible_part_cargo_list else '- None',
        f'### {df_state.vehicle_obj['name']} stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj)

    view = PartSelectView(df_state, compatible_part_cargo_list)

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

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options,
            custom_id='select_part',
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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

    compatibilities = df_state.cargo_obj['compatibilities'].get(df_state.vehicle_obj['vehicle_id'])

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# {df_state.vendor_obj['name']}',
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        '### Current Part(s)',
        discord_app.cargo_menus.format_part(current_parts) if current_parts else '- None',
        '### New Part(s)',
        discord_app.cargo_menus.format_part(compatibilities),
        f'### {df_state.vehicle_obj['name']} stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj, df_state.cargo_obj)

    view = InstallConfirmView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class ConfirmInstallButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int = 1):
        self.df_state = df_state
        self.part_to_install = df_state.cargo_obj  # The cargo item selected for installation

        # Determine if the part is from the vendor's stock
        self.is_from_vendor_stock = any(
            c['cargo_id'] == self.part_to_install['cargo_id']
            for c in self.df_state.vendor_obj['cargo_inventory']
        )

        self.install_cost = 0
        if self.is_from_vendor_stock:
            self.install_cost = self.part_to_install.get('unit_price', 0)

        can_afford = self.df_state.convoy_obj['money'] >= self.install_cost
        
        label = f'Install {self.part_to_install['name']}'
        if self.install_cost > 0:
            label += f' | ${self.install_cost:,.0f}'
        
        disabled = False
        if self.install_cost > 0 and not can_afford:
            disabled = True
        elif self.install_cost == 0:  # Part from convoy inventory, installation is free
            disabled = False

        super().__init__(
            style=discord.ButtonStyle.green,
            label=label,
            disabled=disabled,
            custom_id='confirm_install_part',  # Keep original custom_id for consistency
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.add_part(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                vehicle_id=self.df_state.vehicle_obj['vehicle_id'],
                part_cargo_id=self.part_to_install['cargo_id']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        self.df_state.vehicle_obj = next((  # Get the updated vehicle from the returned convoy obj
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.df_state.vehicle_obj['vehicle_id']
        ), None)

        displayable_vehicle_parts = '\n'.join(
            discord_app.cargo_menus.format_part(part) for part in self.df_state.vehicle_obj['parts']
        )

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        description_str = '\n'.join([
            f'# {self.df_state.vendor_obj['name']}',
            f'## {self.df_state.vehicle_obj['name']}',
            f'*{self.df_state.vehicle_obj['description']}*',
            '## Parts',
            displayable_vehicle_parts,
            f'### {self.df_state.vehicle_obj['name']} stats'
        ])
        embed.description = description_str[:3600]  # Limit length
        embed = discord_app.vehicle_menus.df_embed_vehicle_stats(self.df_state, embed, self.df_state.vehicle_obj)

        view = PostMechView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)

class InstallConfirmView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, df_state)
        self.add_item(ConfirmInstallButton(df_state, row=1))

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def remove_part_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=remove_part_vehicle_menu)  # Add this menu to the back stack

    removable_parts = [part for part in df_state.vehicle_obj['parts'] if part['removable']]

    displayable_vehicle_parts = '\n'.join(discord_app.cargo_menus.format_part(part) for part in removable_parts)

    header_embed = df_embed_author(discord.Embed(), df_state)
    header_embed.description = '\n'.join([
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
    ])
    
    parts_embed = discord.Embed(description='\n'.join([
        '## Removable parts',
        displayable_vehicle_parts,
        f'### {df_state.vehicle_obj['name']} stats'
    ]))

    footer_embed = discord.Embed(description=f'## {df_state.vehicle_obj['name']} stats')
    footer_embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, footer_embed, df_state.vehicle_obj)

    view = RemovePartView(df_state, removable_parts)

    await df_state.interaction.response.edit_message(embeds=[header_embed, parts_embed, footer_embed], view=view)

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

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options,
            custom_id='select_part',
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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
        f'### {df_state.vehicle_obj['name']} stats'
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        self.df_state.convoy_obj = await api_calls.remove_part(
            vendor_id=self.df_state.vendor_obj['vendor_id'],
            convoy_id=self.df_state.convoy_obj['convoy_id'],
            vehicle_id=self.df_state.vehicle_obj['vehicle_id'],
            part_id=self.df_state.part_obj['part_id']
        )
        # self.df_state.convoy_obj = remove_items_pending_deletion(self.df_state.convoy_obj)

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
            f'### {self.df_state.vehicle_obj['name']} stats'
        ])
        embed = discord_app.vehicle_menus.df_embed_vehicle_stats(self.df_state, embed, self.df_state.vehicle_obj)

        view = PostMechView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)

    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def scrap_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=scrap_vehicle_menu)  # Add this menu to the back stack

    try:
        scrap_check = await api_calls.check_scrap(df_state.vehicle_obj['vehicle_id'])
    except RuntimeError as e:
        await df_state.interaction.response.send_message(content=e, ephemeral=True)
        return

    scrap_price = scrap_check['salvage_price']
    salvage_part_cargo = scrap_check['salvage_part_cargo']

    displayable_salvage_part_cargo = []
    for cargo in salvage_part_cargo:
        part_strs = '\n'.join([discord_app.cargo_menus.format_part(part) for part in cargo['parts']])
        displayable_salvage_part_cargo.append('\n'.join([
            f'### {cargo['base_name']}',
            f'*{cargo['base_desc']}*',
            part_strs
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
        f'### {df_state.vehicle_obj['name']} stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj)
    embed.description = embed.description[:3600]  # Band-aid fix to truncate this

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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.vendor_scrap_vehicle(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                vehicle_id=self.df_state.vehicle_obj['vehicle_id']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        # self.df_state.convoy_obj = remove_items_pending_deletion(self.df_state.convoy_obj)

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
