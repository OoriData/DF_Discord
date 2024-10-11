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

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


class CargoView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(
            self,
            interaction: discord.Interaction,
            convoy_obj: dict,
            previous_view: discord.ui.View,
            previous_embed: discord.Embed,
            recipient_vendor_obj: dict = None,
            previous_attachments: list[discord.Attachment] = None
    ):
        super().__init__(timeout=120)

        self.interaction = interaction
        self.convoy_obj = convoy_obj
        self.previous_view = previous_view
        self.previous_embed = previous_embed
        self.previous_attachments = previous_attachments or []

        # self.add_item(CargoSelect(
        #     convoy_obj=convoy_obj,
        #     previous_embed=previous_embed,
        #     previous_view=previous_view
        # ))

        if recipient_vendor_obj:
            self.add_item(MapButton(
                convoy_info=self.convoy_obj,
                recipient_info=recipient_vendor_obj,
                label='Map (Recipient)',
                style=discord.ButtonStyle.blurple,
                custom_id='map_button')
            )

    # @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.blurple, custom_id='previous_menu', row=0)
    # async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
    #     await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view, attachments=self.previous_attachments)


class CargoSelect(discord.ui.Select):
    def __init__(self, convoy_obj, previous_embed, previous_view, previous_attachments=None):
        options=[
            discord.SelectOption(label=cargo['name'], value=cargo['cargo_id'])
            for cargo in convoy_obj['all_cargo']
        ]
        
        super().__init__(
            placeholder='Select cargo to inspect',
            options=options,
            custom_id='select_cargo',
            row=3
        )

        self.convoy_obj = convoy_obj
        self.previous_embed = previous_embed
        self.previous_view = previous_view
        self.previous_attachments = previous_attachments or []

    async def callback(self, interaction: discord.Interaction):
        selected_cargo = next((
            c for c in self.convoy_obj['all_cargo']
            if c['cargo_id'] == self.values[0]
        ), None)
        carrier_vehicle = next((
            v for v in self.convoy_obj['vehicles']
            if v['vehicle_id'] == selected_cargo['vehicle_id']
        ), None)
        if selected_cargo['recipient']:
            recipient_vendor_obj = await api_calls.get_vendor(vendor_id=selected_cargo['recipient'])
        else:
            recipient_vendor_obj = {}

        cargo_embed = discord.Embed()
        cargo_embed = df_embed_author(cargo_embed, self.convoy_obj, interaction.user)
        # cargo_embed.description = '\n'.join([
        #     # f'# {self.vendor_obj['name']}',
        #     f'## {selected_cargo['name']}',
        #     f'*{selected_cargo['base_desc']}*',
        #     '## repr',
        #     f'```{selected_cargo}```'
        # ])
        cargo_embed.description = '\n'.join([
            f'## {selected_cargo['name']}',
            '- $$$',
            f'  - Base (sell) price: **${selected_cargo['base_price']}**',
            f'  - Recipient: **{recipient_vendor_obj.get('name')}**',
            f'  - Delivery Reward: **${selected_cargo['delivery_reward']}**',
            '- misc',
            f'  - Carrier Vehicle: **{carrier_vehicle['name']}**',
            f'  - Intrinsic: **{selected_cargo['intrinsic']}**',
            f'  - Capacity: **{selected_cargo['capacity']} L**',
            f'  - Quantity: **{selected_cargo['quantity']}**',
            f'  - Volume: **{selected_cargo['volume']}** L',
            f'  - Weight: **{selected_cargo['weight']}** kg',
        ])
        # cargo_embed = df_embed_vehicle_stats(cargo_embed, selected_vehicle)

        cargo_view = CargoView(
            interaction=interaction,
            convoy_obj=self.convoy_obj,
            recipient_vendor_obj=recipient_vendor_obj,
            previous_embed=self.previous_embed,
            previous_view=self.previous_view,
            previous_attachments=self.previous_attachments
        )

        # await interaction.response.edit_message(embed=cargo_embed, view=cargo_view, attachments=[])
        await interaction.response.send_message(embed=cargo_embed, view=cargo_view, ephemeral=True)


class MapButton(discord.ui.Button):
    def __init__(self, convoy_info: dict, recipient_info: dict, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.convoy_info = convoy_info
        self.recipient_info = recipient_info
    
    async def callback(self, interaction: discord.Interaction):

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

        await interaction.response.defer()
        await interaction.followup.send(
            embed=map_embed,
            file=image_file,
            ephemeral=True
        )
