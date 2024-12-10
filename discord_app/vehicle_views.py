# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap

import                                discord

import discord_app.cargo_views
from discord_app               import api_calls, discord_timestamp, df_embed_author, get_user_metadata
from discord_app.map_rendering import add_map_to_embed
from discord_app.nav_menus     import add_nav_buttons

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


async def vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=vehicle_menu)  # Add this menu to the back stack

    part_list = []
    for category, part in df_state.vehicle_obj['parts'].items():
        if not part:  # If the part slot is empty
            part_list.append(f'- {category.replace('_', ' ').capitalize()}\n  - None')
            continue

        part_list.append(discord_app.cargo_views.format_part(part))
    displayable_vehicle_parts = '\n'.join(part_list)

    vehicle_embed = discord.Embed()
    vehicle_embed = df_embed_author(vehicle_embed, df_state)
    vehicle_embed.description = '\n'.join([
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['base_desc']}*',
        '',
        f'Value: **${df_state.vehicle_obj['value']:,}**',
        '### Parts',
        displayable_vehicle_parts,
        '### Stats'
    ])
    vehicle_embed = df_embed_vehicle_stats(df_state, vehicle_embed, df_state.vehicle_obj)

    vehicle_view = VehicleView(df_state=df_state)

    await df_state.interaction.response.edit_message(embed=vehicle_embed, view=vehicle_view, attachments=[])

class VehicleView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        add_nav_buttons(self, self.df_state)

        # self.add_item(VehicleSelect(self.df_state))

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


def df_embed_vehicle_stats(df_state: DFState, embed: discord.Embed, vehicle: dict, new_part: dict=None):
    fields = {
        '💵 Value': ('value', '${:,}', '', 'part_value', ' (${:+})'),
        '🔧 Wear': ('wear', '{}', ' / 100', None, ''),
        '🛡️ AP': ('ap', '{}', f' / {vehicle['max_ap']}', 'max_ap_mod', ' ({:+})'),
        '⛽️ Fuel Efficiency': ('fuel_efficiency', '{}', ' / 100', 'fuel_efficiency_mod', ' ({:+})'),
        '🏎️ Top Speed': ('top_speed', '{}', ' / 100', 'top_speed_mod', ' ({:+})'),
        '🏔️ Off-road Capability': ('offroad_capability', '{}', ' / 100', 'offroad_capability_mod', ' ({:+})'),
        '📦 Cargo Capacity': ('cargo_capacity', '{:,}', ' L', 'cargo_capacity_mod', ' ({:+} L)'),
        '🏋️ Weight Capacity': ('weight_capacity', '{:,}', ' kg', 'weight_capacity_mod', ' ({:+} kg)'),
        '🚛 Towing Capacity': ('towing_capacity', '{:,}', ' kg', 'towing_capacity_mod', ' ({:+} kg)')
    }

    for name, (stat_key, base_format, suffix, mod_key, mod_format) in fields.items():
        # Get the base value, default to 'N/A' if None
        base_value = vehicle.get(stat_key)

        # If base_value is None, assign 'N/A'
        if base_value is None:
            value_str = 'N/A'
        else:
            value_str = base_format.format(base_value)

        # Get the modifier value and apply it if available
        mod_value = new_part.get(mod_key) if new_part and mod_key else None
        if mod_value is not None and value_str != 'N/A':
            value_str += mod_format.format(mod_value)

        value_str += suffix
        
        # Add the formatted field to the embed
        if get_user_metadata(df_state, 'mobile'):
            embed.description += f'\n- {name}: {value_str}'
        else:
            embed.add_field(name=name, value=value_str)

    return embed
