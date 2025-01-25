# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, handle_timeout, df_embed_author, add_tutorial_embed, get_user_metadata, validate_interaction, DF_LOGO_EMOJI
from discord_app.map_rendering import add_map_to_embed
import                                discord_app.main_menu_menus
import                                discord_app.vendor_views.vendor_menus
import                                discord_app.vendor_views.buy_menus
import                                discord_app.warehouse_menus
import                                discord_app.nav_menus
import                                discord_app.warehouse_menus
from discord_app.df_state      import DFState


async def banner_menu(df_state: DFState, follow_on_embeds: list[discord.Embed] | None = None, edit: bool=True):
    if df_state.convoy_obj:
        df_state.append_menu_to_back_stack(func=banner_menu)  # Add this menu to the back stack
    if df_state.sett_obj:
        df_state.sett_obj['banner'] = await api_calls.get_settlement_banner(df_state.sett_obj['sett_id'])

    follow_on_embeds = [] if follow_on_embeds is None else follow_on_embeds

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    if df_state.user_obj['civic_allegiance']:
        civic_allegiance = df_state.user_obj['civic_allegiance']
        civic_banner_info = '\n'.join([
            f'- **{civic_allegiance['banner']['name']}**',
            f'- *{civic_allegiance['banner']['description']}*',
        ])
    else:
        civic_banner_info = '- N/a'

    if df_state.user_obj['guild_allegiance']:
        guild_allegiance = df_state.user_obj['guild_allegiance']
        guild_banner_info = '\n'.join([
            f'- **{guild_allegiance['banner']['name']}**',
            f'- *{guild_allegiance['banner']['description']}*',
        ])
    else:
        guild_banner_info = '- N/a'

    if df_state.user_obj['syndicate_allegiance']:
        syndicate_allegiance = df_state.user_obj['syndicate_allegiance']
        syndicate_banner_info = '\n'.join([
            f'- **{syndicate_allegiance['banner']['name']}**',
            f'- *{syndicate_allegiance['banner']['description']}*',
        ])
    else:
        syndicate_banner_info = '- N/a'

    embed.description = '\n'.join([
        '# Banners',
        '### Civic banner',
        civic_banner_info,
        '### Guild banner',
        guild_banner_info,
        '### Syndicate banner',
        syndicate_banner_info,
    ])

    embeds = [embed, *follow_on_embeds]

    view = BannerView(df_state)

    if edit:
        if df_state.interaction.response.is_done():
            og_message = await df_state.interaction.original_response()
            await df_state.interaction.followup.edit_message(og_message.id, embeds=embeds, view=view, attachments=[])
        else:
         await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=embed, view=view)

class BannerView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        if df_state.convoy_obj:
            self.clear_items()
            discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        allegiance_types = ['civic', 'guild', 'syndicate']

        for row, allegiance_type in enumerate(allegiance_types, start=1):
            allegiance = self.df_state.user_obj.get(f'{allegiance_type}_allegiance')
            if allegiance:
                self.add_item(BannerButton(
                    df_state=self.df_state,
                    banner_obj=allegiance['banner'],
                    row=row
                ))
            else:
                self.add_item(discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    label=f'No {allegiance_type} banner',
                    disabled=True,
                    row=row
                ))

        if df_state.sett_obj:
            sett_banner = df_state.sett_obj['banner']
            civic_allegiance = df_state.user_obj.get('civic_allegiance')

            # Check if there is no civic allegiance or the banner IDs differ
            if not civic_allegiance or civic_allegiance.get('banner', {}).get('banner_id') != sett_banner['banner_id']:
                self.add_item(ProspectiveBannerButton(
                    df_state=self.df_state,
                    banner_obj=sett_banner,
                    row=1
                ))

    @discord.ui.button(label='Return to Main Menu', style=discord.ButtonStyle.gray, row=0)
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction
        await discord_app.main_menu_menus.main_menu(
            interaction=interaction,
            df_map=self.df_state.map_obj,
            user_cache=self.df_state.user_cache,
            edit=False
        )
    
    async def on_timeout(self):
        await handle_timeout(self.df_state)

class BannerButton(discord.ui.Button):
    def __init__(self, df_state: DFState, banner_obj: dict, row: int=1):
        self.df_state = df_state
        self.banner_obj = banner_obj

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=banner_obj['name'],
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        # await discord_app.warehouse_menus.warehouse_menu(self.df_state)


class ProspectiveBannerButton(discord.ui.Button):
    def __init__(self, df_state: DFState, banner_obj: dict, row: int=1):
        self.df_state = df_state
        self.banner_obj = banner_obj

        super().__init__(
            style=discord.ButtonStyle.red,
            label=f'Join {banner_obj['name']}',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        self.df_state.user_obj = await api_calls.form_allegiance(
            self.df_state.user_obj['user_id'],
            banner_id=self.banner_obj['banner_id']
        )

        await banner_menu(self.df_state)
