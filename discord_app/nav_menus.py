# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__           import annotations
import                           discord

import                           discord_app.main_menu_menus
import                           discord_app.convoy_menus
import discord_app.sett_menus
import                           discord_app.vendor_views.vendor_menus

from discord_app.df_state import DFState, DFMenu
from discord_app          import validate_interaction


def add_nav_buttons(view: discord.ui.View, df_state: DFState):
    if 'nav_back_button' not in [item.custom_id for item in view.children]:  # Only add back button if a back button wasn't already added
        view.add_item(NavBackButton(df_state))
    view.add_item(NavMainMenuButton(df_state))
    view.add_item(NavConvoyButton(df_state))
    view.add_item(NavSettButton(df_state))

class NavBackButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if len(self.df_state.back_stack) > 1:
            disabled = False
        else:
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.gray,
            label='⬅ Back',
            disabled=disabled,
            custom_id='nav_back_button',
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction
        await self.df_state.previous_menu()

class NavMainMenuButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.gray,
            label='Main Menu',
            custom_id='nav_main_menu_button',
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        await discord_app.main_menu_menus.main_menu(
            interaction=interaction,
            df_map=self.df_state.map_obj,
            user_cache=self.df_state.user_cache
        )

class NavConvoyButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.gray,
            label='Convoy',
            custom_id='nav_convoy_button',
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction
        await discord_app.convoy_menus.convoy_menu(self.df_state)

class NavSettButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if df_state.sett_obj['sett_type'] == 'dome':
            emoji= '🏙️'
        elif df_state.sett_obj['sett_type'] == 'city' or 'city-state':
            emoji = '🏢'
        elif df_state.sett_obj['sett_type'] == 'military_base':
            emoji = '🪖'
        elif df_state.sett_obj['sett_type'] == 'town':
            emoji = '🏘️'
        else:
            emoji = ''
        

        if df_state.sett_obj:
            label = df_state.sett_obj['name']
            disabled = False
        else:
            label = 'Settlement'
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.gray,
            label=label,
            disabled=disabled,
            custom_id='nav_sett_button',
            emoji = emoji,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction
        self.df_state.vendor_obj = None  # Reset
        await discord_app.sett_menus.sett_menu(self.df_state)
