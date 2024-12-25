# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Discord Frontend'
from __future__             import annotations
from datetime               import datetime
import                             io

import                             httpx

import                             discord

from discord_app.df_state   import DFState

DF_GUILD_ID = 1225943320078057582

DF_LOGO_EMOJI = '<:df_logo:1310693347370864710>'

DF_LOGO_URL = 'https://www.oori.dev/assets/branding/df_Logo_FullColor.png'
DF_TEXT_LOGO_URL = 'https://www.oori.dev/assets/branding/df_TextLogo_FullColor.png'

OORI_WHITE = (219, 226, 233)
OORI_YELLOW = (243, 213, 78)
OORI_RED = (138, 43, 43)


async def handle_timeout(df_state: DFState, message: discord.Message=None):
    if message:
        await message.edit(
            view=TimeoutView(df_state.user_cache)
        )

    else:
        await df_state.interaction.edit_original_response(
            view=TimeoutView(df_state.user_cache)
        )

class TimeoutView(discord.ui.View):
    def __init__(self, user_cache):
        super().__init__(timeout=None)

        self = add_external_URL_buttons(self)  # Add external link buttons

        self.add_item(TimedOutMainMenuButton(user_cache))

class TimedOutMainMenuButton(discord.ui.Button):
    def __init__(self, user_cache: DFState):
        self.user_cache = user_cache

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Interaction timed out; Main Menu',
            custom_id='timed_out_main_menu_button',
            row=1
        )

    async def callback(self, interaction):
        new_message = await interaction.channel.send(content=f'{DF_LOGO_EMOJI} Loading...')

        import discord_app.main_menu_menus  # XXX: This sucks i wanna put it at the top
        await discord_app.main_menu_menus.main_menu(
            interaction=interaction,
            message=new_message,
            user_cache=self.user_cache,
            user_id=interaction.user.id
        )

        if not interaction.response.is_done():
            await interaction.response.pong()


def add_external_URL_buttons(view: discord.ui.View) -> discord.ui.View:
    view.add_item(URLButton('Join the DF Server', 'https://discord.gg/nS7NVC7PaK'))
    view.add_item(URLButton('Add the DF App', 'https://discord.com/oauth2/authorize?client_id=1257782434896806009'))

    return view


class URLButton(discord.ui.Button):
    def __init__(self, label, url, row=0):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            url=url,
            emoji=DF_LOGO_EMOJI,
            row=row
        )


async def validate_interaction(interaction: discord.Interaction, df_state: DFState):
    if df_state.user_discord_id != interaction.user.id:
        import discord_app.main_menu_menus  # XXX: This sucks i wanna put it at the top
        await discord_app.main_menu_menus.main_menu(
            interaction=interaction,
            df_map=df_state.map_obj,
            user_cache=df_state.user_cache,
            edit=False
        )


async def get_image_as_discord_file(url: str) -> discord.File:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()  # Ensure we got a successful response
        image_bytes = io.BytesIO(response.content)  # Wrap the content in a BytesIO object
    return discord.File(fp=image_bytes, filename='image.png')


def df_embed_author(embed: discord.Embed, df_state: DFState) -> discord.Embed:
    if df_state.convoy_obj:
        name = f'{df_state.convoy_obj['name']} - ${df_state.convoy_obj['money']:,.0f}'
    elif df_state.user_obj:
        name = f'{df_state.user_obj['username']} - ${df_state.user_obj['money']:,.0f}'
    else:
        name = df_state.interaction.user.display_name

    embed.set_author(
        name=name,
        icon_url=df_state.interaction.user.avatar.url if df_state.interaction.user.avatar else None
    )
    return embed


def discord_timestamp(formatted_time: str | datetime, format_letter: str) -> str:
    '''
    Generate a Discord timestamp string for a given datetime or ISO format string and format letter.

    Args:
        formatted_time (str | datetime): The datetime object or ISO format string to format. 
                                         If a string is provided, it should be in ISO 8601 format.
                                         The datetime object **must** have a timezone set!

        format_letter (str): The format letter specifying the Discord timestamp style. Possible values are:
        - 'd': Short date (e.g., 01/31/2024)
        - 'f': Long date with time (e.g., January 31, 2024 01:45 PM)
        - 't': Short time (e.g., 01:45 PM)
        - 'D': Long date (e.g., January 31, 2024)
        - 'F': Day of the week, long date with time (e.g., Wednesday, January 31, 2024 01:45 PM)
        - 'R': Relative time (e.g., <Time remaining since/until>)
        - 'T': Long time with seconds (e.g., 01:45:30 PM)

    Returns:
        str: The Discord-formatted timestamp string.
    '''

    # Convert ISO format string to datetime object if necessary
    if isinstance(formatted_time, str):
        formatted_time = datetime.fromisoformat(formatted_time)

    # Ensure the datetime object has a timezone set
    if formatted_time.tzinfo is None:
        msg = 'The datetime object must be timezone-aware.'
        raise ValueError(msg)

    # Create the Discord timestamp format
    discord_format = f"<t:{int(formatted_time.timestamp())}:{format_letter}>"

    return discord_format


DF_DISCORD_LOGO = '''\
  ╔════════════════════════════════════════╗  
  ║ ┏┳┓┏━┓  ┏┳┓┳┏━┓┏━┓┏━┓┳━┓┏┳┓  ┏━┓┏━┓┏━┓ ║  
  ║  ┃┃┣┫    ┃┃┃┗━┓┃  ┃ ┃┣┳┛ ┃┃  ┣━┫┣━┛┣━┛ ║  
  ║ ╺┻┛┗    ━┻┛┻┗━┛┗━┛┗━┛┻┗━╺┻┛  ┻ ┻┻  ┻   ║  
  ╚════════════════════════════════════════╝  \
'''


def get_user_metadata(df_state: DFState, metadata_key: str):
    user_metadata = df_state.convoy_obj.get('user_metadata')
    return user_metadata.get(metadata_key)


def add_tutorial_embed(embeds: list[discord.Embed], df_state: DFState) -> discord.Embed:
    if not df_state.convoy_obj:
        return embeds
    if (
        not df_state.convoy_obj.get('user_metadata')
        or not df_state.convoy_obj.get('user_metadata', {}).get('tutorial')
    ):
        return embeds

    tutorial_embed = TutorialEmbed()

    match df_state.convoy_obj['user_metadata']['tutorial']:
        case 1:
            tutorial_embed.description = '\n'.join([
                "## Welcome to the **Desolate Frontiers**!",
                "### You're going nowhere without a vehicle, so time to buy one. 🚗",
                f"1. Gray `{df_state.sett_obj['name']}` button to check out the vendors",
                f"- Use the `Select vendor to visit` dropdown menu to select {DF_LOGO_EMOJI}` {df_state.sett_obj['name']} dealership`",
                "- Blurple `Buy (Resources, Vehicles, Cargo)` button",
                f"- Select from the `Vehicle Inventory` dropdown. Vehicles you can afford are marked with {DF_LOGO_EMOJI}",
                "- The block will update, allowing you to inspect the chosen vehicle. If it suits you, hit the green `Buy Vehicle| $X,XXX` button.",
                "  - To inspect a different vehicle, hit the gray `⬅ Back` button",
            ])
        case 2:
            tutorial_embed.description = '\n'.join([
                "### Now that you have a vehicle, you need water & food for your convoy's crew to sustain themselves on their travels. 🥪 💧",
                f"1. Gray `{df_state.sett_obj['name']}` button",
                f"- Use the `Select vendor to visit` dropdown menu to select {DF_LOGO_EMOJI}` {df_state.sett_obj['name']} Market`",
                "- Blurple `Buy (Resources, Vehicles, Cargo)` button",
                f"- Use the `Cargo Inventory` dropdown to select {DF_LOGO_EMOJI}` Water Jerry Cans`",
                "- Blurple `+1` button to add an additional jerry can to your cart",
                "- Green `Buy 2 Water Jerry Cans(s)` button. Note: the cans are sold already full",
                f"- **Repeat this process, to buy just one of {DF_LOGO_EMOJI}` MRE Boxes`, which contain food, and come full**",
            ])
        case 3:
            tutorial_embed.description = '\n'.join([
                "### Now that you have rations, you'll need fuel. The cheap-ass dealership sold you a vehicle with an empty tank. ⛽️",
                f"1. Gray `{df_state.sett_obj['name']}` button",
                "- `Top up fuel | $XXX` button to fill your empty tank",
                "  - Seek out this button in future as a convenient shortcut to buy resources depleted on the road",
            ])
        case 4:
            tutorial_embed.description = '\n'.join([
                "### With the basics down, it's time for your first delivery. 📦",
                f"1. One last time, hit the gray `{df_state.sett_obj['name']}` button",
                f"- Use the `Select vendor to visit` dropdown menu to select `{df_state.sett_obj['name']} Market`",
                "- Blurple `Buy (Resources, Vehicles, Cargo)` button",
                f"- Select your chosen cargo to transport from the `Cargo Inventory` dropdown. Cargo you can fit in your car are marked with {DF_LOGO_EMOJI}",
                "  - Refer below. 💵 emojis indicate the profit margin for that delivery",
                "  - Also consider the distance for the delivery; a high margin delivery might not be worth the time & resource expense of a cross-country trip!",
                "- Blurple `max (+X)` button adds to your cart the maximum amount of this cargo that you can afford and carry",
                "  - **if you just hit the green buy button now, you'll only buy one. Seek big deliveries for big profits!**",
                "- Green `Buy X cargo(s)` button to complete the purchase",
            ])
        case 5:
            tutorial_embed.description = '\n'.join([
                "### Now that you have a vehicle, provisions, and a delivery to fulfill, let's get you on the road! 🛣️",
                "1. Gray `convoy` button",
                "- Green `Embark on new Journey` button",
                "- Use the `Where to?` dropdown menu to select your delivery destination",
                "  - This destination will have the name of the cargo bound for it in parentheses after its name",
                "- Hit the green `Embark upon Journey` button to send your convoy on its way!",
            ])
        case 6:
            tutorial_embed.description = '\n'.join([
                "### Finishing this ~~fight~~ delivery... 🚛",
                f"1. Gray `{df_state.sett_obj['name']}` button",
                "- `Top up fuel | $XXX` button to refill your resources",
                "- Gray `convoy` button",
                "- Green `Embark on new Journey` button",
                "- Use the `Where to?` dropdown menu to select your delivery destination",
                "  - This destination will have the name of the cargo bound for it in parentheses after its name",
            ])
        case 7:
            tutorial_embed.description = '\n'.join([
                "### ...and now you wait! Desolate Frontiers is an idle game; you'll get a ping when your convoy arrives. 📱",
                "If you're curious about its progress, you can use **`/desolate-frontiers`** to check up on it.",
            ])
        case _:
            tutorial_embed.description = 'tutorial error! 😵‍💫 please ping the devs!'

    embeds.insert(0, tutorial_embed)

    tutorial_embed_footer = TutorialEmbed(author=False)
    tutorial_embed_footer.description = '\n\n-# The tutorial guide is up above!'
    embeds.append(tutorial_embed_footer)

    return embeds


class TutorialEmbed(discord.Embed):
    def __init__(self, author: bool=True):
        super().__init__(color=discord.Color.from_rgb(*OORI_RED))

        if author:
            self.set_author(name='Desolate Frontiers Tutorial', icon_url=DF_LOGO_URL)


DF_HELP = '''\
## Welcome to the **Desolate Frontiers**!

This thing's just out of Alpha, so things *will* break and the game *is not* finished! If you have an issue, please DM Choccy (or just holler in #general)!

- You'll be managing a logistics company, running convoys of land vehicles across the remains of the US, carrying all manner of useful goods. 🚛
- To get started, run **`/desolate-frontiers`** to get your account signed up for our system. You'll also get to name your first convoy there! 💻
  - **Be patient with these buttons, please! Don't button mash!** we're working on speeding up their responsiveness, but we totally understand that it's a bit frustrating that it takes up to 5 seconds to get feedback from pressing them sometimes.
  - Also, **your interaction will time out sometimes!** This is a bit of a technical limitaiton on the discord side of things; we're working on figuring out a more clever solution for this ASAP; it annoys us even more than it annoys you, and it'll annoy you a whole lot!
    - in the meantime, if your interaction times out, you can just call **`/desolate-frontiers`** again!
- Next, you'll need to buy a vehicle. 🚗
  - Use the gray button with a city name to investigate the vendors in the city you spawned in, and head to the dealership to get yourself some wheels.
  - The menus there are a little janky. We're cookin' on 'em!
- After that, you're gonna need to buy some **Fuel** from the gas station, which you can also access from the `city name` button. ⛽️
  - **Your vehicle has a gas tank!** While you can buy more jerry cans if you wanna cary more fuel, you can just buy fuel straight from the blue `buy fuel` button to fill up your tank.
    - Your vehicle doesn't have capacity for water or food, though. That's handled in the next bullet!
  - Next, grab some water from the market; (imaginatively named) **Water Jerry Cans**
  - Finally, you'll wanna buy some **MRE boxes** to feed your crew, also at the market.
  - Note that these jerry cans and MREs you buy are already full! No need to refill them before you move on to the next step.
- With the basics down, it's time for your first delivery. 📦
  - Head to the market once again and look into the goods with a **Profit margin**, which will earn you some money once you bring them to their destination.
- Now that you have a vehicle, prepared resources, and a delivery to fulfill, you're ready to get on the road! 🛣️
  - Use the gray `convoy` button, hit `Embark on new Journey`, and select the destination of the cargo you just bought.
  - Your convoy will present you the path it will take to get there and how many resources you'll use in the process; hit `Embark upon Journey` to send them on their way!
- ...and now you wait! Desolate Frontiers is an idle game; you'll get a ping when your convoy arrives. 📱
  - If you're curious about its progress, you can use **`/desolate-frontiers`** to check up on it.

Happy trails! The game will be updated frequently, and we will be listening closely for any feedback you've got. Have fun!
-# You can show this message at any time with **`/df-help`**
'''
