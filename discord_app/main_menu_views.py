# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap
import                                asyncio

import                                discord

from discord_app               import discord_timestamp
from discord_app               import api_calls, convoy_views, discord_timestamp, df_embed_author
from discord_app.map_rendering import add_map_to_embed

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


async def main_menu(interaction: discord.Interaction, edit: bool=True):
    if not edit:
        await interaction.response.defer()

    try:
        user_obj = await api_calls.get_user_by_discord(interaction.user.id)
    except RuntimeError as e:
        # print(f'user not registered: {e}')
        user_obj = None

    if user_obj:
        if user_obj['convoys']:  # If the user has convoys
            convoy_descs = '\n'.join([
                f'### {convoy['name']}\n'
                f'Current location: ({convoy['x']}, {convoy['y']})\n'
                'Vehicles:\n' + '\n'.join([f'  - {vehicle['name']}' for vehicle in convoy['vehicles']])
                for convoy in user_obj['convoys']
            ])

            description = '\n'.join([
                '# Desolate Frontiers',
                'Welcome to the Desolate Frontiers!',
                'Select a convoy:',
                convoy_descs
            ])
        else:  # If the user doesn't have convoys
            description = '\n'.join([
                '# Desolate Frontiers',
                'Welcome to the Desolate Frontiers!',
                'You do not have any convoys. Use the button below to create one.'
            ])
    else:  # If the user is not registered the Desolate Frontiers
        description = '\n'.join([
            '# Desolate Frontiers',
            'Welcome to the Desolate Frontiers!',
            'You are not a registered Desolate Frontiers user. Use the button below to register.'
        ])
        user_obj = None

    # Prepare the DFState object
    df_state = DFState(
        user_obj=user_obj,
        interaction=interaction,
        previous_embed=None,  # Will be assigned in like 5 lines
        previous_view=None,   # Will be assigned in like 8 lines
    )

    # Send the main menu message
    main_menu_embed = discord.Embed()
    main_menu_embed = df_embed_author(main_menu_embed, df_state)
    main_menu_embed.description = description
    df_state.previous_embed = main_menu_embed

    main_menu_view = MainMenuView(df_state)
    df_state.previous_view = main_menu_view

    if edit:
        await interaction.response.edit_message(embed=main_menu_embed, view=main_menu_view, attachments=[])
    else:
        await interaction.followup.send(embed=main_menu_embed, view=main_menu_view)


class MainMenuView(discord.ui.View):
    def __init__(self, df_state: DFState):
        super().__init__()

        self.df_state = df_state

        self.clear_items()

        if self.df_state.user_obj:
            if len(df_state.user_obj['convoys']) == 1:  # If the user has 1 convoy
                df_state.convoy_obj = df_state.user_obj['convoys'][0]
                self.add_item(MainMenuSingleConvoyButton(df_state=df_state))
                self.add_item(self.user_options_button)

            elif self.df_state.user_obj['convoys']:  # If the user has serveral convoys
                self.add_item(convoy_views.ConvoySelect(df_state=self.df_state))
                self.add_item(self.user_options_button)

            else:  # If the user has no convoys
                self.add_item(self.create_convoy_button)
        
        else:
            self.add_item(self.register_user_button)

    @discord.ui.button(label='Sign Up', style=discord.ButtonStyle.blurple)
    async def register_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.df_state.interaction = interaction
        await interaction.response.send_modal(UsernameModal(interaction.user.display_name))

    @discord.ui.button(label='Create a new convoy', style=discord.ButtonStyle.blurple)
    async def create_convoy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.df_state.interaction = interaction
        await interaction.response.send_modal(ConvoyNameModal(self.df_state))

    @discord.ui.button(label='⚙ Options', style=discord.ButtonStyle.blurple, disabled=True)
    async def user_options_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.df_state.interaction = interaction
        # await interaction.response.send_modal(ConvoyNameModal(self.df_state))


class MainMenuSingleConvoyButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=self.df_state.convoy_obj['name'],
            custom_id='single_convoy_button'
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await convoy_views.convoy_menu(self.df_state)


class UsernameModal(discord.ui.Modal, title='Sign up for Desolate Frontiers'):
    def __init__(self, discord_nickname: str):
        super().__init__()

        self.username_input = discord.ui.TextInput(
            label='New username',
            style=discord.TextStyle.short,
            required=True,
            default=discord_nickname,
            max_length=32,
            custom_id='new_username'
        )
        self.add_item(self.username_input)

    async def on_submit(self, interaction: discord.Interaction):
        await api_calls.new_user(self.username_input.value, interaction.user.id)
        await main_menu(interaction=interaction, edit=True)


class ConvoyNameModal(discord.ui.Modal, title='Name your new convoy'):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__()

        self.convoy_name_input = discord.ui.TextInput(
            label='New convoy name',
            style=discord.TextStyle.short,
            required=True,
            default=f'{df_state.user_obj['username']}\'s convoy',
            max_length=48,
            custom_id='new_convoy_name'
        )
        self.add_item(self.convoy_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        convoy_id = await api_calls.new_convoy(self.df_state.user_obj['user_id'], self.convoy_name_input.value)
        self.df_state.convoy_obj = await api_calls.get_convoy(convoy_id)

        await convoy_views.convoy_menu(self.df_state)
