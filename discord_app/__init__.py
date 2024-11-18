# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Discord Frontend'
from __future__             import annotations
from datetime               import datetime

import                             discord

from discord_app.df_state   import DFState


def df_embed_author(embed: discord.Embed, df_state: DFState) -> discord.Embed:
    if df_state.convoy_obj:
        name = f'{df_state.convoy_obj['name']} - ${df_state.convoy_obj['money']:,.0f}'
    elif df_state.user_obj:
        name = f'{df_state.user_obj['username']} - ${df_state.user_obj['money']:,.0f}'
    else:
        name = df_state.interaction.user.display_name

    embed.set_author(
        name=name,
        icon_url=df_state.interaction.user.avatar.url
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
        raise ValueError('The datetime object must be timezone-aware.')

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

DF_HELP = '''\
## Welcome to the **Desolate Frontiers**!

This thing's still in Alpha, so things *will* break and that the game *is not* finished! If you have an issue, please DM Choccy (or just holler in #general)!

- You'll be managing a logistics company, running convoys of land vehicles across the remains of the US, carrying all manner of useful goods. 🚛
- To get started, run **`/desolate-frontiers`** to get your account signed up for our system. You'll also get to name your first convoy there! 💻
  - **Be patient with these buttons, please! Don't button mash!** we're working on speeding up their responsiveness, but we totally understand that it's a bit frustrating that it takes up to 5 seconds to get feedback from pressing them sometimes.
  - Also, **your interaction will time out sometimes!** This is a bit of a technical limitaiton on the discord side of things; we're working on figuring out a more clever solution for this ASAP; it annoys us even more than it annoys you, and it'll annoy you a whole lot!
    - in the meantime, if your interaction times out, you can just call **`/desolate-frontiers`** again!
- Next, you'll need to buy a vehicle. 🚗
  - Use the gray button with a city name to investigate the vendors in the city you spawned in, and head to the ~~dealership~~ stealership to get yourself some wheels.
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
  - Use the gray `convoy` button, hit `Embark on new Journey` **wait a really long time for that menu to load** (we're working on that lag, sorry!), and select the destination of the cargo you just bought.
  - Your convoy will present you the path it will take to get there and how many resources you'll use in the process; hit `Embark upon Journey` to send them on their way!
    - If you picked a really far delivery, you might not be able to make it. You can either make the journey in two parts by going halfway, then later going the rest of the way, or you can go back to the market and buy some more resources.
- ...and now you wait! Desolate Frontiers is an idle game; you'll get a ping when your convoy arrives. 📱
  - If you're curious about its progress, you can use **`/desolate-frontiers`** to check up on it.

Happy trails! The game will be updated frequently, and we will be listening closely for any feedback you've got. Have fun!
-# You can show this message at any time with **`/df-help`**
'''


def add_tutorial_embed(embeds: list[discord.Embed], df_state: DFState) -> discord.Embed:
    if (
        not df_state.convoy_obj.get('user_metadata')
        or not df_state.convoy_obj.get('user_metadata', {}).get('tutorial')
    ):
        return embeds

    ERROR_DESC = 'tutorial error! 😵‍💫 please ping the devs!'
    FOOTER = '\n\n-# If you get "Interaction Timed Out!", just call `/desolate_frontiers` again'

    tutorial_embed = discord.Embed(color=discord.Color.from_rgb(0, 255, 0))
    tutorial_embed.set_author(name='Desolate Frontiers Tutorial', icon_url='https://i.imgur.com/OSPCcye.png')

    match df_state.convoy_obj['user_metadata']['tutorial']:
        case 1:
            tutorial_embed.description = '\n'.join([
                "## Welcome to the **Desolate Frontiers**!",
                "### You aren\'t going anywhere without a vehicle, so you\'ll need to go buy one. 🚗",
                f"1. Hit the gray `{df_state.sett_obj['name']}` button to check out the vendors",
                f"- Use the `Select vendor to visit` dropdown menu to select the `{df_state.sett_obj['name']} stealership`",
                "- Hit the blurple `Buy (Resources, Vehicles, Cargo)` button",
                "- Select the vehicle you'd like to purchase with the `Vehicle Inventory` dropdown",
                "- Inspect the vehicle you've chosen. If it suits you, you can hit the green `Buy Vehicle| $XX,XXX` button.",
                f"  - If you want to inspect a different vehicle, hit the gray `{df_state.sett_obj['name']}` button again to start over.",
            ])
        case 2:
            tutorial_embed.description = '\n'.join([
                "### Now that you have a vehicle, you'll need water and food for your convoy's crew to sustain themselves on their travels. 🍕 💧",
                f"1. Hit the gray `{df_state.sett_obj['name']}` button",
                f"- Use the `Select vendor to visit` dropdown menu to select the `{df_state.sett_obj['name']} Market`",
                "- Hit the blurple `Buy (Resources, Vehicles, Cargo)` button",
                "- Use the `Cargo Inventory` dropdown to select `Water Jerry Cans`",
                "- Hit the blurple `+1` button to add an additional jerry can to your cart",
                "- Hit the green `Buy 2 Water Jerry Cans(s)` button to complete the purchase",
                "  - *`Water Jerry Cans` are sold full of water*",
                "- **Repeat this process, but with the `MRE Boxes`, which contain food**",
                "  - You only need 1 MRE box to get on the road",
                "  - *`MRE Boxes` are also sold with a full compliment of MREs*",
            ])
        case 3:
            tutorial_embed.description = '\n'.join([
                "### Now that you have rations, you're gonna need to buy some fuel as well. The cheap-ass dealership sold you a vehicle with an empty tank. ⛽️",
                f"1. Hit the gray `{df_state.sett_obj['name']}` button",
                "- Hit the `Top up fuel | $XXX` button to fill your empty tank",
                "  - This button is a convenience so that you don't have to bother individually buying all the resources you deplete on your travels",
            ])
        case 4:
            tutorial_embed.description = '\n'.join([
                "### With the basics down, it's time for your first delivery. 📦",
                f"1. One last time, hit the gray `{df_state.sett_obj['name']}` button",
                f"- Use the `Select vendor to visit` dropdown menu to select the `{df_state.sett_obj['name']} Market`",
                "- Hit the blurple `Buy (Resources, Vehicles, Cargo)` button",
                "- Select the cargo you'd like to purchase with the `Cargo Inventory` dropdown",
                "  - The 💵 emojis represent how much profit margin the delivery will net you",
                "  - Consider that alongside the distance you'll have to travel to make the delivery; a high margin delivery which requires you go cross-country will cost you in both time and resources.",
                "- Hit the blurple `max (+X)` button to add the maximum number of this cargo to your cart",
                "  - **if you just hit the green buy button now, you'll only buy one! You want to make big deliveries**",
                "- Hit the green `Buy X cargo(s)` button to complete the purchase",
            ])
        case 5:
            tutorial_embed.description = '\n'.join([
                "### Now that you have a vehicle, prepared resources, and a delivery to fulfill, you're ready to get on the road! 🛣️",
                "1. Hit the gray `convoy` button",
                "- Hit the green `Embark on new Journey` button",
                "- Use the `Where to?` dropdown menu to select the destination of your goods",
                "  - This destination will have the name of the cargo bound for it in parentheses after its name",
                "- If the green `Embark upon Journey` button is enabled, you can hit it to send your convoy on its way!",
                "  - **If the green button is disabled, saying `Not enough resource`, you'll have to make this journey in several steps.**",
                "  - Start this step back from the top, and select a destination in between your current location and the recipient's location instead.",
            ])
        case 6:
            tutorial_embed.description = '\n'.join([
                "### Finishing this ~~fight~~ delivery... 🚛",
                f"1. Hit the gray `{df_state.sett_obj['name']}` button",
                "- Hit the `Top up fuel | $XXX` button to refill your resources",
                "- Hit the gray `convoy` button",
                "- Hit the green `Embark on new Journey` button",
                "- Use the `Where to?` dropdown menu to select the destination of your goods",
                "  - This destination will have the name of the cargo bound for it in parentheses after its name",
                "- If the green `Embark upon Journey` button is enabled, you can hit it to send your convoy on its way!",
                "  - **If the green button is disabled, saying `Not enough resource`, you'll have to make this journey in several steps.**",
                "  - Start this step back from the top, and select a destination in between your current location and the recipient's location instead.",
            ])
        case 7:
            tutorial_embed.description = '\n'.join([
                "### ...and now you wait! Desolate Frontiers is an idle game; you'll get a ping when your convoy arrives. 📱",
                "If you're curious about its progress, you can use **`/desolate-frontiers`** to check up on it.",
            ])
        case _:
            tutorial_embed.description = ERROR_DESC

    tutorial_embed.description += FOOTER

    embeds.append(tutorial_embed)
    return embeds
