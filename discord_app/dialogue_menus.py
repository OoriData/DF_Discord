# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from uuid                  import UUID

import                            discord

from discord_app           import api_calls, df_embed_author, discord_timestamp
from discord_app.nav_menus import add_nav_buttons
from discord_app.df_state  import DFState


async def dialogue_menu(df_state: DFState, char_a_id: UUID, char_b_id: UUID, edit: bool=True, page: int = -1):
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
    ''' Overarching convoy button menu '''
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
        page = self.page - 1
        self.df_state.interaction = interaction
        
        await dialogue_menu(
            df_state=self.df_state,
            char_a_id=self.df_state.user_obj['user_id'],
            char_b_id=self.df_state.convoy_obj['convoy_id'],
            page=page
        )

    @discord.ui.button(style=discord.ButtonStyle.blurple, label='▶', custom_id='next_dialogue', row=1)
    async def dialogue_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        page = self.page + 1
        self.df_state.interaction = interaction

        await dialogue_menu(
            df_state=self.df_state,
            char_a_id=self.df_state.user_obj['user_id'],
            char_b_id=self.df_state.convoy_obj['convoy_id'],
            page=page
        )


    @discord.ui.button(style=discord.ButtonStyle.green, label='Send Message', custom_id='send_message_modal', row=2)
    async def send_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.df_state.interaction = interaction
        
        await interaction.response.send_modal(SendMessageModal(self.df_state, self.char_a_id, self.char_b_id))

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()


class SendMessageModal(discord.ui.Modal):
    def __init__(self, df_state: DFState, char_a_id: UUID, char_b_id: UUID):
        self.df_state = df_state
        self.char_a_id = char_a_id
        self.char_b_id = char_b_id
        
        super().__init__(title='Send a message to your convoy captain')

        self.convoy_name_input = discord.ui.TextInput(
            label='Message to send',
            style=discord.TextStyle.paragraph,
            required=True,
            default='hello!',
            max_length=2048,
            custom_id='new_message'
        )
        self.add_item(self.convoy_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        await api_calls.send_message(self.char_a_id, self.char_b_id, self.convoy_name_input.value)
        await dialogue_menu(self.df_state, self.char_a_id, self.char_b_id)
