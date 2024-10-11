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

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


class VehicleView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(
            self,
            interaction: discord.Interaction,
            convoy_obj: dict,
            previous_view: discord.ui.View,
            previous_embed: discord.Embed,
            previous_attachments: list[discord.Attachment] = None
    ):
        super().__init__(timeout=120)

        self.interaction = interaction
        self.convoy_obj = convoy_obj
        self.previous_view = previous_view
        self.previous_embed = previous_embed
        self.previous_attachments = previous_attachments or []

        # self.add_item(VehicleSelect(
        #     convoy_obj=convoy_obj,
        #     previous_embed=previous_embed,
        #     previous_view=previous_view
        # ))

    # @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.blurple, custom_id='previous_menu', row=0)
    # async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
    #     await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view, attachments=self.previous_attachments)


class VehicleSelect(discord.ui.Select):
    def __init__(self, convoy_obj, previous_embed, previous_view, previous_attachments=None):
        options=[
            discord.SelectOption(label=vehicle['name'], value=vehicle['vehicle_id'])
            for vehicle in convoy_obj['vehicles']
        ]
        
        super().__init__(
            placeholder='Select vehicle to inspect',
            options=options,
            custom_id='select_vehicle',
            row=2
        )

        self.convoy_obj = convoy_obj
        self.previous_embed = previous_embed
        self.previous_view = previous_view
        self.previous_attachments = previous_attachments or []

    async def callback(self, interaction: discord.Interaction):
        selected_vehicle = next((
            v for v in self.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        vehicle_embed = discord.Embed()
        vehicle_embed = df_embed_author(vehicle_embed, self.convoy_obj, interaction.user)
        vehicle_embed.description = '\n'.join([
            # f'# {self.vendor_obj['name']}',
            f'## {selected_vehicle['name']}',
            f'*{selected_vehicle['base_desc']}*',
            
            '## Stats'
        ])
        vehicle_embed = df_embed_vehicle_stats(vehicle_embed, selected_vehicle)

        vehicle_view = VehicleView(
            interaction=interaction,
            convoy_obj=self.convoy_obj,
            previous_embed=self.previous_embed,
            previous_view=self.previous_view,
            previous_attachments=self.previous_attachments
        )

        # await interaction.response.edit_message(embed=vehicle_embed, view=vehicle_view, attachments=[])
        await interaction.response.send_message(embed=vehicle_embed, view=vehicle_view, ephemeral=True)
