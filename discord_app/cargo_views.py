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
import discord_app.nav_menus
import discord_app.convoy_views

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

    cargo_view = ConvoyCargoView(
        df_state=df_state,
        recipient_vendor_obj=recipient_vendor_obj
    )

    await df_state.interaction.response.edit_message(embed=cargo_embed, view=cargo_view, attachments=[])


class ConvoyCargoView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState, recipient_vendor_obj: dict = None):
        self.df_state = df_state
        super().__init__()

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        # self.add_item(ConvoyCargoSelect(self.df_state))

        self.add_item(MoveCargoVehicleSelect(self.df_state))

        if recipient_vendor_obj:
            self.add_item(MapButton(self.df_state.convoy_obj, recipient_vendor_obj))

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


class MoveCargoVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state

        if self.df_state.cargo_obj['intrinsic']:
            disabled = True
        else:
            disabled = False

        placeholder = 'Select vehicle to move cargo into'
        options = [
            discord.SelectOption(label=vehicle['name'], value=vehicle['vehicle_id'])
            for vehicle in self.df_state.convoy_obj['vehicles']
            if vehicle['vehicle_id'] != self.df_state.cargo_obj['vehicle_id']
        ]
        if not options:
            placeholder = 'No valid vehicles to move cargo into'
            disabled = True
            options = [discord.SelectOption(label='none', value='none')]
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id='select_vehicle',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        dest_vehicle = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        self.df_state.convoy_obj = await api_calls.move_cargo(
            self.df_state.convoy_obj['convoy_id'],
            self.df_state.cargo_obj['cargo_id'],
            dest_vehicle['vehicle_id']
        )

        await discord_app.convoy_views.convoy_menu(self.df_state)


class ConvoyCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Select cargo to inspect'
        disabled = False
        options = []
        for vehicle in self.df_state.convoy_obj['vehicles']:
            for cargo in vehicle['cargo']:
                if not cargo['intrinsic']:
                    options.append(discord.SelectOption(label=f'{cargo['name']} ({vehicle['name']})', value=cargo['cargo_id']))
        if not options:
            placeholder = 'No cargo in convoy'
            disabled = True
            options = [discord.SelectOption(label='None', value='None')]
        
        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id='select_cargo',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.cargo_obj = next((
            c for c in self.df_state.convoy_obj['all_cargo']
            if c['cargo_id'] == self.values[0]
        ), None)

        await cargo_menu(df_state=self.df_state)


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
    def __init__(self, convoy_obj: dict, recipient_obj: dict, row: int=1):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Map to Recipient',
            custom_id='map_button',
            row=row
        )
        self.convoy_obj = convoy_obj
        self.recipient_obj = recipient_obj
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        convoy_x = self.convoy_obj['x']
        convoy_y = self.convoy_obj['y']

        recipient_x = self.recipient_obj['x']
        recipient_y = self.recipient_obj['y']

        embed = discord.Embed(
            title=f'Map relative to {self.convoy_obj['name']}',
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

        map_embed.set_footer(text='Your interaction is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.followup.send(
            embed=map_embed,
            file=image_file,
            ephemeral=True
        )

def format_part(part_cargo: dict):
    if part_cargo.get('cargo_id'):
        part = part_cargo['part']
        name = part_cargo['name']
    else:
        part = part_cargo
        name = part['name'] if part.get('name') else None

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
        f'  - **{name}**',

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
