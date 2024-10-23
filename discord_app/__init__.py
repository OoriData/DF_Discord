# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Discord Frontend'
from __future__             import annotations
from datetime               import datetime

import                             discord

from discord_app.df_state   import DFState


def df_embed_author(embed: discord.Embed, df_state: DFState) -> discord.Embed:
    if df_state.convoy_obj:
        author_name = f'{df_state.convoy_obj['name']} - ${df_state.convoy_obj['money']:,}'
    elif df_state.user_obj:
        author_name = f'{df_state.user_obj['username']} - ${df_state.user_obj['money']:,}'
    else:
        author_name = df_state.interaction.user.display_name

    embed.set_author(
        name=author_name,
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
  ╚════════════════════════════════════════╝\
'''

DF_HELP = '''\
## Welcome to the **Desolate Frontiers**!

This thing's still in Alpha, so things *will* break and that the game *is not* finished! If you have an issue, please DM Choccy (or just holler in #general)!

1. You'll be managing a logistics company, running convoys of land vehicles across the remains of the US, carrying all manner of useful goods.
- To get started, run **`/df-register`** to get your account signed up for our system. After that, use **`/df-new-convoy`** to create your first convoy!
- Next, you'll need to buy a vehicle. Use **`df-vendors`** to investigate the vendors in the city you spawned in, and head to the ~~dealership~~ stealership to get yourself some wheels. (The menus there are a little janky. We're cookin' on 'em!)
- After that, you're gonna need to buy some *Fuel* from the gas station, which you can also access with **`/df-vendors`**, in the form of `Jerry Cans`. Next, grab some water from the market, (imaginatively named) `Water Jerry Cans`, and finally you'll wanna buy some `MRE boxes` to feed your crew, also at the market.
- With the basics down, it's time for your first delivery. Head to the market once again and look into the goods with a `Recipient`, who will reward you handsomely for bringing them these goods.
- Now that you have a vehicle, prepared resources, and a delivery to fulfill, you're ready to get on the road! Use **`/df-send-convoy`**, and enter the destination of the cargo you just bought. Your convoy will present you the path it will take to get there and how many resources you'll use in the process; hit `Confirm Journey` to send them on their way!
- ...and now you wait! Desolate Frontiers is an idle game; you'll get a ping when your convoy arrives. If you're curious about its progress, you can use **`/df-convoy`** to check up on it.

Happy trails! The game will be updated frequently, and we will be listening closely for any feedback you've got. Have fun!
(You can call this tutorial up at any time with **`/df-help`**)
'''
