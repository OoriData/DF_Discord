# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, handle_timeout, df_embed_author, add_tutorial_embed, get_user_metadata, validate_interaction, DF_LOGO_EMOJI, get_vendor_emoji
from discord_app.map_rendering import add_map_to_embed
import                                discord_app.vendor_views.vendor_menus
import                                discord_app.vendor_views.buy_menus
import                                discord_app.warehouse_menus
import                                discord_app.nav_menus
import                                discord_app.warehouse_menus
import                                discord_app.banner_menus
from discord_app.df_state      import DFState


async def sett_menu(df_state: DFState, follow_on_embeds: list[discord.Embed] | None = None, edit: bool=True):
    df_state.append_menu_to_back_stack(func=sett_menu)  # Add this menu to the back stack

    follow_on_embeds = [] if follow_on_embeds is None else follow_on_embeds

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    tile_obj = await api_calls.get_tile(df_state.convoy_obj['x'], df_state.convoy_obj['y'])
    if not tile_obj['settlements']:
        await df_state.interaction.response.send_message(content='There aint no settle ments here dawg!!!!!', ephemeral=True, delete_after=10)
        return
    df_state.sett_obj = tile_obj['settlements'][0]
    embed.description = f'*{df_state.sett_obj['base_desc']}*' if df_state.sett_obj['base_desc'] else ''

    df_state.warehouse_obj = next((
        w for w in df_state.user_obj['warehouses']
        if w['sett_id'] == df_state.sett_obj['sett_id']
    ), None)
    if df_state.warehouse_obj:
        embed.description += '\n' + '\n'.join([
            f'# {df_state.sett_obj['name']} Warehouse',
            await discord_app.warehouse_menus.warehouse_storage_md(df_state.warehouse_obj)
        ])
    
    vendor_displayables = []  # TODO: make these more better
    for vendor in df_state.sett_obj['vendors']:
        displayable_services = []

        deliverable_cargo = [cargo for cargo in vendor['cargo_inventory'] if cargo['recipient']]
        if deliverable_cargo:
            displayable_services.append(f'- {len(deliverable_cargo)} deliverable cargo')

        RESOURCES = ['fuel', 'water', 'food']
        for key in RESOURCES:
            if vendor[key]:
                displayable_services.append(f'- {key.capitalize()}')

            resource_cargo = [cargo for cargo in vendor['cargo_inventory'] if cargo[key]]
            if resource_cargo:
                displayable_services.append(f'  - {len(resource_cargo)} {key.capitalize()} container(s)')

        if vendor['vehicle_inventory']:
            displayable_services.append(f'- {len(vendor['vehicle_inventory'])} vehicles')

        if vendor['repair_price']:
            displayable_services.append('- Mechanic services')

        part_cargo = [cargo for cargo in vendor['cargo_inventory'] if cargo['parts']]
        if part_cargo:
            displayable_services.append(f'- {len(part_cargo)} upgrade part(s)')

        vendor_displayables.append('\n'.join([
            f'## {vendor['name']}',
            '\n'.join(displayable_services)
        ]))
    
    embed.description += '\n' + '\n'.join([
        f'# {df_state.sett_obj['name']} vendors',
        '\n'.join(vendor_displayables)
    ])

    embeds = [embed, *follow_on_embeds]
    embeds = add_tutorial_embed(embeds, df_state)

    view = SettView(df_state, df_state.sett_obj['vendors'])

    if edit:
        if df_state.interaction.response.is_done():
            og_message = await df_state.interaction.original_response()
            await df_state.interaction.followup.edit_message(og_message.id, embeds=embeds, view=view, attachments=[])
        else:
         await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=embed, view=view)

class SettView(discord.ui.View):
    """ Overarching settlement button menu """
    def __init__(self, df_state: DFState, vendors):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(discord_app.vendor_views.buy_menus.TopUpButton(self.df_state, sett_menu))
        self.add_item(WarehouseButton(self.df_state))
        self.add_item(SettBannerButton(self.df_state))
        self.add_item(VendorSelect(self.df_state, vendors, row=2))

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4}:
            for item in self.children:
                match tutorial_stage:
                    case 1 | 2 | 4:
                        item.disabled = item.custom_id not in (
                            'nav_back_button',
                            'nav_sett_button',
                            'select_vendor'
                        )
                    case 3:
                        item.disabled = item.custom_id not in (
                            'nav_back_button',
                            'nav_sett_button',
                            'top_up_button'
                        )

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class WarehouseButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.warehouse_obj is not None:
            emoji = '🏭'
        else:
            emoji = '📦'
        
        label = 'Warehouse'
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            custom_id='warehouse_button',
            emoji=emoji,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        local_warehouse = next((
            w for w in self.df_state.user_obj['warehouses']
            if w['sett_id'] == self.df_state.sett_obj['sett_id']
        ), None)
        if local_warehouse:
            self.df_state.warehouse_obj = await api_calls.get_warehouse(local_warehouse['warehouse_id'])

        await discord_app.warehouse_menus.warehouse_menu(self.df_state)

class SettBannerButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        label = 'Banner'
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            custom_id='sett_banner_button',
            emoji='🎌',
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        await discord_app.banner_menus.banner_menu(self.df_state)

class VendorSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, vendors, row: int=1):
        self.df_state = df_state
        self.vendors = vendors

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL



        if tutorial_stage == 1:
            options=[
                discord.SelectOption(
                    label=vendor['name'],
                    value=vendor['vendor_id'],
                    emoji=DF_LOGO_EMOJI if 'Dealership' in vendor['name'] else None  # Add the tutorial emoji if dealership, else don't
                )
                for vendor in self.vendors
            ]
        elif tutorial_stage in [2, 4]:
            options=[
                discord.SelectOption(
                    label=vendor['name'],
                    value=vendor['vendor_id'],
                    emoji=DF_LOGO_EMOJI if 'Market' in vendor['name'] else None  # Add the tutorial emoji if dealership, else don't
                )
                for vendor in self.vendors
            ]
        else:  # Not in tutorial
            options=[
                discord.SelectOption(
                    label=f'{vendor['name']}',
                    value=vendor['vendor_id'],
                    emoji= '🔧' if 'Mechanic' in vendor['name'] else get_vendor_emoji(vendor)
                )
                for vendor in self.vendors
            ]
        
        super().__init__(
            placeholder='Select vendor to visit',
            options=options,
            custom_id='select_vendor',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        self.df_state.vendor_obj = next((
            v for v in self.vendors
            if v['vendor_id'] == self.values[0]
        ), None)

        await discord_app.vendor_views.vendor_menus.vendor_menu(self.df_state)
