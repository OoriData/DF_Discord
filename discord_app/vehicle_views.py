# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap

import                                discord

from discord_app               import discord_timestamp
from discord_app               import api_calls, discord_timestamp, df_embed_author
from discord_app.map_rendering import add_map_to_embed
from discord_app.nav_menus     import add_nav_buttons

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


async def vehicle_menu(df_state: DFState):
    vehicle_embed = discord.Embed()
    vehicle_embed = df_embed_author(vehicle_embed, df_state)
    vehicle_embed.description = '\n'.join([
        f'## {df_state.vehicle_obj['name']}',
        f'*{df_state.vehicle_obj['base_desc']}*',
        '## Stats'
    ])
    vehicle_embed = df_embed_vehicle_stats(vehicle_embed, df_state.vehicle_obj)

    vehicle_view = VehicleView(df_state=df_state)

    await df_state.interaction.response.edit_message(embed=vehicle_embed, view=vehicle_view, attachments=[])


class VehicleView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        add_nav_buttons(self, self.df_state)

        # self.add_item(VehicleSelect(self.df_state))


class VehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Select vehicle to inspect'
        disabled = False
        options=[
            discord.SelectOption(label=vehicle['name'], value=vehicle['vehicle_id'])
            for vehicle in self.df_state.convoy_obj['vehicles']
        ]
        if not options:
            placeholder = 'No vehicles in convoy'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id='select_vehicle',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.vehicle_obj = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        await vehicle_menu(self.df_state)


def df_embed_vehicle_stats(embed: discord.Embed, vehicle: dict, new_part: dict=None):
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
        embed.add_field(name=name, value=value_str)

    return embed
