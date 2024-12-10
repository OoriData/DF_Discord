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
            user_discord_id=None,
            map_obj=None,
            user_obj=None,
            sett_obj=None,
            vendor_obj=None,
            warehouse_obj=None,
            convoy_obj=None,
            vehicle_obj=None,
            cargo_obj=None,
            interaction=None,
            back_stack=None
    ):
        self.user_discord_id = user_discord_id
        self.map_obj = map_obj
        self.user_obj = user_obj
        self.sett_obj = sett_obj
        self.vendor_obj = vendor_obj
        self.warehouse_obj = warehouse_obj
        self.convoy_obj = convoy_obj
        self.vehicle_obj = vehicle_obj
        self.cargo_obj = cargo_obj

        self.interaction: discord.Interaction = interaction

        self.back_stack = back_stack or []

    def append_menu_to_back_stack(self, func, args: dict | None=None):
        if args is None:
            args = {}

        self.back_stack.append(DFMenu(
            func=func,
            args=args
        ))

    async def previous_menu(self):
        current_menu: DFMenu = self.back_stack.pop()  # To be thrown out
        previous_menu: DFMenu = self.back_stack.pop()
        await previous_menu.func(df_state=self, **previous_menu.args)


class DFMenu:
    def __init__(self, func, args):
        self.func = func
        self.args = args
