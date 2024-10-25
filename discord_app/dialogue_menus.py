# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from uuid                  import UUID

import                            discord

from discord_app           import api_calls, df_embed_author, discord_timestamp
from discord_app.nav_menus import add_nav_buttons
from discord_app.df_state  import DFState

def add_dialogue_buttons(view: discord.ui.View, df_state: DFState, page: int):  # FIXME: probably just remove this and add items individually
    view.add_item(DialogueBackButton(df_state=df_state, page=page))
    view.add_item(DialogueNextButton(df_state=df_state, page=page))

async def dialogue_menu(df_state: DFState, char_a_id: UUID, char_b_id: UUID, edit: bool=True, page: int = -1):
    # TODO: call an embed with the ConvoySelect if the df_state doesn't have a convoy_obj

    dialogue_obj = await api_calls.get_dialogue_by_char_ids(char_a_id, char_b_id)

    convoy_name = await api_calls.get_convoy(char_b_id)
    convoy_name = convoy_name['name']
    sender_name = 'Master Chief'  # FIXME: This is just a placeholder since I can't access the sender's name yet

    display_messages = []
    for message in dialogue_obj['messages']:
        # display_messages.append(f'**{message['role']}**:\n{message['content']}')
        timestamp = discord_timestamp(format_letter='f', formatted_time=message['timestamp'])
        display_messages.append(f'{timestamp}:\n{message['content']}')
    if not display_messages:
        display_messages = ['Nobody\'s spoken here yet.']

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'## Dialogue between {convoy_name} & {sender_name}',
        # '\n\n'.join(display_messages)
        display_messages[page]
    ])
    embed.description = embed.description[:4096]  # Guarentee the log is short enough to send
    if page == -1:  # display nuances
        embed.set_footer(text=f'Page [{len(display_messages)} / {len(display_messages)}]')
    else:
        embed.set_footer(text=f'Page [{(page + 1) % len(display_messages)} / {len(display_messages)}]')

    view = DialogueView(df_state, page)

    if edit:
        await df_state.interaction.response.edit_message(embed=embed, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=embed, view=view, files=[])

class DialogueView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(
            self,
            df_state: DFState,
            page: int
    ):
        self.df_state = df_state
        self.page = page
        super().__init__()  # TODO: Add view timeout as a configurable option
        
        add_nav_buttons(self, df_state)

        add_dialogue_buttons(self, df_state, page)

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

class DialogueNextButton(discord.ui.Button):
    ''' Button for navigating between convoy dialogues '''
    def __init__(self, df_state: DFState, page: int):
        self.df_state = df_state
        self.page = page

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='▶',
            custom_id='next_dialogue',
            row=1,
        )  # TODO: Add view timeout as a configurable option
        
    async def callback(self, interaction: discord.Interaction):
        page = self.page + 1
        self.df_state.interaction = interaction
        await dialogue_menu(df_state=self.df_state, char_a_id=self.df_state.user_obj['user_id'], char_b_id=self.df_state.convoy_obj['convoy_id'], edit=True, page=page)
        
class DialogueBackButton(discord.ui.Button):
    ''' Button for navigating between convoy dialogues '''
    def __init__(self, df_state: DFState, page: int):
        self.df_state = df_state
        self.page = page

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='◀',
            custom_id='back_dialogue',
            row=1,
        )  # TODO: Add view timeout as a configurable option
        
    async def callback(self, interaction: discord.Interaction):
        page = self.page - 1
        self.df_state.interaction = interaction
        await dialogue_menu(df_state=self.df_state, char_a_id=self.df_state.user_obj['user_id'], char_b_id=self.df_state.convoy_obj['convoy_id'], edit=True, page=page)