# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, df_embed_author
from discord_app.map_rendering import add_map_to_embed
from discord_app.vendor_views.mechanic_views import MechVehicleDropdownView
import discord_app.vendor_views.mechanic_views
import discord_app.vendor_views.buy_menus
import discord_app.vendor_views.sell_menus
import discord_app.nav_menus

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')

# TODO: send message if user tries to iterate through menu with a length of zero
# TODO: Add universal BackButtonView that just allows users to go back to the main vendor menu after they complete a transaction

SERVICE_KEYS = {
    'fuel': ('Fuel', '{number} liter(s)'),
    'water': ('Water', '{number} liter(s)'),
    'food': ('Food', '{number} serving(s)'),
    'cargo_inventory': ('Cargo', '{number} item(s)'),
    'vehicle_inventory': ('Vehicles', '{number} vehicle(s)'),
    'repair_price': ('Mechanic Services', 'Available')
}


def vendor_services(vendor_obj: dict):
    services = []
    for key in list(SERVICE_KEYS.keys()):
        if vendor_obj[key]:
            if isinstance(vendor_obj[key], list):
                number = len(vendor_obj[key])
            else:
                number = vendor_obj[key]
            services.append((
                SERVICE_KEYS[key][0],
                SERVICE_KEYS[key][1].format(number=number)
            ))

    return services


async def vendor_menu(df_state: DFState, edit: bool=True):
    vendor_embed = discord.Embed()
    vendor_embed = df_embed_author(vendor_embed, df_state)

    if df_state.vendor_obj:  # If a vendor has been selected
        vendor_embed.description = '\n'.join([
            f'## {df_state.vendor_obj['name']}',
            'Available Services:'
        ])
        
        for service, availability in vendor_services(df_state.vendor_obj):
            vendor_embed.add_field(
                name=service,
                value=availability,
            )

        vendor_view = VendorView(df_state)

    else:  # If no vendor selected, go select one
        tile_obj = await api_calls.get_tile(df_state.convoy_obj['x'], df_state.convoy_obj['y'])
        if not tile_obj['settlements']:
            await df_state.interaction.response.send_message(content='There aint no settle ments here dawg!!!!!', ephemeral=True, delete_after=10)
            return
        
        vendor_displayables = []
        for vendor in tile_obj['settlements'][0]['vendors']:
            displayable_services = []
            for key in list(SERVICE_KEYS.keys()):
                if vendor[key]:
                    displayable_services.append(f'  - {SERVICE_KEYS[key][0]}')

            vendor_displayables.append('\n'.join([
                f'- **{vendor['name']}**',
                '\n'.join(displayable_services)
            ]))
        
        vendor_embed.description = '\n'.join([
            f'## {tile_obj['settlements'][0]['name']}',
            '\n'.join(vendor_displayables),
            'Select a vendor:'
        ])

        vendor_view = ChooseVendorView(df_state, tile_obj['settlements'][0]['vendors'])

    if edit:
        await df_state.interaction.response.edit_message(embed=vendor_embed, view=vendor_view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=vendor_embed, view=vendor_view)


class ChooseVendorView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState, vendors):
        self.df_state = df_state
        super().__init__(timeout=120)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(VendorSelect(self.df_state, vendors))

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


class VendorSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, vendors, row: int=1):
        self.df_state = df_state
        self.vendors = vendors

        options=[
            discord.SelectOption(label=vendor['name'], value=vendor['vendor_id'])
            for vendor in self.vendors
        ]
        
        super().__init__(
            placeholder='Select vendor to visit',
            options=options,
            custom_id='select_vendor',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.vendor_obj = next((
            v for v in self.vendors
            if v['vendor_id'] == self.values[0]
        ), None)

        await vendor_menu(self.df_state)


class VendorView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=120)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyButton(df_state))
        self.add_item(MechanicButton(df_state))
        self.add_item(SellButton(df_state))

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


class BuyButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.vendor_obj['cargo_inventory']:
            disabled = False
        else:
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Buy (Resources, Vehicles, Cargo)',
            disabled=disabled,
            custom_id='buy_button',
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.vendor_views.buy_menus.buy_menu(self.df_state)


class MechanicButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.vendor_obj['repair_price']:
            disabled = False
        else:
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Mechanic (Repairs, part/upgrade management)',
            disabled=disabled,
            custom_id='mech_button',
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.vendor_views.mechanic_views.mechanic_menu(self.df_state)


class SellButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        # if self.df_state.vendor_obj['repair_price']:
        #     disabled = False
        # else:
        #     disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Sell (Resources, Vehicles, Cargo)',
            # disabled=disabled,
            custom_id='sell_button',
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.vendor_views.sell_menus.sell_menu(self.df_state)
