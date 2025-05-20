# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, handle_timeout, df_embed_author, validate_interaction, DF_LOGO_EMOJI, DF_GUILD_ID
from discord_app.map_rendering import add_map_to_embed
import                                discord_app.main_menu_menus
import                                discord_app.vendor_menus.vendor_menus
import                                discord_app.vendor_menus.buy_menus
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

# --- LEADERBOARD UTILITY FUNCTIONS ---

def create_condensed_internal_leaderboard(internal_leaderboard_data: dict, allegiance_id: str) -> list[str]:
    """
    Creates a condensed list of user IDs for an internal banner leaderboard display.
    Highlights top 3, and the area around the specified allegiance's user.
    """
    condensed_internal_leaderboard = []
    allegiance_pos = None

    # Sort by leaderboard_position to ensure consistent processing
    sorted_spots = sorted(internal_leaderboard_data.items(), key=lambda item: item[1]['leaderboard_position'])

    for user_id, spot in sorted_spots:  # Find allegiance position
        if spot['allegiance']['allegiance_id'] == allegiance_id:
            allegiance_pos = spot['leaderboard_position']
            break

    if allegiance_pos is None: # Should not happen if allegiance_id is valid
        # Fallback: just take top 5 if user not found for some reason
        return [user_id for user_id, spot in sorted_spots[:5]]

    # Collect user_ids for display
    processed_user_ids = set()

    # Add top 3
    for user_id, spot in sorted_spots:
        if spot['leaderboard_position'] <= 3:
            condensed_internal_leaderboard.append(user_id)
            processed_user_ids.add(user_id)
        else:
            break # Already sorted, so we can break

    if allegiance_pos <= 5:  # Add 4th and 5th place if allegiance is in top 5 and not already added
        for user_id, spot in sorted_spots:
            if 3 < spot['leaderboard_position'] <= 5 and user_id not in processed_user_ids:
                condensed_internal_leaderboard.append(user_id)
                processed_user_ids.add(user_id)
    else: # Allegiance is outside top 5
        # Check if there's a gap between top 3 and user's surrounding positions
        # Ensure condensed_internal_leaderboard is not empty before accessing its last element
        if condensed_internal_leaderboard:
            last_top_pos = internal_leaderboard_data[condensed_internal_leaderboard[-1]]['leaderboard_position']
            if allegiance_pos -1 > last_top_pos + 1:
                condensed_internal_leaderboard.append('…')
        elif allegiance_pos > 1: # If top 3 was empty and user is not #1, ellipsis might be needed
             condensed_internal_leaderboard.append('…')


        for user_id, spot in sorted_spots:  # Add the users around allegiance position
            if spot['leaderboard_position'] in [allegiance_pos - 1, allegiance_pos, allegiance_pos + 1] and \
               user_id not in processed_user_ids:
                condensed_internal_leaderboard.append(user_id)
                processed_user_ids.add(user_id)

    # Ensure unique entries while preserving order for '…'
    final_list = []
    seen = set()
    for item in condensed_internal_leaderboard:
        if item == '…':
            if 'ellipsis' not in seen: # Allow only one ellipsis
                final_list.append(item)
                seen.add('ellipsis')
        elif item not in seen:
            final_list.append(item)
            seen.add(item)
    return final_list


def format_internal_leaderboard_for_display(internal_leaderboard_data: dict, condensed_user_ids: list[str], user_id_to_highlight: str) -> list[str]:
    """ Formats the condensed internal leaderboard data for display, highlighting a specific user. """
    internal_formatted_output = []
    
    # Create a map of position to user_id for easier lookup from condensed_user_ids
    # This assumes condensed_user_ids contains actual user_ids and potentially '...'
    display_order_map = {uid: internal_leaderboard_data[uid] for uid in condensed_user_ids if uid != '…' and uid in internal_leaderboard_data}
    
    # Sort the spots to be displayed by their actual leaderboard position
    sorted_display_spots = sorted(display_order_map.values(), key=lambda x: x['leaderboard_position'])

    last_pos = 0
    # Determine if an ellipsis should be displayed based on its presence in condensed_user_ids
    # and the positions of the surrounding actual entries.
    
    processed_ellipsis = False
    temp_output = []

    for spot_data in sorted_display_spots:
        user_id = next((uid for uid, data in display_order_map.items() if data == spot_data), None)
        if not user_id: continue

        current_pos = spot_data['leaderboard_position']

        # Check if '...' should be inserted before this entry
        if '…' in condensed_user_ids and not processed_ellipsis:
            # Find index of '...' and current user_id in original condensed_user_ids
            try:
                ellipsis_idx = condensed_user_ids.index('…')
                user_idx_in_condensed = condensed_user_ids.index(user_id)
                # If '...' comes before this user_id in condensed_user_ids and creates a visual gap
                if ellipsis_idx < user_idx_in_condensed and current_pos > last_pos + 1 and last_pos != 0:
                    temp_output.append('-# •••')
                    processed_ellipsis = True
            except ValueError:  # user_id might not be in condensed_user_ids if list is malformed
                pass

        position_line = (
            f'{spot_data['leaderboard_position']}. **{spot_data['username']}**'
            if user_id == user_id_to_highlight
            else f'{spot_data['leaderboard_position']}. {spot_data['username']}'
        )
        match spot_data['leaderboard_position']:
            case 1: position_line += '🥇'
            case 2: position_line += '🥈'
            case 3: position_line += '🥉'
        volume_line = f'  - Total volume moved: **{spot_data['allegiance']['stats'].get('total_volume_moved', 0)}L**'
        temp_output.extend([position_line, volume_line])
        last_pos = current_pos

    # If '...' was intended to be at the end (e.g., after top 3, and user is far below)
    if '…' in condensed_user_ids and not processed_ellipsis and condensed_user_ids[-1] == '…':
        temp_output.append('-# •••')

    internal_formatted_output = temp_output
    return internal_formatted_output


def create_condensed_global_leaderboard(global_leaderboard_data: dict, allegiance_banner_id: str) -> list[str]:
    """ Creates a condensed list of banner IDs for a global leaderboard display, focusing on a specific banner. """
    # This is a direct port of the logic from banner_menus, assuming it's sufficient.
    condensed_global_leaderboard = []
    allegiance_pos = None
    
    sorted_banners = sorted(global_leaderboard_data.items(), key=lambda item: item[1]['leaderboard_position'])

    for banner_id, spot in sorted_banners:
        if banner_id == allegiance_banner_id:
            allegiance_pos = spot['leaderboard_position']
        if spot['leaderboard_position'] <= 3:
            if banner_id not in condensed_global_leaderboard:  # Avoid duplicates if allegiance banner is in top 3
                condensed_global_leaderboard.append(banner_id)

    if allegiance_pos is None:
        return []  # Allegiance banner not found

    if allegiance_pos <= 5:
        for banner_id, spot in sorted_banners:
            if 3 < spot['leaderboard_position'] <= 5 and banner_id not in condensed_global_leaderboard:
                condensed_global_leaderboard.append(banner_id)
    else: # Allegiance banner is outside top 5
        # Check if ellipsis is needed
        last_top_pos = 0
        if condensed_global_leaderboard: # If top 3 were added
            # Get the position of the last banner added from top 3
            last_top_banner_id = condensed_global_leaderboard[-1]
            if last_top_banner_id in global_leaderboard_data:
                 last_top_pos = global_leaderboard_data[last_top_banner_id]['leaderboard_position']
        
        if allegiance_pos -1 > last_top_pos + 1 :  # If there's a gap
            condensed_global_leaderboard.append('…')

        for banner_id, spot in sorted_banners:
            if spot['leaderboard_position'] in [allegiance_pos - 1, allegiance_pos, allegiance_pos + 1] and \
               banner_id not in condensed_global_leaderboard:
                condensed_global_leaderboard.append(banner_id)
    
    # Ensure unique entries while preserving order for '…'
    final_list = []
    seen_items = set()
    # Sort by original position before final processing to maintain visual order
    # Need a way to sort '...' appropriately or handle its insertion carefully.
    # For now, rely on the construction logic for order.
    
    # Re-sort based on actual position for items that are not '...'
    # This is tricky because '...' breaks direct sorting.
    # The create_condensed logic should ideally place '...' correctly.
    
    # Simple uniqueness filter, assuming create_condensed handles order
    for item in condensed_global_leaderboard:
        if item == '…':
            if 'ellipsis' not in seen_items:
                final_list.append(item)
                seen_items.add('ellipsis')  # Use a generic key for ellipsis
        elif item not in seen_items:
            final_list.append(item)
            seen_items.add(item)
            
    return final_list


def format_global_leaderboard_for_display(global_leaderboard_data: dict, condensed_banner_ids: list[str], banner_id_to_highlight: str) -> list[str]:
    """Formats the condensed global leaderboard data for display, highlighting a specific banner."""
    global_leaderboard_string = []
    last_pos = 0
    processed_ellipsis = False

    # Filter out '...' for sorting, then re-insert based on condensed_banner_ids logic
    actual_banner_ids_to_display = [bid for bid in condensed_banner_ids if bid != '…' and bid in global_leaderboard_data]
    
    # Sort these actual banner IDs by their leaderboard position
    sorted_banner_spots_data = sorted(
        [global_leaderboard_data[bid] for bid in actual_banner_ids_to_display],
        key=lambda x: x['leaderboard_position']
    )

    # Iterate based on the original condensed_banner_ids to respect '...' placement
    current_sorted_idx = 0
    for item_in_condensed_list in condensed_banner_ids:
        if item_in_condensed_list == '…':
            if not processed_ellipsis : # Add ellipsis only once if multiple were somehow added
                # Check if this ellipsis is logically placed (i.e., creates a visual gap)
                # This is hard to do perfectly without knowing the next actual item's position from condensed_banner_ids
                # A simpler rule: if '...' is present, and we haven't added it, add it.
                # The create_condensed function should be responsible for placing '...' correctly.
                global_leaderboard_string.append('•••')
                processed_ellipsis = True
            continue

        # Find the spot data for the current banner_id from the sorted list
        # This assumes item_in_condensed_list is an actual banner_id here
        if current_sorted_idx < len(sorted_banner_spots_data):
            spot = next((s for s in sorted_banner_spots_data if global_leaderboard_data.get(item_in_condensed_list) == s), None)
            if not spot: # Should not happen if condensed_banner_ids are valid
                # Try to find by matching banner_id if spot object comparison fails due to dict nuances
                if item_in_condensed_list in global_leaderboard_data:
                    spot = global_leaderboard_data[item_in_condensed_list]
                else:
                    continue # Skip if banner_id from condensed list is not in global_leaderboard_data

            # Ensure we are processing in sorted order from sorted_banner_spots_data
            # This loop structure is a bit complex due to '...'. A simpler way might be to iterate sorted_banner_spots_data
            # and decide when to print '...' based on gaps and its presence in condensed_banner_ids.
            # For now, let's use the current spot.

            current_banner_id = item_in_condensed_list # This is the banner_id we are processing

            position_line = (
                f"{spot['leaderboard_position']}. **{spot['name']}**"
                if current_banner_id == banner_id_to_highlight
                else f"{spot['leaderboard_position']}. {spot['name']}"
            )
            match spot['leaderboard_position']:
                case 1: position_line += '🥇'
                case 2: position_line += '🥈'
                case 3: position_line += '🥉'
            volume_line = f"  - Total volume moved: **{spot['stats'].get('total_volume_moved', 0)}L**"
            global_leaderboard_string.extend([position_line, volume_line])
            last_pos = spot['leaderboard_position']
            current_sorted_idx += 1 # Move to the next item in the pre-sorted list
        
    return global_leaderboard_string


def format_top_n_global_leaderboard(leaderboard_data: dict, top_n: int = 10, source_stats_from_archive: bool = False) -> list[str]:
    """
    Formats a global leaderboard to display the top N entries.
    Assumes leaderboard_data is a dict {banner_id: {'leaderboard_position': int, 'name': str, 'stats': ...}}.
    If source_stats_from_archive is True, it will attempt to use the latest stats from entry['stats']['archive'].
    """
    if not leaderboard_data:
        return ['-# No data available.']

    valid_entries = [entry for entry in leaderboard_data.values() if 'leaderboard_position' in entry and 'name' in entry]
    
    sorted_entries = sorted(
        valid_entries,
        key=lambda x: x['leaderboard_position']
    )

    output_lines = []
    for i, entry in enumerate(sorted_entries):
        if i >= top_n:
            if len(sorted_entries) > top_n:
                output_lines.append('-# ...and more!')
            break

        pos = entry['leaderboard_position']
        name = entry['name']
        
        # Determine which stats dictionary to use
        stats_to_use = {}
        raw_stats_field = entry.get('stats') or {}  # Ensure raw_stats_field is a dict, even if entry['stats'] is None

        if source_stats_from_archive:
            archive_data = raw_stats_field.get('archive', {})
            if archive_data:
                # Assuming date keys are sortable (e.g., "YYYY-MM-DD")
                latest_date = max(archive_data.keys(), default=None)
                if latest_date:
                    stats_to_use = archive_data[latest_date]
        # Use the raw_stats_field directly if not sourcing from archive,
        # or if archive sourcing was attempted but yielded no specific stats.
        elif not stats_to_use:  # Fallback if archive sourcing didn't populate
            stats_to_use = raw_stats_field

        line = f'{pos}. {name}'
        if pos == 1: line += ' 🥇'
        elif pos == 2: line += ' 🥈'
        elif pos == 3: line += ' 🥉'
        output_lines.append(line)
        
        volume_moved = stats_to_use.get('total_volume_moved', 0)
        output_lines.append(f'  - Total volume moved: **{volume_moved:,}L**')

    if not output_lines and leaderboard_data:
        return ['-# Leaderboard data found, but could not be formatted (check structure).']
    if not output_lines and not leaderboard_data:
        return ['-# No data available.']
        
    return output_lines


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

        if df_state.interaction.guild and df_state.interaction.guild_id != DF_GUILD_ID:  # If in a different guild and not a DM
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return

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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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

        try:
            self.df_state.user_obj = await api_calls.new_banner(
                user_id=self.df_state.user_obj['user_id'],
                name=self.new_banner_name_input.value,
                description=self.new_banner_description_input.value,
                banner_desc=self.new_banner_physical_description_input.value,
                public=True,
                discord_id=self.df_state.interaction.guild_id
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
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

    embed.description = '\n'.join([
        f'# {banner['name']}',
        f'*{banner['description']}*',
        '### Internal Player leaderboard',
        '\n'.join(format_internal_leaderboard_for_display(
            internal_leaderboard_data=allegiance['banner']['internal_leaderboard'],
            condensed_user_ids=create_condensed_internal_leaderboard(
                internal_leaderboard_data=allegiance['banner']['internal_leaderboard'],
                allegiance_id=allegiance['allegiance_id']
            ),
            user_id_to_highlight=allegiance['user_id']
        )),
        '### Global Banner leaderboard',
        '\n'.join(format_global_leaderboard_for_display(
            global_leaderboard_data=allegiance['banner']['global_leaderboard'],
            condensed_banner_ids=create_condensed_global_leaderboard(
                global_leaderboard_data=allegiance['banner']['global_leaderboard'],
                allegiance_banner_id=allegiance['banner']['banner_id']
            ),
            banner_id_to_highlight=allegiance['banner']['banner_id']
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
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
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await banner_inspect_menu(self.df_state, self.banner)

    async def on_timeout(self):
        await handle_timeout(self.df_state)
