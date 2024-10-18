# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap

import                                discord

from discord_app               import discord_timestamp
from discord_app               import api_calls, discord_timestamp, format_part, df_embed_author, df_embed_vehicle_stats
from discord_app.map_rendering import add_map_to_embed
from discord_app.df_state      import DFState
from discord_app.nav_menus     import add_nav_buttons

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


async def vehicle_menu(df_state: DFState):
    vehicle_embed = discord.Embed()
    vehicle_embed = df_embed_author(vehicle_embed, df_state)
    vehicle_embed.description = '\n'.join([
        # f'# {self.vendor_obj['name']}',
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
        super().__init__(timeout=120)

        add_nav_buttons(self, self.df_state)

        self.add_item(VehicleSelect(self.df_state))

class VehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        options=[
            discord.SelectOption(label=vehicle['name'], value=vehicle['vehicle_id'])
            for vehicle in self.df_state.convoy_obj['vehicles']
        ]
        
        super().__init__(
            placeholder='Select vehicle to inspect',
            options=options,
            custom_id='select_vehicle',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.vehicle_obj = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        await vehicle_menu(self.df_state)
