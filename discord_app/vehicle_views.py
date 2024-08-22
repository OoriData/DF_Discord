# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap

import                                discord

from discord_app               import discord_timestamp
from discord_app               import api_calls
from discord_app.map_rendering import add_map_to_embed

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


# async def make_vehicle_embed(interaction, convoy_obj, prospective_journey_plus_misc=None) -> discord.Embed:
#     convoy_embed = discord.Embed(
#         color=discord.Color.green(),
#         title=f'{convoy_obj['name']} Information'
#     )
    
#     convoy_embed.description = vehicles_embed_str(convoy_obj['vehicles'])

#     convoy_embed.set_author(
#         name=f'{convoy_obj['name']} | ${convoy_obj['money']:,}',
#         icon_url=interaction.user.avatar.url
#     )

#     convoy_embed.add_field(name='Fuel ⛽️', value=textwrap.dedent(f'''\
#         **{convoy_obj['fuel']:.2f}**
#         /{convoy_obj['max_fuel']:.2f} liters
#     '''))
#     convoy_embed.add_field(name='Water 💧', value=textwrap.dedent(f'''\
#         **{convoy_obj['water']:.2f}**
#         /{convoy_obj['max_water']:.2f} liters
#     '''))
#     convoy_embed.add_field(name='Food 🥪', value=textwrap.dedent(f'''\
#         **{convoy_obj['food']:.2f}**
#         /{convoy_obj['max_food']:.2f} meals
#     '''))

#     convoy_embed.add_field(name='Fuel Efficiency', value=textwrap.dedent(f'''\
#         **{convoy_obj['fuel_efficiency']:.0f}**
#         /100
#     '''))
#     convoy_embed.add_field(name='Top Speed', value=textwrap.dedent(f'''\
#         **{convoy_obj['top_speed']:.0f}**
#         /100
#     '''))
#     convoy_embed.add_field(name='Offroad Capability', value=textwrap.dedent(f'''\
#         **{convoy_obj['offroad_capability']:.0f}**
#         /100
#     '''))

#     convoy_x = convoy_obj['x']
#     convoy_y = convoy_obj['y']

#     if convoy_obj['journey']:  # If the convoy is in transit
#         journey = convoy_obj['journey']
#         route_tiles = []  # a list of tuples
#         pos = 0  # bad way to do it but i'll fix later
#         for x in journey['route_x']:
#             y = journey['route_y'][pos]
#             route_tiles.append((x, y))
#             pos += 1

#         destination = await api_calls.get_tile(journey['dest_x'], journey['dest_y'])
#         convoy_embed.add_field(name='Destination 📍', value=textwrap.dedent(f'''\
#             **{destination['settlements'][0]['name']}**
#             ({journey['dest_x']}, {journey['dest_y']})
#         '''))  # XXX: replace coords with `{territory_name}`

#         eta = convoy_obj['journey']['eta']
#         convoy_embed.add_field(name='ETA ⏰', value=textwrap.dedent(f'''\
#             **{discord_timestamp(eta, 'R')}**
#             {discord_timestamp(eta, 't')}
#         '''))

#         progress_percent = ((convoy_obj['journey']['progress'] - 1) / len(convoy_obj['journey']['route_x'])) * 100
#         progress_in_km = convoy_obj['journey']['progress'] * 50  # progress is measured in tiles; tiles are 50km to a side
#         convoy_embed.add_field(name='Progress 🚗', value=textwrap.dedent(f'''\
#             **{progress_percent:.0f}%**
#             {progress_in_km:.0f} km
#         '''))

#         origin_x = journey['origin_x']
#         origin_y = journey['origin_y']
#         destination_x = journey['dest_x']
#         destination_y = journey['dest_y']

#         if origin_x < destination_x:
#             min_x = origin_x
#             max_x = destination_x
#         else:
#             min_x = destination_x
#             max_x = origin_x
        
#         # Declaring minimum and maximum y coordinates
#         if origin_y < destination_y:
#             min_y = origin_y
#             max_y = destination_y
#         else:
#             min_y = destination_y
#             max_y = origin_y
            
#         x_padding = 3
#         y_padding = 3

#         convoy_embed, image_file = await add_map_to_embed(
#             embed=convoy_embed,
#             highlighted=[(convoy_x, convoy_y)],
#             lowlighted=route_tiles,
#             top_left=(min_x - x_padding, min_y - y_padding),
#             bottom_right=(max_x + x_padding, max_y + y_padding),
#         )

#     elif prospective_journey_plus_misc:  # If a journey is being considered
#         route_tiles = []  # a list of tuples
#         pos = 0  # bad way to do it but i'll fix later
#         for x in prospective_journey_plus_misc['journey']['route_x']:
#             y = prospective_journey_plus_misc['journey']['route_y'][pos]
#             route_tiles.append((x, y))
#             pos += 1

#         destination = await api_calls.get_tile(prospective_journey_plus_misc['journey']['dest_x'], prospective_journey_plus_misc['journey']['dest_y'])

#         convoy_embed.add_field(name='Destination 📍', value=textwrap.dedent(f'''\
#             **{destination['settlements'][0]['name']}**
#             ({prospective_journey_plus_misc['journey']['dest_x']}, {prospective_journey_plus_misc['journey']['dest_y']})
#         '''))  # XXX: replace coords with `{territory_name}`
        
#         delta_t = discord_timestamp(datetime.now(timezone.utc) + timedelta(minutes=prospective_journey_plus_misc['delta_t']), 'R')
#         eta_discord_time = discord_timestamp(datetime.now(timezone.utc) + timedelta(minutes=prospective_journey_plus_misc['delta_t']), 't')
#         convoy_embed.add_field(name='ETA ⏰', value=textwrap.dedent(f'''\
#             **{delta_t}**
#             {eta_discord_time}
#         '''))

#         origin_x = prospective_journey_plus_misc['journey']['origin_x']
#         origin_y = prospective_journey_plus_misc['journey']['origin_y']
#         destination_x = prospective_journey_plus_misc['journey']['dest_x']
#         destination_y = prospective_journey_plus_misc['journey']['dest_y']

#         if origin_x < destination_x:
#             min_x = origin_x
#             max_x = destination_x
#         else:
#             min_x = destination_x
#             max_x = origin_x
        
#         # Declaring minimum and maximum y coordinates
#         if origin_y < destination_y:
#             min_y = origin_y
#             max_y = destination_y
#         else:
#             min_y = destination_y
#             max_y = origin_y
            
#         x_padding = 3
#         y_padding = 3

#         convoy_embed, image_file = await add_map_to_embed(
#             embed=convoy_embed,
#             highlighted=[(convoy_x, convoy_y)],
#             lowlighted=route_tiles,
#             top_left=(min_x - x_padding, min_y - y_padding),
#             bottom_right=(max_x + x_padding, max_y + y_padding),
#         )

#     else:  # If the convoy is just chilling somewhere
#         x_padding = 16
#         y_padding = 9

#         top_left = (convoy_x - x_padding, convoy_y - y_padding)
#         bottom_right = (convoy_x + x_padding, convoy_y + y_padding)

#         convoy_embed, image_file = await add_map_to_embed(
#             embed=convoy_embed,
#             highlighted=[(convoy_x, convoy_y)],
#             top_left=top_left,
#             bottom_right=bottom_right
#         )

#     return convoy_embed, image_file
