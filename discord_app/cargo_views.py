# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap

import                                discord

from discord_app               import api_calls, discord_timestamp, df_embed_author
from discord_app.map_rendering import add_map_to_embed
from discord_app.nav_menus     import add_nav_buttons

from discord_app.df_state      import DFState

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


class ConvoyCargoView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState, recipient_vendor_obj: dict = None):
        self.df_state = df_state
        super().__init__(timeout=120)

        add_nav_buttons(self, self.df_state)

        self.add_item(ConvoyCargoSelect(self.df_state))

        if recipient_vendor_obj:
            self.add_item(MapButton(
                convoy_info=self.df_state.convoy_obj,
                recipient_info=recipient_vendor_obj
            ))


class ConvoyCargoSelect(discord.ui.Select):
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


class VendorCargoView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState, recipient_vendor_obj: dict = None):
        self.df_state = df_state
        super().__init__(timeout=120)

        add_nav_buttons(self, self.df_state)

        self.add_item(VendorCargoSelect(self.df_state))

        if recipient_vendor_obj:
            self.add_item(MapButton(
                convoy_info=self.df_state.convoy_obj,
                recipient_info=recipient_vendor_obj
            ))


class VendorCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        options=[
            discord.SelectOption(label=cargo['name'], value=cargo['cargo_id'])
            for cargo in self.df_state.vendor_obj['cargo_inventory']
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
            c for c in self.df_state.vendor_obj['cargo_inventory']
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

def format_part(part):
    fuel_gal = round(part['capacity'] * 0.264172) if part.get('capacity') else None
    lbft = round(part['Nm'] * 0.7376) if part.get('Nm') else None
    horsepower = round(part['kW'] * 1.34102) if part.get('kW') else None
    displacement_cubic_inches = round(part['displacement'] * 61.0237) if part.get('displacement') else None
    cargo_cubic_feet = round(part['cargo_capacity_mod'] * 0.0353147) if part.get('cargo_capacity_mod') else None
    weight_lbs = round(part['weight_capacity_mod'] * 2.20462) if part.get('weight_capacity_mod') else None
    towing_lbs = round(part['towing_capacity_mod'] * 2.20462) if part.get('towing_capacity_mod') else None
    diameter_in = round(part['diameter'] * 39.3701) if part.get('diameter') else None

    part_bits = [
        f'- {part['category'].replace('_', ' ').capitalize()} (OE)' if part.get('OE') else f'- {part['category'].replace('_', ' ').capitalize()}',
        f'  - **{part['name']}**' if part.get('name') else None,

        f'  - {part['capacity']} L ({fuel_gal} gal)' if part.get('capacity') else None,

        f'  - {part['Nm']} N·m ({lbft} lb·ft)' if part.get('Nm') else None,
        f'  - {part['kW']} kW ({horsepower} hp)' if part.get('kW') else None,
        f'  - {part['displacement']} L ({displacement_cubic_inches} in³)' if part.get('displacement') else None,

        f'  - Max AP: {part['max_ap_mod']:+}' if part.get('max_ap_mod') else None,
        f'  - Fuel efficiency: {part['fuel_efficiency_mod']:+}' if part.get('fuel_efficiency_mod') else None,
        f'  - Top speed: {part['top_speed_mod']:+}' if part.get('top_speed_mod') else None,
        f'  - Offroad capability: {part['offroad_capability_mod']:+}' if part.get('offroad_capability_mod') else None,
        f'  - Cargo capacity: {part['cargo_capacity_mod']:+} L ({cargo_cubic_feet:+} ft³)' if part.get('cargo_capacity_mod') else None,
        f'  - Weight capacity: {part['weight_capacity_mod']:+} kg ({weight_lbs:+} lbs)' if part.get('weight_capacity_mod') else None,
        f'  - Towing capacity: {part['towing_capacity_mod']:+} kg ({towing_lbs:+} lbs)' if part.get('towing_capacity_mod') else None,

        f'  - {part['diameter']} m ({diameter_in} in) diameter' if part.get('diameter') else None,

        f'  - *{part['description']}*' if part.get('description') else None,
        # f'  - ${part['part_value']}' if part.get('part_value') else None,
        f'    - Part price: ${part['kit_price']}' if part.get('kit_price') else None,
        f'    - Installation price: ${part['installation_price']}' if part.get('installation_price') else None,
        f'    - Total price: ${part['kit_price'] + part['installation_price']}' if part.get('kit_price') and part.get('installation_price') else None,
    ]

    return '\n'.join(bit for bit in part_bits if bit)
