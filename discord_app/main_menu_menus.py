# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap
import                                asyncio

import                                discord

import                                discord_app
from discord_app               import (
    api_calls, convoy_menus, warehouse_menus, banner_menus,
    handle_timeout, add_external_URL_buttons, discord_timestamp, df_embed_author, get_image_as_discord_file,
    DF_GUILD_ID, DF_TEXT_LOGO_URL, DF_LOGO_EMOJI, OORI_RED, get_user_metadata, validate_interaction, get_settlement_emoji
)
import discord_app.convoy_menus
from discord_app.map_rendering import add_map_to_embed

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


async def main_menu(
        interaction: discord.Interaction,
        user_cache: dict,
        message: discord.Message=None,
        user_id: int=None,
        df_map=None,
        edit: bool=True
):
    'This menu should *always* perform a "full refresh" in order to allow it to function as a reset/refresh button'
    df_logo = await get_image_as_discord_file(DF_TEXT_LOGO_URL)
    title_embed = discord.Embed()
    title_embed.color = discord.Color.from_rgb(*OORI_RED)
    title_embed.set_image(url='attachment://image.png')

    if not user_id:
        user_id = interaction.user.id

    guild_id = interaction.guild.id if interaction.guild else None
    if user_id not in list(user_cache.keys()) and guild_id != DF_GUILD_ID:
        external_embed = discord.Embed()
        external_embed.description = '\n'.join([
            f"## To play, you must join the [{DF_LOGO_EMOJI} Desolate Frontiers server](https://discord.gg/nS7NVC7PaK).",
            "Desolate Frontiers is a solarpunk-inspired, mildly apocalyptic idle MMO logistics simulator. You take on the role of a logistics company, transporting cargo and passengers across a shattered, not so United States.",
            "",
            "After signing up in the Desolate Frontiers server, you'll be able to manage your convoys from any Discord server where the Desolate Frontiers app is installed, or by [adding the Desolate Frontiers app to your Discord account](https://discord.com/oauth2/authorize?client_id=1257782434896806009)."
        ])

        if message:
            await message.edit(
                content=None,
                embeds=[title_embed, external_embed],
                attachments=[df_logo],
                view=add_external_URL_buttons(discord.ui.View())
            )

        else:
            await interaction.response.send_message(
                embeds=[title_embed, external_embed],
                files=[df_logo],
                view=add_external_URL_buttons(discord.ui.View())
            )

        return

    if interaction:
        await interaction.response.defer()

    try:
        user_obj = await api_calls.get_user_by_discord(user_id)
    except RuntimeError as e:
        # print(f'user not registered: {e}')
        user_obj = None

    if user_obj:
        if user_obj['convoys']:  # If the user has convoys
            convoy_descs = []
            for convoy in user_obj['convoys']:
                tile_obj = await api_calls.get_tile(convoy['x'], convoy['y'])

                if convoy['journey']:
                    destination = await api_calls.get_tile(convoy['journey']['dest_x'], convoy['journey']['dest_y'])
                    progress_percent = ((convoy['journey']['progress']) / len(convoy['journey']['route_x'])) * 100
                    eta = convoy['journey']['eta']
                    convoy_descs.extend([
                        f'## {convoy['name']} 🛣️\n'
                        f'In transit to **{destination['settlements'][0]['name']}**: **{progress_percent:.2f}%** (ETA: {discord_timestamp(eta, 't')})',
                        '\n'.join([f'- {vehicle['name']}' for vehicle in convoy['vehicles']])
                    ])
                else:
                    convoy_descs.extend([
                        f'## {convoy['name']} 🅿️\n'
                        f'Arrived at **{tile_obj['settlements'][0]['name']}**' if tile_obj['settlements'] else f'Arrived at **({convoy['x']}, {convoy['y']})**',
                        '\n'.join([f'- {vehicle['name']}' for vehicle in convoy['vehicles']])
                    ])

            description = '\n' + '\n'.join(convoy_descs)
        elif any(w['vehicle_storage'] for w in user_obj['warehouses']):
            description = '\nYou do not have any convoys. Create a new one at a warehouse.'

        else:  # If the user doesn't have convoys
            description = '\nYou do not have any convoys. Use the button below to create one.'

    else:  # If the user is not registered the Desolate Frontiers
        description = '\nWelcome to the Desolate Frontiers!\nYou are not a registered Desolate Frontiers user. Use the button below to register.'
        user_obj = None

    if not df_map:  # Get the map, if none was provided
        df_map = await api_calls.get_map()

    df_state = DFState(  # Prepare the DFState object
        user_discord_id=user_id,
        map_obj=df_map,
        user_obj=user_obj,
        interaction=interaction,
        user_cache=user_cache
    )

    main_menu_embed = discord.Embed()
    main_menu_embed = df_embed_author(main_menu_embed, df_state)
    main_menu_embed.description = description

    embeds = [title_embed, main_menu_embed]

    if message:
        main_menu_view = MainMenuView(df_state, message)

        await message.edit(
            content=None,
            embeds=embeds,
            view=main_menu_view,
            attachments=[df_logo]
        )

    elif edit:
        main_menu_view = MainMenuView(df_state)

        og_message = await df_state.interaction.original_response()
        await interaction.followup.edit_message(
            message_id=og_message.id,
            content=None,
            embeds=embeds,
            view=main_menu_view,
            attachments=[df_logo]
        )

    else:
        main_menu_view = MainMenuView(df_state)

        await interaction.followup.send(
            content=None,
            embeds=[title_embed, main_menu_embed],
            view=main_menu_view,
            files=[df_logo]
        )

class MainMenuView(discord.ui.View):
    def __init__(self, df_state: DFState, message: discord.Message=None):
        self.df_state = df_state
        self.message = message

        super().__init__(timeout=600)

        self.clear_items()

        if self.df_state.user_obj:  # If user exists
            if len(df_state.user_obj['convoys']) == 1:  # If the user has 1 convoy
                self.add_item(self.user_options_button)
                self.add_item(MainMenuBannerButton(df_state=self.df_state, row=0))
                self.add_item(MainMenuWarehouseSelect(df_state=self.df_state, row=1))
                self.add_item(MainMenuSingleConvoyButton(df_state=df_state, row=2))

            elif self.df_state.user_obj['convoys']:  # If the user has serveral convoys
                self.add_item(self.user_options_button)
                self.add_item(MainMenuBannerButton(df_state=self.df_state, row=0))
                self.add_item(MainMenuWarehouseSelect(df_state=self.df_state, row=1))
                self.add_item(MainMenuConvoySelect(df_state=self.df_state, row=2))

            elif any(w['vehicle_storage'] for w in self.df_state.user_obj['warehouses']):  # If the user has no convoys, but has vehicles in warehouses
                self.add_item(self.user_options_button)
                self.add_item(MainMenuBannerButton(df_state=self.df_state, row=0))
                self.add_item(MainMenuWarehouseSelect(df_state=self.df_state, row=1))

            else:  # If the user has no convoys and no warehoused vehicles (presumably fresh user)
                self.add_item(self.create_convoy_button)

        else:  # If no user
            self.add_item(self.register_user_button)

    @discord.ui.button(label='Sign Up', style=discord.ButtonStyle.blurple, emoji = '🖊️')
    async def register_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        await interaction.response.send_modal(MainMenuUsernameModal(self.df_state))

    @discord.ui.button(label='Create a new convoy', style=discord.ButtonStyle.blurple, emoji='➕')
    async def create_convoy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        await interaction.response.send_modal(MainMenuConvoyNameModal(self.df_state))

    @discord.ui.button(label='Options', style=discord.ButtonStyle.gray, emoji='⚙️', row=0)
    async def user_options_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction
        await options_menu(self.df_state)

    async def on_timeout(self):
        await handle_timeout(self.df_state, self.message)

class MainMenuUsernameModal(discord.ui.Modal):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(title='Sign up for Desolate Frontiers')

        self.username_input = discord.ui.TextInput(
            label='Desolate Frontiers username',
            style=discord.TextStyle.short,
            required=True,
            default=self.df_state.interaction.user.display_name,
            max_length=15,
            custom_id='new_username'
        )
        self.add_item(self.username_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = await api_calls.new_user(self.username_input.value, interaction.user.id)
        self.df_state.user_obj = await api_calls.get_user(user_id)
        self.df_state.user_obj['metadata']['mobile'] = True
        await api_calls.update_user_metadata(self.df_state.user_obj['user_id'], self.df_state.user_obj['metadata'])
        await main_menu(interaction=interaction, df_map=self.df_state.map_obj, user_cache=self.df_state.user_cache)

class MainMenuConvoyNameModal(discord.ui.Modal):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(title='Name your new convoy')

        self.convoy_name_input = discord.ui.TextInput(
            label='New convoy name',
            style=discord.TextStyle.short,
            required=True,
            default=f'{df_state.user_obj['username']}\'s convoy',
            max_length=48,
            custom_id='new_convoy_name'
        )
        self.add_item(self.convoy_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        try:
            convoy_id = await api_calls.new_convoy(self.df_state.user_obj['user_id'], self.convoy_name_input.value)
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        self.df_state.convoy_obj = await api_calls.get_convoy(convoy_id)
        tile_obj = await api_calls.get_tile(self.df_state.convoy_obj['x'], self.df_state.convoy_obj['y'])
        self.df_state.sett_obj = tile_obj['settlements'][0]

        await convoy_menus.convoy_menu(self.df_state)

class MainMenuBannerButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row=0):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Banners',
            custom_id='banner_button',
            emoji='🎌',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        await banner_menus.banner_menu(self.df_state)

class MainMenuWarehouseSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=0):
        self.df_state = df_state

        placeholder = 'Warehouses'
        disabled = False
        options=[]
        for warehouse in self.df_state.user_obj['warehouses']:
            warehouse_sett = next(
                (
                    s
                    for row in self.df_state.map_obj['tiles']
                    for t in row
                    for s in t['settlements']
                    if s['sett_id'] == warehouse['sett_id']
                ),
                None
            )

            if warehouse_sett:  # Ensure the settlement exists
                options.append(discord.SelectOption(
                    label=warehouse_sett['name'],
                    value=warehouse['warehouse_id'],
                    emoji=get_settlement_emoji(warehouse_sett['sett_type'])
                ))
        if not options:
            placeholder = 'No Warehouses'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]



        super().__init__(
            placeholder=placeholder,
            options=options,
            custom_id='warehouse_select',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        self.df_state.warehouse_obj = await api_calls.get_warehouse(self.values[0])
        self.df_state.sett_obj = next((
            s
            for row in self.df_state.map_obj['tiles']
            for t in row
            for s in t['settlements']
            if s['sett_id'] == self.df_state.warehouse_obj['sett_id']
        ), None)

        await warehouse_menus.warehouse_menu(self.df_state)

class MainMenuSingleConvoyButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row=2):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=df_state.user_obj['convoys'][0]['name'],
            custom_id='single_convoy_button',
            emoji='🛣️' if df_state.user_obj['convoys'][0]['journey'] else '🅿️',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        self.df_state.convoy_obj = self.df_state.user_obj['convoys'][0]

        tile_obj = await api_calls.get_tile(self.df_state.convoy_obj['x'], self.df_state.convoy_obj['y'])
        self.df_state.sett_obj = tile_obj['settlements'][0] if tile_obj['settlements'] else None

        await convoy_menus.convoy_menu(self.df_state)

class MainMenuConvoySelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row=1):
        self.df_state = df_state

        options = [
            discord.SelectOption(
                label=convoy['name'],
                value=convoy['convoy_id'],
                emoji='🛣️' if convoy['journey'] else '🅿️'
            )
            for convoy in df_state.user_obj['convoys']
        ]

        super().__init__(
            placeholder='Which convoy?',
            options=options,
            custom_id='select_convoy',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction

        self.df_state.convoy_obj = next((
            c for c in self.df_state.user_obj['convoys']
            if c['convoy_id'] == self.values[0]
        ), None)

        tile_obj = await api_calls.get_tile(self.df_state.convoy_obj['x'], self.df_state.convoy_obj['y'])
        if tile_obj['settlements']:
            self.df_state.sett_obj = tile_obj['settlements'][0]  # XXX presuming only one settlement

        await discord_app.convoy_menus.convoy_menu(self.df_state)


async def options_menu(df_state: DFState, edit: bool=True):
    df_state.user_obj = await api_calls.get_user(df_state.user_obj['user_id'])

    options_embed = discord.Embed()
    options_embed = df_embed_author(options_embed, df_state)

    options_embed.description = '# Options'

    user_metadata = df_state.user_obj['metadata']
    user_metadata.setdefault('mobile', False)

    referral_code_text = ''

    df_plus_str = df_state.user_obj.get('df_plus')  # Safely get the value (or None)

    if df_plus_str:
        df_exp = datetime.strptime(df_plus_str, "%Y-%m-%d").date()
    else:
        df_exp = None  # Assign None if df_plus_str is None

    if df_exp and df_exp >= datetime.now().date():
        referral_code_text = f'\n\nInvite your friends to subscribe to DF+ to get 14 days for free!\n'
    if df_state.user_obj['free_days']:
        free_days = df_state.user_obj['free_days']
    else: 
        free_days = 0
    referral_code_text += f'\nYou currently have **{free_days}** free day(s) of DF+\nUse /redeem_free_days on Oori ledger to Claim '
    if df_exp and df_exp >= datetime.now().date():
            referral_code_text += f'\nYour referral code:\n**{df_state.user_obj['referral_code']}**'


    options_embed.description += f'\n 📱🖥️ App Mode: **{user_metadata['mobile']}**\n*Reformats certain menus to be easier to read on mobile devices.*{referral_code_text}'

    view = OptionsView(df_state)

    await df_state.interaction.response.edit_message(embeds=[options_embed], view=view, attachments=[])

class OptionsView(discord.ui.View):
    def __init__(self, df_state: DFState):
        super().__init__(timeout=600)
        self.df_state = df_state
        is_disabled  = False
        # Check if the button should be disabled (disable if expired)
        df_plus_str = df_state.user_obj.get('df_plus')  # Safely get the value (or None)

        if df_plus_str is None:
            is_disabled = True
        elif df_plus_str < datetime.now().date():
            is_disabled = True

        # Add the referral button dynamically
        self.add_item(ReferralButton(df_state, disabled=is_disabled))

        self.add_item(
            AppModeButton(df_state)
        )

        self.add_item(
            ChangeUsernameButton(df_state, disabled=is_disabled)
        )

        self.add_item(
            ChangeConvoyNameButton(df_state, disabled=is_disabled)
        )

    @discord.ui.button(label='Return to Main Menu', style=discord.ButtonStyle.gray, row=0)
    async def main_menu_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction
        await main_menu(interaction=interaction, df_map=self.df_state.map_obj, user_cache=self.df_state.user_cache, edit=False)




class ChangeUsernameButton(discord.ui.Button):
    def __init__(self, df_state: DFState, disabled: bool, row=2):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Change Your Username',
            custom_id='change_username',
            emoji='🖊️',
            row=row,
            disabled=disabled  # Correctly setting the disabled state
        )
        self.df_state = df_state  # Store df_state so it can be used in callback

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        # Check the expiration date again just to be sure
        df_exp = df_exp = datetime.strptime(self.df_state.user_obj['df_plus'].strip(), "%Y-%m-%d").date()

        if df_exp > datetime.now().date():
            await interaction.response.send_modal(ChangeUsernameModal(self.df_state))


class ChangeUsernameModal(discord.ui.Modal):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(title='Change your Username')

        self.username_modal = discord.ui.TextInput(
            label='Change Username',
            style=discord.TextStyle.short,
            required=False,
            default=f'Wastelander',
            max_length=15,
            custom_id='change_username',
        )
        self.add_item(self.username_modal)

    async def on_submit(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        # ✅ Get value directly from the TextInput instance
        new_username = self.username_modal.value

        self.df_state.user_obj['username'] = new_username

        success = await api_calls.change_username(
            self.df_state.user_obj['user_id'],
            new_username
        )

        refer_embed = discord.Embed()
        refer_embed = df_embed_author(refer_embed, self.df_state)

        refer_embed.description = success
        view = OptionsView(self.df_state)

        await self.df_state.interaction.response.edit_message(embeds=[refer_embed], view=view, attachments=[])


class ConvoySelectBeforeRename(discord.ui.Select):
    def __init__(self, df_state: DFState, row=0):
        self.df_state = df_state

        options = [
            discord.SelectOption(
                label=convoy['name'],
                value=convoy['convoy_id'],
                emoji='🛣️' if convoy['journey'] else '🅿️'
            )
            for convoy in df_state.user_obj['convoys']
        ]

        super().__init__(
            placeholder='Select a convoy to rename',
            options=options,
            custom_id='select_convoy_to_rename',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        # Store the selected convoy in df_state
        selected_convoy = next(
            (convoy for convoy in self.df_state.user_obj['convoys']
             if convoy['convoy_id'] == self.values[0]),
            None
        )
        if selected_convoy:
            self.df_state.convoy_obj = selected_convoy
            await interaction.response.send_modal(ChangeConvoyNameModal(self.df_state))

class ChangeConvoyNameButton(discord.ui.Button):
    def __init__(self, df_state: DFState, disabled: bool, row=2):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Change Your Convoy\'s Name',
            custom_id='change_convoy_name',
            emoji='🖊️',
            row=row,
            disabled=disabled
        )
        self.df_state = df_state

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        view = discord.ui.View()
        view.add_item(ConvoySelectBeforeRename(self.df_state))

        await interaction.response.send_message(
            content='Select a convoy to rename:',
            view=view,
            ephemeral=True
        )


class ChangeConvoyNameModal(discord.ui.Modal):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(title='Rename Your Convoy')

        # Pre-fill the name with the selected convoy’s current name
        self.convoy_name_modal = discord.ui.TextInput(
            label='New convoy name',
            style=discord.TextStyle.short,
            required=True,
            default=self.df_state.convoy_obj['name'],
            max_length=15,
            custom_id='new_convoy_name',
        )
        self.add_item(self.convoy_name_modal)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.convoy_name_modal.value

        # Call the backend to update the name
        success = await api_calls.change_convoy_name(
            convoy_id=self.df_state.convoy_obj['convoy_id'],
            new_name=new_name
        )

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)

        embed.description = success
        view = OptionsView(self.df_state)

        await interaction.response.edit_message(embeds=[embed], view=view, attachments=[])




class ReferralButton(discord.ui.Button):
    def __init__(self, df_state: DFState, disabled: bool, row=2):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Redeem a Friend\'s code',
            custom_id='referral_button',
            emoji='🫵',
            row=row,
            disabled=disabled  # Correctly setting the disabled state
        )
        self.df_state = df_state  # Store df_state so it can be used in callback

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        # Check the expiration date again just to be sure
        df_plus_str = self.df_state.user_obj.get('df_plus')  # Safely get the value

        if df_plus_str:  # Ensure it's not None or empty
            df_exp = datetime.strptime(df_plus_str.strip(), "%Y-%m-%d").date()

            if df_exp > datetime.now().date():
                await interaction.response.send_modal(ReferralCodeModal(self.df_state))

class AppModeButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row=1):
        self.df_state = df_state

        if df_state.user_obj['metadata']['mobile']:
            label = 'Switch to Desktop Mode'
            emoji = '🖥️'
        else:
            label = 'Switch to App Mode'
            emoji = '📱'

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            custom_id='mobile_button',
            emoji=emoji,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)

        self.df_state.interaction = interaction

        self.df_state.user_obj['metadata']['mobile'] = not self.df_state.user_obj['metadata']['mobile']
        if self.df_state.convoy_obj:
            self.df_state.convoy_obj['user_metadata']['mobile'] = not self.df_state.user_obj['metadata']['mobile']
        await api_calls.update_user_metadata(self.df_state.user_obj['user_id'], self.df_state.user_obj['metadata'])

        await options_menu(self.df_state)



class ReferralCodeModal(discord.ui.Modal):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(title='Use a Friend\'s code')

        self.referral_modal = discord.ui.TextInput(
            label='Redeem a Friend\'s code to gift 14 Days',
            style=discord.TextStyle.short,
            required=False,
            default=f'XXXXXX',
            max_length=48,
            custom_id='referral_code',
        )
        self.add_item(self.referral_modal)

    async def on_submit(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        success = await api_calls.redeem_referral(self.df_state.user_obj['user_id'], str(self.referral_modal.value).upper())

        refer_embed = discord.Embed()
        refer_embed = df_embed_author(refer_embed, self.df_state)

        refer_embed.description = success[1]
        view = OptionsView(self.df_state)

        await self.df_state.interaction.response.edit_message(embeds=[refer_embed], view=view, attachments=[])


# class RedeemConfirmationView(discord.ui.View):
#     def __init__(self, df_state: DFState):
#         super().__init__()
#         self.df_state = df_state

#         # Add confirm and cancel buttons
#         self.add_item(ConfirmRedeemButton(df_state))
#         self.add_item(CancelButton())

class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.grey,
            label='Cancel',
            custom_id='cancel'
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Action cancelled.", view=None)
