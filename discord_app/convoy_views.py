# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED

import discord
import os
import httpx
import textwrap

from utiloori.ansi_color import ansi_color

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

class SendConvoyConfirmView(discord.ui.View):
    '''Confirm button before sending convoy somewhere'''
    def __init__(
            self,
            interaction: discord.Interaction,
            convoy_obj: dict,
            route: dict
    ):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.convoy_obj = convoy_obj
        self.route = route

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red, custom_id='cancel_send')
    async def cancel_journey_button(self, interaction: discord.Interaction, button: discord.Button):
        # TODO: Make it so that when you press the cancel button it gives you some sort of feedback rather than just deleting the whole thing
        await interaction.response.edit_message(content='Canceled!', delete_after=5, embed=None, view=None)

    @discord.ui.button(label='Confirm Journey', style=discord.ButtonStyle.green, custom_id='confirm_send')
    async def confirm_journey_button(self, interaction: discord.Interaction, button: discord.Button):
        async with httpx.AsyncClient(verify=False) as client:
            journey = await client.patch(
                f'{DF_API_HOST}/convoy/send',
                params={
                    'convoy_id': self.convoy_obj['convoy_id'],
                    'journey_id': self.route['journey']['journey_id']
                }
            )

            if journey.status_code != API_SUCCESS_CODE:
                msg = self.route.json()['detail']
                await interaction.response.send_message(content=msg, ephemeral=True, delete_after=10)
                return

            await interaction.response.send_message('Look at them gooooooo :D')  # TODO: send more information than just 'look at them go'
