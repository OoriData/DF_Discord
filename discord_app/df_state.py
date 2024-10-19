# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap

import                                discord

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


class DFState:
    ''' A class to hold the state of the DF Discord menus. '''
    def __init__(
            self,
            user_obj=None,
            vendor_obj=None,
            convoy_obj=None,
            vehicle_obj=None,
            cargo_obj=None,
            interaction=None,
            previous_embed=None,
            previous_view=None,
            previous_attachments=None
    ):
        self.user_obj = user_obj
        self.vendor_obj = vendor_obj
        self.convoy_obj = convoy_obj
        self.vehicle_obj = vehicle_obj
        self.cargo_obj = cargo_obj

        self.interaction: discord.Interaction = interaction
        self.previous_embed: discord.Embed = previous_embed
        self.previous_view: discord.ui.View = previous_view
        self.previous_attachments: discord.Attachment = previous_attachments
