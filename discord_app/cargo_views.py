# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap

import                                discord

from discord_app               import discord_timestamp
from discord_app               import api_calls, discord_timestamp, format_part, df_embed_author
from discord_app.map_rendering import add_map_to_embed
from discord_app.df_state      import DFState
from discord_app.nav_menus     import add_nav_buttons

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


async def cargo_menu(df_state: DFState):
    carrier_vehicle = next((
        v for v in df_state.convoy_obj['vehicles']
        if v['vehicle_id'] == df_state.cargo_obj['vehicle_id']
    ), None)

    if df_state.cargo_obj['recipient']:
        recipient_vendor_obj = await api_calls.get_vendor(vendor_id=df_state.cargo_obj['recipient'])
    else:
        recipient_vendor_obj = {}

    cargo_embed = discord.Embed()
    cargo_embed = df_embed_author(cargo_embed, df_state)
    cargo_embed.description = '\n'.join([
        f'## {df_state.cargo_obj['name']}',
        '- $$$',
        f'  - Base (sell) price: **${df_state.cargo_obj['base_price']}**',
        f'  - Recipient: **{recipient_vendor_obj.get('name')}**',
        f'  - Delivery Reward: **${df_state.cargo_obj['delivery_reward']}**',
        '- misc',
        f'  - Carrier Vehicle: **{carrier_vehicle['name']}**',
        f'  - Intrinsic: **{df_state.cargo_obj['intrinsic']}**',
        f'  - Capacity: **{df_state.cargo_obj['capacity']} L**',
        f'  - Quantity: **{df_state.cargo_obj['quantity']}**',
        f'  - Volume: **{df_state.cargo_obj['volume']}** L',
        f'  - Weight: **{df_state.cargo_obj['weight']}** kg',
    ])

    cargo_view = CargoView(
        df_state=df_state,
        recipient_vendor_obj=recipient_vendor_obj
    )

    await df_state.interaction.response.edit_message(embed=cargo_embed, view=cargo_view, attachments=[])


class CargoView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState, recipient_vendor_obj: dict = None):
        self.df_state = df_state
        super().__init__(timeout=120)

        add_nav_buttons(self, self.df_state)

        self.add_item(CargoSelect(self.df_state))

        if recipient_vendor_obj:
            self.add_item(MapButton(
                convoy_info=self.df_state.convoy_obj,
                recipient_info=recipient_vendor_obj
            ))


class CargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        options=[
            discord.SelectOption(label=cargo['name'], value=cargo['cargo_id'])
            for cargo in self.df_state.convoy_obj['all_cargo']
        ]
        
        super().__init__(
            placeholder='Select cargo to inspect',
            options=options,
            custom_id='select_cargo',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.cargo_obj = next((
            c for c in self.df_state.convoy_obj['all_cargo']
            if c['cargo_id'] == self.values[0]
        ), None)

        await cargo_menu(df_state=self.df_state)


class MapButton(discord.ui.Button):
    def __init__(self, convoy_info: dict, recipient_info: dict):
        super().__init__(label='Map to Recipient', custom_id='map_button', style=discord.ButtonStyle.blurple)
        self.convoy_info = convoy_info
        self.recipient_info = recipient_info
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        convoy_x = self.convoy_info['x']
        convoy_y = self.convoy_info['y']

        recipient_x = self.recipient_info['x']
        recipient_y = self.recipient_info['y']

        embed = discord.Embed(
            title=f'Map relative to {self.convoy_info['name']}',
            description=textwrap.dedent('''
                🟨 - Your convoy's location
                🟦 - Recipient vendor's location
            ''')
        )

        map_embed, image_file = await add_map_to_embed(
            embed=embed,
            highlighted=[(convoy_x, convoy_y)],
            lowlighted=[(recipient_x, recipient_y)],
        )

        map_embed.set_footer(text='Your vendor interaction is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.followup.send(
            embed=map_embed,
            file=image_file,
            ephemeral=True
        )
