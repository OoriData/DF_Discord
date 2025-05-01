# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from uuid                  import UUID

import                            discord

from discord_app           import api_calls, handle_timeout, df_embed_author, discord_timestamp, validate_interaction
from discord_app.nav_menus import add_nav_buttons
from discord_app.df_state  import DFState


async def dialogue_menu(df_state: DFState, char_a_id: UUID, char_b_id: UUID, page: int = -1, edit: bool=True):
    df_state.append_menu_to_back_stack(func=dialogue_menu, args={
        'char_a_id': char_a_id,
        'char_b_id': char_b_id,
        'page': page
    })  # Add this menu to the back stack

    dialogue_obj = await api_calls.get_dialogue_by_char_ids(char_a_id, char_b_id)
    # TODO: find out who's what, and fetch more relevant details instead

    convoy_name = df_state.convoy_obj['name']
    sender_name = df_state.user_obj['username']

    display_messages = []
    for message in dialogue_obj['messages']:
        # display_messages.append(f'**{message['role']}**:\n{message['content']}')
        timestamp = discord_timestamp(format_letter='f', formatted_time=message['timestamp'])
        display_messages.append(f'## {timestamp}:\n{message['content']}')
    if not display_messages:
        display_messages = ['Nobody\'s spoken here yet.']

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'# Dialogue between {convoy_name} & {sender_name}',
        # '\n\n'.join(display_messages)
        display_messages[page]
    ])
    embed.description = embed.description[:4096]  # Guarentee the log is short enough to send
    if page == -1:  # display nuances
        embed.set_footer(text=f'Page [{len(display_messages)} / {len(display_messages)}]')
    else:
        embed.set_footer(text=f'Page [{(page + 1) % len(display_messages)} / {len(display_messages)}]')

    view = DialogueView(df_state, page, char_a_id, char_b_id)

    if edit:
        await df_state.interaction.response.edit_message(embed=embed, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=embed, view=view, files=[])

class DialogueView(discord.ui.View):
    """ Overarching dialogue button menu """
    def __init__(
            self,
            df_state: DFState,
            page: int,
            char_a_id: UUID,
            char_b_id: UUID
    ):
        self.df_state = df_state
        self.page = page
        self.char_a_id = char_a_id
        self.char_b_id = char_b_id

        super().__init__(timeout=600)

        add_nav_buttons(self, df_state)

    @discord.ui.button(style=discord.ButtonStyle.blurple, label='◀', custom_id='prev_dialogue', row=1)
    async def dialogue_prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        page = self.page - 1

        await dialogue_menu(
            df_state=self.df_state,
            char_a_id=self.df_state.user_obj['user_id'],
            char_b_id=self.df_state.convoy_obj['convoy_id'],
            page=page
        )

    @discord.ui.button(style=discord.ButtonStyle.blurple, label='▶', custom_id='next_dialogue', row=1)
    async def dialogue_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        page = self.page + 1

        await dialogue_menu(
            df_state=self.df_state,
            char_a_id=self.df_state.user_obj['user_id'],
            char_b_id=self.df_state.convoy_obj['convoy_id'],
            page=page
        )


    @discord.ui.button(style=discord.ButtonStyle.green, label='Send Message', custom_id='send_message_modal', emoji='💬', row=2)
    async def send_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        dialogue_obj = await api_calls.get_dialogue_by_char_ids(self.char_a_id, self.char_b_id)
        dialogue_msg = dialogue_obj['messages'][self.page]['content']

        await interaction.response.send_modal(SendMessageModal(self.df_state, self.char_a_id, self.char_b_id, dialogue_msg=dialogue_msg))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class SendMessageModal(discord.ui.Modal):
    def __init__(self, df_state: DFState, char_a_id: UUID, char_b_id: UUID, dialogue_msg: str = None):
        self.df_state = df_state
        self.char_a_id = char_a_id
        self.char_b_id = char_b_id
        self.dialogue_msg = dialogue_msg

        super().__init__(title='Send a message to your convoy captain')

        self.add_item(discord.ui.TextInput(
            label='Previous message from convoy',
            style=discord.TextStyle.paragraph,
            required=False,
            default=self.dialogue_msg,
            max_length=2048,
            custom_id='previous_message'
        ))
        self.convoy_name_input = discord.ui.TextInput(
            label='Message to send',
            style=discord.TextStyle.paragraph,
            required=True,
            placeholder='',
            default='hello!',
            max_length=2048,
            custom_id='new_message'
        )
        self.add_item(self.convoy_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        try:
            await api_calls.send_message(self.char_a_id, self.char_b_id, self.convoy_name_input.value)
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        await dialogue_menu(self.df_state, self.char_a_id, self.char_b_id)


class RespondToConvoyView(discord.ui.View):
    def __init__(
            self,
            user_discord_id,
            user_convoy_id,
            user_cache
    ):
        self.user_discord_id = user_discord_id
        self.user_convoy_id = user_convoy_id
        self.user_cache = user_cache

        super().__init__(timeout=600)

        self.df_state = DFState(user_discord_id=self.user_discord_id)

    @discord.ui.button(style=discord.ButtonStyle.blurple, label='Respond')
    async def respond_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.df_state.user_obj = await api_calls.get_user_by_discord(self.user_discord_id)
        self.df_state.convoy_obj = await api_calls.get_convoy(self.user_convoy_id)  # TODO: implement 'next' pattern to fetch this out of user_obj
        self.df_state.map_obj = await api_calls.get_map()
        self.df_state.user_cache = self.user_cache

        self.df_state.interaction = interaction

        await validate_interaction(interaction=interaction, df_state=self.df_state)

        await dialogue_menu(
            df_state=self.df_state,
            char_a_id=self.df_state.user_obj['user_id'],
            char_b_id=self.df_state.convoy_obj['convoy_id']
        )
