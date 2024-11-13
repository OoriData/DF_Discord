# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, df_embed_author, add_tutorial_embed
from discord_app.map_rendering import add_map_to_embed

from discord_app.vendor_views.vendor_views import SERVICE_KEYS
import discord_app.vendor_views.vendor_views
import discord_app.vendor_views.buy_menus
import discord_app.nav_menus

from discord_app.df_state      import DFState

async def sett_menu(df_state: DFState, edit: bool=True):
    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    tile_obj = await api_calls.get_tile(df_state.convoy_obj['x'], df_state.convoy_obj['y'])
    if not tile_obj['settlements']:
        await df_state.interaction.response.send_message(content='There aint no settle ments here dawg!!!!!', ephemeral=True, delete_after=10)
        return
    df_state.sett_obj = tile_obj['settlements'][0]
    
    vendor_displayables = []
    for vendor in df_state.sett_obj['vendors']:
        displayable_services = []
        for key in list(SERVICE_KEYS.keys()):
            if vendor[key]:
                displayable_services.append(f'  - {SERVICE_KEYS[key][0]}')

        vendor_displayables.append('\n'.join([
            f'- **{vendor['name']}**',
            '\n'.join(displayable_services)
        ]))
    
    embed.description = '\n'.join([
        f'## {df_state.sett_obj['name']}',
        '\n'.join(vendor_displayables),
        'Select a vendor:'
    ])

    embeds = [embed]
    embeds = add_tutorial_embed(embeds, df_state)

    view = SettView(df_state, df_state.sett_obj['vendors'])

    if edit:
        await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=embed, view=view)


class SettView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState, vendors):
        self.df_state = df_state
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(discord_app.vendor_views.buy_menus.TopUpButton(self.df_state, vendors))
        # self.add_item(WarehouseButton)
        self.add_item(VendorSelect(self.df_state, vendors, row=3))

        user_metadata = self.df_state.convoy_obj.get('user_metadata')  # TUTORIAL BUTTON DISABLING
        tutorial_stage = user_metadata.get('tutorial') if user_metadata else None
        if tutorial_stage in {1, 2, 3, 4}:
            for item in self.children:
                match tutorial_stage:
                    case 1 | 2 | 4:
                        item.disabled = item.custom_id != 'select_vendor'
                    case 3:
                        item.disabled = item.custom_id != 'top_up_button'

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


class NavSettButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.convoy_obj['journey']:  # Cache the tile the convoy is in or smth, and actually check if they are in a tile with settmelent
            label = 'Settlement'
            disabled = True
        else:
            label = df_state.sett_obj['name']
            disabled = False

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
            custom_id='nav_sett_button',
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.warehouse_menus.warehouse_menu(self.df_state)

    

class VendorSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, vendors, row: int=1):
        self.df_state = df_state
        self.vendors = vendors

        options=[
            discord.SelectOption(label=vendor['name'], value=vendor['vendor_id'])
            for vendor in self.vendors
        ]
        
        super().__init__(
            placeholder='Select vendor to visit',
            options=options,
            custom_id='select_vendor',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.vendor_obj = next((
            v for v in self.vendors
            if v['vendor_id'] == self.values[0]
        ), None)

        await discord_app.vendor_views.vendor_views.vendor_menu(self.df_state)