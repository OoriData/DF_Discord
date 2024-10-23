# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from uuid                  import UUID

import                            discord

from discord_app           import api_calls, df_embed_author
from discord_app.nav_menus import add_nav_buttons
from discord_app.df_state  import DFState


async def dialogue_menu(df_state: DFState, char_a_id: UUID, char_b_id: UUID, edit: bool=True):
    # TODO: call an embed with the ConvoySelect if the df_state doesn't have a convoy_obj

    dialogue_obj = await api_calls.get_dialogue_by_char_ids(char_a_id, char_b_id)
    display_messages = []
    for message in dialogue_obj['messages']:
        display_messages.append(f'**{message['role']}**:\n{message['content']}')
    if not display_messages:
        display_messages = ['Nobody\'s spoken here yet.']

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'## Dialogue between {char_a_id} & {char_b_id}',
        '\n\n'.join(display_messages)
    ])
    embed.description = embed.description[:4096]  # Guarentee the log is short enough to send

    view = DialogueView(df_state)

    if edit:
        await df_state.interaction.response.edit_message(embed=embed, view=view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=embed, view=view, files=[])


class DialogueView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(
            self,
            df_state: DFState
    ):
        self.df_state = df_state
        super().__init__(timeout=120)  # TODO: Add view timeout as a configurable option

        add_nav_buttons(self, df_state)
