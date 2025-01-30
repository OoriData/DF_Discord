# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, handle_timeout, df_embed_author, validate_interaction, DF_LOGO_EMOJI, DF_GUILD_ID
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
    if df_state.sett_obj:  # If there is a settlement's civic banner to join
        df_state.sett_obj['banner'] = await api_calls.get_settlement_banner(df_state.sett_obj['sett_id'])
    
    server_banner = None
    if df_state.interaction.guild_id != DF_GUILD_ID:  # If in a different guild
        try:
            server_banner = await api_calls.get_banner_by_discord_id(df_state.interaction.guild_id)
        except RuntimeError as e:
            server_banner = None

    follow_on_embeds = [] if follow_on_embeds is None else follow_on_embeds

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    if df_state.user_obj['civic_allegiance']:
        civic_allegiance = next(
            a for a in df_state.user_obj['allegiances']
            if a['allegiance_id'] == df_state.user_obj['civic_allegiance']['allegiance_id']
        )

        civic_allegiance['banner']['internal_leaderboard'] = await api_calls.get_banner_internal_leaderboard(
            civic_allegiance['banner']['banner_id']
        )
        internal_leaderboard_position = civic_allegiance['banner']['internal_leaderboard'][df_state.user_obj['user_id']]['leaderboard_position']
        civic_allegiance['banner']['global_leaderboard'] = await api_calls.get_banner_global_leaderboard(
            civic_allegiance['banner']['banner_id']
        )
        global_leaderboard_position = civic_allegiance['banner']['global_leaderboard'][civic_allegiance['banner']['banner_id']]['leaderboard_position']

        civic_banner_info = '\n'.join([
            f'- **{civic_allegiance['banner']['name']}**',
            f'  - Total volume moved: **{civic_allegiance['stats'].get('total_volume_moved', 0)}L**',
            f'  - Total weight moved: **{civic_allegiance['stats'].get('total_weight_moved', 0)}kg**',
            f'  - Total value moved: **${civic_allegiance['stats'].get('total_value_moved', 0)}**',
            f'  - {df_state.user_obj['username']} leaderboard position: **{internal_leaderboard_position}**',
            f'  - Global civic leaderboard position: **{global_leaderboard_position}**',
        ])
    else:
        civic_banner_info = '- N/a'

    if df_state.user_obj['guild_allegiance']:
        guild_allegiance = next(
            a for a in df_state.user_obj['allegiances']
            if a['allegiance_id'] == df_state.user_obj['guild_allegiance']['allegiance_id']
        )

        guild_allegiance['banner']['internal_leaderboard'] = await api_calls.get_banner_internal_leaderboard(
            guild_allegiance['banner']['banner_id']
        )
        internal_leaderboard_position = guild_allegiance['banner']['internal_leaderboard'][df_state.user_obj['user_id']]['leaderboard_position']
        guild_allegiance['banner']['global_leaderboard'] = None

        guild_banner_info = '\n'.join([
            f'- **{guild_allegiance['banner']['name']}**',
            f'  - Total volume moved: **{guild_allegiance['stats'].get('total_volume_moved', 0)}L**',
            f'  - Total weight moved: **{guild_allegiance['stats'].get('total_weight_moved', 0)}kg**',
            f'  - Total value moved: **${guild_allegiance['stats'].get('total_value_moved', 0)}**',
            f'  - {df_state.user_obj['username']} leaderboard position: **{internal_leaderboard_position}**',
        ])
    else:
        guild_banner_info = '- N/a'

    if df_state.user_obj['syndicate_allegiance']:
        syndicate_allegiance = next(
            a for a in df_state.user_obj['allegiances']
            if a['allegiance_id'] == df_state.user_obj['syndicate_allegiance']['allegiance_id']
        )

        syndicate_allegiance['banner']['internal_leaderboard'] = await api_calls.get_banner_internal_leaderboard(
            syndicate_allegiance['banner']['banner_id']
        )
        internal_leaderboard_position = syndicate_allegiance['banner']['internal_leaderboard'][df_state.user_obj['user_id']]['leaderboard_position']
        syndicate_allegiance['banner']['global_leaderboard'] = await api_calls.get_banner_global_leaderboard(
            syndicate_allegiance['banner']['banner_id']
        )
        global_leaderboard_position = syndicate_allegiance['banner']['global_leaderboard'][syndicate_allegiance['banner']['banner_id']]['leaderboard_position']

        syndicate_banner_info = '\n'.join([
            f'- **{syndicate_allegiance['banner']['name']}**',
            f'  - Total volume moved: **{syndicate_allegiance['stats'].get('total_volume_moved', 0)}L**',
            f'  - Total weight moved: **{syndicate_allegiance['stats'].get('total_weight_moved', 0)}kg**',
            f'  - Total value moved: **${syndicate_allegiance['stats'].get('total_value_moved', 0)}**',
            f'  - {df_state.user_obj['username']}\'s leaderboard position: **{internal_leaderboard_position}**',
            f'  - Global syndicate leaderboard position: **{global_leaderboard_position}**',
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

    view = BannerView(df_state, server_banner)

    if edit:
        if df_state.interaction.response.is_done():
            og_message = await df_state.interaction.original_response()
            await df_state.interaction.followup.edit_message(og_message.id, embeds=embeds, view=view, attachments=[])
        else:
            await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=embed, view=view)

class BannerView(discord.ui.View):
    def __init__(self, df_state: DFState, server_banner: dict):
        self.df_state = df_state
        self.server_banner = server_banner
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

        if df_state.sett_obj:  # If there is a settlement's civic banner to join
            sett_banner = df_state.sett_obj['banner']
            civic_allegiance = df_state.user_obj.get('civic_allegiance')

            if (  # Check if the user has no civic allegiance or a different allegiance
                not civic_allegiance
                or civic_allegiance.get('banner', {}).get('banner_id') != sett_banner['banner_id']
            ):
                self.add_item(ProspectiveBannerButton(
                    df_state=self.df_state,
                    banner_obj=sett_banner,
                    row=1
                ))

        if df_state.interaction.guild_id != DF_GUILD_ID:  # If in a different guild
            syndicate_allegiance = df_state.user_obj.get('syndicate_allegiance')

            if not self.server_banner:  # If the server has no banner
                self.add_item(NewSyndicateBannerButton(
                    df_state=self.df_state,
                    row=3
                ))
            elif (  # Check if user has no syndicate allegiance or a different allegiance
                not syndicate_allegiance
                or syndicate_allegiance.get('banner', {}).get('banner_id') != self.server_banner['banner_id']
            ):
                self.add_item(ProspectiveBannerButton(
                    df_state=self.df_state,
                    banner_obj=self.server_banner,
                    row=3
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

        await banner_inspect_menu(self.df_state, self.banner_obj)

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

        try:
            self.df_state.user_obj = await api_calls.form_allegiance(
                self.df_state.user_obj['user_id'],
                banner_id=self.banner_obj['banner_id']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        await banner_menu(self.df_state)

class NewSyndicateBannerButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.green,
            label='Create banner',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        await self.df_state.interaction.response.send_modal(NewBannerModal(self.df_state))

class NewBannerModal(discord.ui.Modal):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(title='Sign up for Desolate Frontiers')

        self.new_banner_name_input = discord.ui.TextInput(
            label='New banner name',
            style=discord.TextStyle.short,
            required=True,
            default=self.df_state.interaction.guild.name,
            placeholder=self.df_state.interaction.guild.name,
            max_length=32,
            custom_id='new_banner_name'
        )
        self.add_item(self.new_banner_name_input)

        self.new_banner_description_input = discord.ui.TextInput(
            label='New banner description',
            style=discord.TextStyle.long,
            required=True,
            placeholder='The description and mission statement of your new banner',
            max_length=512,
            custom_id='new_banner_description'
        )
        self.add_item(self.new_banner_description_input)

        self.new_banner_physical_description_input = discord.ui.TextInput(
            label='New banner (physical) description',
            style=discord.TextStyle.long,
            required=True,
            placeholder='The description of the actual flag/tapestry/etc that convoys will fly when representing this banner',
            max_length=512,
            custom_id='new_banner_physical_desc'
        )
        self.add_item(self.new_banner_physical_description_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.user_obj = await api_calls.new_banner(
            user_id=self.df_state.user_obj['user_id'],
            name=self.new_banner_name_input.value,
            description=self.new_banner_description_input.value,
            banner_desc=self.new_banner_physical_description_input.value,
            public=True,
            discord_id=self.df_state.interaction.guild_id
        )

        await banner_menu(self.df_state)


async def banner_inspect_menu(df_state: DFState, banner: dict):
    if df_state.convoy_obj:
        df_state.append_menu_to_back_stack(func=banner_inspect_menu)  # Add this menu to the back stack

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    allegiance = next((
        a for a in df_state.user_obj['allegiances']
        if a['banner']['banner_id'] == banner['banner_id']
    ), None)

    def create_condensed_internal_leaderboard(internal_leaderboard_data, allegiance_id):
        condensed_internal_leaderboard = []
        allegiance_pos = None

        for user_id, spot in internal_leaderboard_data.items():  # Find allegiance position and collect top 3 users
            if spot['allegiance']['allegiance_id'] == allegiance_id:  # Find the allegiance (and therefor user) we're looking for
                allegiance_pos = spot['leaderboard_position']
            if spot['leaderboard_position'] <= 3:
                condensed_internal_leaderboard.append(user_id)  # Add top 3 user IDs

        if allegiance_pos is None:
            return []  # Return empty if allegiance not found

        if allegiance_pos <= 5:  # Add 4th and 5th place if allegiance is in top 5
            for user_id, spot in internal_leaderboard_data.items():
                if 3 < spot['leaderboard_position'] <= 5:
                    condensed_internal_leaderboard.append(user_id)
        else:
            condensed_internal_leaderboard.append('...')  # Add ellipsis
            for user_id, spot in internal_leaderboard_data.items():  # Add the users around allegiance position
                if spot['leaderboard_position'] in [allegiance_pos - 1, allegiance_pos, allegiance_pos + 1]:
                    condensed_internal_leaderboard.append(user_id)

        return condensed_internal_leaderboard

    def format_internal_leaderboard_for_display(internal_leaderboard_data, condensed_allegiance_ids):
        internal_formatted_output = []
        last_pos = 0
        added_ellipsis = False

        for user_id, spot in internal_leaderboard_data.items():  # First pass - process actual user entries
            if user_id in condensed_allegiance_ids:
                # If we haven't added ellipsis yet and we're jumping from ≤3 to >3
                if '...' in condensed_allegiance_ids and last_pos <= 3 and spot['leaderboard_position'] > 3 and not added_ellipsis:
                    internal_formatted_output.append('-# •••')
                    added_ellipsis = True

                position_line = (
                    f'{spot['leaderboard_position']}. **{spot['username']}**'
                    if user_id == allegiance['user_id']
                    else f'{spot['leaderboard_position']}. {spot['username']}'
                )  # Bold the name if it's the current user
                match spot['leaderboard_position']:
                    case 1:
                        position_line += '🥇'
                    case 2:
                        position_line += '🥈'
                    case 3:
                        position_line += '🥉'
                volume_line = f'  - Total volume moved: **{spot['allegiance']['stats'].get('total_volume_moved', 0)}L**'
                internal_formatted_output.extend([position_line, volume_line])
                last_pos = spot['leaderboard_position']

        return internal_formatted_output

    def create_condensed_global_leaderboard(global_leaderboard_data, allegiance_banner_id):
        condensed_global_leaderboard = []
        allegiance_pos = None

        for banner_id, spot in global_leaderboard_data.items():  # Find allegiance position and collect top 3 banners
            if banner_id == allegiance_banner_id:
                allegiance_pos = spot['leaderboard_position']
            if spot['leaderboard_position'] <= 3:
                condensed_global_leaderboard.append(banner_id)  # Add top 3 banner IDs

        if allegiance_pos is None:
            return []  # Return empty if allegiance not found

        if allegiance_pos <= 5:  # Add 4th and 5th place if allegiance is in top 5
            for banner_id, spot in global_leaderboard_data.items():
                if 3 < spot['leaderboard_position'] <= 5:
                    condensed_global_leaderboard.append(banner_id)
        else:
            condensed_global_leaderboard.append('...')  # Add ellipsis
            for banner_id, spot in global_leaderboard_data.items():  # Add the banners around allegiance position
                if spot['leaderboard_position'] in [allegiance_pos - 1, allegiance_pos, allegiance_pos + 1]:
                    condensed_global_leaderboard.append(banner_id)

        return condensed_global_leaderboard

    def format_global_leaderboard_for_display(global_leaderboard_data, condensed_banner_ids):
        global_leaderboard_string = []
        last_pos = 0
        added_ellipsis = False

        for banner_id, spot in global_leaderboard_data.items():  # First pass - process actual banner entries
            if banner_id in condensed_banner_ids:
                # If we haven't added ellipsis yet and we're jumping from ≤3 to >3
                if '...' in condensed_banner_ids and last_pos <= 3 and spot['leaderboard_position'] > 3 and not added_ellipsis:
                    global_leaderboard_string.append('•••')
                    added_ellipsis = True

                position_line = (
                    f'{spot['leaderboard_position']}. **{spot['name']}**'
                    if banner_id == allegiance['banner']['banner_id']
                    else f'{spot['leaderboard_position']}. {spot['name']}'
                )  # Bold the name if it's the allegiance banner
                match spot['leaderboard_position']:
                    case 1:
                        position_line += '🥇'
                    case 2:
                        position_line += '🥈'
                    case 3:
                        position_line += '🥉'
                volume_line = f'  - Total volume moved: **{spot['stats'].get('total_volume_moved', 0)}L**'
                global_leaderboard_string.extend([position_line, volume_line])
                last_pos = spot['leaderboard_position']

        return global_leaderboard_string

    embed.description = '\n'.join([
        f'# {banner['name']}',
        f'*{banner['description']}*',
        '### Internal Player leaderboard',
        '\n'.join(format_internal_leaderboard_for_display(
            internal_leaderboard_data=allegiance['banner']['internal_leaderboard'],
            condensed_allegiance_ids=create_condensed_internal_leaderboard(
                internal_leaderboard_data=allegiance['banner']['internal_leaderboard'],
                allegiance_id=allegiance['allegiance_id']
            )
        )),
        '### Global Banner leaderboard',
        '\n'.join(format_global_leaderboard_for_display(
            global_leaderboard_data=allegiance['banner']['global_leaderboard'],
            condensed_banner_ids=create_condensed_global_leaderboard(
                global_leaderboard_data=allegiance['banner']['global_leaderboard'],
                allegiance_banner_id=allegiance['banner']['banner_id']
            )
        )),
    ])

    embeds = [embed]

    view = BannerInspectView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])

class BannerInspectView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        if df_state.convoy_obj:
            self.clear_items()
            discord_app.nav_menus.add_nav_buttons(self, self.df_state)

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.gray, row=0)
    async def banner_inspect_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        await banner_menu(self.df_state)
    
    async def on_timeout(self):
        await handle_timeout(self.df_state)


async def leaderboard_inspect_menu(df_state: DFState, banner: dict):
    if df_state.convoy_obj:
        df_state.append_menu_to_back_stack(func=leaderboard_inspect_menu)  # Add this menu to the back stack
    
    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)

    allegiance = next((
        a for a in df_state.user_obj['allegiances']
        if a['banner']['banner_id'] == banner['banner_id']
    ), None)

    embed.description = '\n'.join([
        f'# {banner['name']}',
        f'*{banner['description']}*',
    ])

    if allegiance:
        internal_leaderboard_position = allegiance['banner']['internal_leaderboard'][df_state.user_obj['user_id']]['leaderboard_position']
        global_leaderboard_position = allegiance['banner']['global_leaderboard'][allegiance['banner']['banner_id']]['leaderboard_position']

        allegiance_stats = '\n'.join([
            '### Leaderboard',
            f'- Total volume moved: **{allegiance['stats'].get('total_volume_moved', 0)}L**',
            f'- Total weight moved: **{allegiance['stats'].get('total_weight_moved', 0)}kg**',
            f'- Total value moved: **${allegiance['stats'].get('total_value_moved', 0)}**',
            f'- {df_state.user_obj['username']}\'s leaderboard position: **{internal_leaderboard_position}**',
            f'- Global syndicate leaderboard position: **{global_leaderboard_position}**',
        ])
        embed.description += '\n' + allegiance_stats

    embeds = [embed]

    view = LeaderboardInspectView(df_state)

    await df_state.interaction.response.edit_message(embeds=embeds, view=view, attachments=[])

class LeaderboardInspectView(discord.ui.View):
    def __init__(self, df_state: DFState, banner):
        self.df_state = df_state
        self.banner = banner
        super().__init__(timeout=600)

        if df_state.convoy_obj:
            self.clear_items()
            discord_app.nav_menus.add_nav_buttons(self, self.df_state)

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.gray, row=0)
    async def leaderboard_inspect_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        await banner_inspect_menu(self.df_state, self.banner)
    
    async def on_timeout(self):
        await handle_timeout(self.df_state)
