# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Discord Frontend'
from datetime import datetime

import               discord


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


def df_embed_author(embed: discord.Embed, convoy, user: discord.User):
    embed.set_author(
        name=f'{convoy['name']} | ${convoy['money']:,}',
        icon_url=user.avatar.url
    )
    return embed


def df_embed_vehicle_stats(embed: discord.Embed, vehicle):
    embed.add_field(name='💵 Value', value=f'${vehicle['value']:,}')
    embed.add_field(name='🔧 Wear', value=f'{vehicle['wear']} / 100')
    embed.add_field(name='🛡️ AP', value=f'{vehicle['ap']} / {vehicle['max_ap']}')
    embed.add_field(name='⛽️ Fuel Efficiency', value=f'{vehicle['fuel_efficiency']} / 100')
    embed.add_field(name='🏎️ Top Speed', value=f'{vehicle['top_speed']} / 100')
    embed.add_field(name='🏔️ Off-road Capability', value=f'{vehicle['offroad_capability']} / 100')
    embed.add_field(name='📦 Cargo Capacity', value=f'{vehicle['cargo_capacity']:,} L')
    embed.add_field(name='🏋️ Weight Capacity', value=f'{vehicle['weight_capacity']:,} kg')
    embed.add_field(name='🚛 Towing Capacity', value=f'{vehicle['towing_capacity']:,} kg')
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
