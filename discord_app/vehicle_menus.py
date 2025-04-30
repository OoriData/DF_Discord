# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional

import                                discord

import discord_app.nav_menus
import discord_app.cargo_menus
from discord_app               import api_calls, handle_timeout, discord_timestamp, df_embed_author, get_user_metadata
from discord_app.map_rendering import add_map_to_embed
import discord_app.nav_menus# from discord_app.nav_menus     import add_nav_buttons

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


def df_embed_vehicle_stats(
        df_state: DFState,
        embed: discord.Embed,
        vehicle: dict,
        new_part: dict | None=None
):
    fields = {
        # 'FIELD_NAME': ('STAT_KEY', '**BASE_FORMAT**', 'SUFFIX', 'MODIFIER_KEY', 'MODIFIER_FORMAT'),
        'Value 💵': ('value', '**${:,}**', None, 'part_value', ' (${:+})'),
        'Cargo Capacity 📦': ('cargo_capacity', '**{:,}**', ' L', 'cargo_capacity_add', ' ({:+} L)'),
        'Weight Capacity 🏋️': ('weight_capacity', '**{:,}**', ' kg', 'weight_capacity_add', ' ({:+} kg)'),
        'Efficiency 🌿': ('efficiency', '**{:.0f}**', ' / {}', 'fuel_efficiency_add', ' ({:+})'),
        'Top Speed 🚀': ('top_speed', '**{:.0f}**', ' / {}', 'top_speed_add', ' ({:+})'),
        'Off-road Capability 🏔️': ('offroad_capability', '**{:.0f}**', ' / {}', 'offroad_capability_add', ' ({:+})'),
        'Weight Class 🥊': ('weight_class', '**{}**', None, None, None),
        'Stat Floor ⌊⌋': ('hard_stat_floor', '**{}**', None, None, None),
        'Stat Soft Cap ⌈⌉': ('soft_stat_cap', '**{}**', None, None, None),
        'Coupling 🚛': ('coupling', '**{}**', None, None, None),
        'Armor Class 🛡️': ('ac', '**{}**', None, 'ac_add', ' ({:+})'),
    }

    # Special-cased "Powered by" field
    if vehicle.get('internal_combustion') and vehicle.get('electric'):
        powered_by = 'fuel ⛽️ and electric 🔋 (hybrid)'
    elif vehicle.get('internal_combustion'):
        powered_by = 'fuel ⛽️'
    elif vehicle.get('electric'):
        powered_by = 'electric 🔋'

    fields = {
        **fields,
        '⚙️ Powertrain': ('_powertrain', '**{}**', None, None, None)
    }
    vehicle = {**vehicle, '_powertrain': powered_by}

    raw_stats = {  # Map vehicle stats to raw stats
        'efficiency': 'raw_efficiency',
        'top_speed': 'raw_top_speed',
        'offroad_capability': 'raw_offroad_capability'
    }

    for name, (stat_key, base_format, suffix, mod_key, mod_format) in fields.items():
        base_value = vehicle.get(stat_key)
        base_value = None if base_value == '' else base_value  # Normalize empty strings to None

        if base_value is None:
            value_str = 'N/A'
        else:
            try:
                value_str = base_format.format(base_value)
            except Exception:
                value_str = str(base_value)

        mod_value = new_part.get(mod_key) if new_part and mod_key else None
        if mod_value is not None and value_str != 'N/A' and mod_format:
            value_str += mod_format.format(mod_value)

        if suffix:
            value_str += suffix.format(vehicle['hard_stat_cap'])

        if stat_key in raw_stats and base_value is not None:
            raw_value = vehicle.get(raw_stats[stat_key])
            if raw_value is not None:
                value_str += f' (*raw: {raw_value}*)'

        if get_user_metadata(df_state, 'mobile'):
            embed.description += f'\n- {name}: {value_str}'
        else:
            embed.add_field(name=name, value=value_str)

    return embed


async def vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=vehicle_menu)  # Add this menu to the back stack

    # Sort the vehicle parts by slot (alphabetically), and then criticality
    sorted_parts = sorted(df_state.vehicle_obj['parts'], key=lambda part: (part['slot'], not part['critical']))

    displayable_vehicle_parts = '\n'.join(
        discord_app.cargo_menus.format_part(part, verbose=False) for part in sorted_parts
    )
    truncated_vehicle_parts = displayable_vehicle_parts[:3750]

    vehicle_embed = discord.Embed()
    vehicle_embed = df_embed_author(vehicle_embed, df_state)
    vehicle_embed.description = '\n'.join([
        f'# {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['description']}*',
        '## Parts',
        truncated_vehicle_parts,
        f'### {df_state.vehicle_obj['name']} stats'
    ])
    vehicle_embed = df_embed_vehicle_stats(df_state, vehicle_embed, df_state.vehicle_obj)

    vehicle_view = VehicleView(df_state=df_state)

    await df_state.interaction.response.edit_message(embed=vehicle_embed, view=vehicle_view, attachments=[])

class VehicleView(discord.ui.View):
    """ Overarching vehicle button menu """
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        # self.add_item(VehicleSelect(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)
