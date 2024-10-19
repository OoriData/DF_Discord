# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__               import annotations
import                               discord

# from discord_app              import main_menu_views, convoy_views
# from discord_app.vendor_views import vendor_views

import discord_app.main_menu_views
import discord_app.convoy_views
import discord_app.vendor_views.vendor_views

from discord_app.df_state     import DFState


def add_nav_buttons(view: discord.ui.View, df_state: DFState):
    # view.add_item(NavBackButton(df_state))
    view.add_item(NavMainMenuButton(df_state))
    view.add_item(NavConvoyButton(df_state))
    view.add_item(NavVendorsButton(df_state))


class NavBackButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.previous_embed:
            disabled = False
        else:
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='⬅ Back',
            disabled=disabled,
            custom_id='nav_back_button',
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=self.df_state.previous_embed,
            view=self.df_state.previous_view,
            attachments=self.df_state.previous_attachments
        )


class NavMainMenuButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Main Menu',
            custom_id='nav_main_menu_button',
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.main_menu_views.main_menu(self.df_state.interaction)


class NavConvoyButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Convoy',
            custom_id='nav_convoy_button',
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.convoy_views.convoy_menu(self.df_state)


class NavVendorsButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.convoy_obj['journey']:  # Cache the tile the convoy is in or smth, and actually check if they are in a tile with settmelent
            disabled = True
        else:
            disabled = False

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Vendors',
            disabled=disabled,
            custom_id='nav_vendor_button',
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        self.df_state.vendor_obj = None  # Reset
        await discord_app.vendor_views.vendor_views.vendor_menu(self.df_state)
