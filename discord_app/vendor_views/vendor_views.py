# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                              import annotations
import                                              os
import                                              textwrap

import                                              discord

from utiloori.ansi_color                     import ansi_color

from discord_app                             import api_calls, df_embed_author, add_tutorial_embed, get_tutorial_stage
from discord_app.map_rendering               import add_map_to_embed
from discord_app.vendor_views.mechanic_views import MechVehicleDropdownView
from discord_app.vendor_views                import vendor_inv_md
import                                              discord_app.vendor_views.mechanic_views
import                                              discord_app.vendor_views.buy_menus
import                                              discord_app.vendor_views.sell_menus
import                                              discord_app.nav_menus

from discord_app.df_state                    import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


async def vendor_menu(df_state: DFState, edit: bool=True):
    vendor_embed = discord.Embed()
    vendor_embed = df_embed_author(vendor_embed, df_state)

    vendor_embed.description = await vendor_inv_md(df_state.vendor_obj)
    
    embeds = [vendor_embed]
    embeds = add_tutorial_embed(embeds, df_state)

    vendor_view = VendorView(df_state)

    if edit:
        await df_state.interaction.response.edit_message(embeds=embeds, view=vendor_view)
    else:
        await df_state.interaction.followup.send(embeds=embeds, view=vendor_view)


class VendorView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyButton(df_state))
        self.add_item(MechanicButton(df_state))
        self.add_item(SellButton(df_state))

        tutorial_stage = get_tutorial_stage(self.df_state)  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                item.disabled = item.custom_id not in (
                    # 'nav_back_button',
                    'nav_sett_button',
                    'buy_button'
                )

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
