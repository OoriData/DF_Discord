# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Map image rendering functionality'
from PIL import Image, ImageDraw, ImageColor, ImageFont
from io import BytesIO
from typing import Optional

import discord
import logging
import httpx
import os
API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.environ.get('DF_API_HOST')

TILE_SIZE = 32         # Pixels
GRID_SIZE = 2          # Number of pixels to reduce each side of the tile
FONT_SIZE = 12         # Pixels
FONT_OUTLINE_SIZE = 2  # Pixels
FONT = ImageFont.load_default(size=FONT_SIZE)  # Load a default font

GRID_COLOR = '#202020'   # Background grid color
TILE_COLORS = {
    1: '#303030',   # Highway
    2: '#606060',   # Road
    3: '#CB8664',   # Trail
    4: '#F6D0B0',   # Desert
    5: '#3F5D4B',   # Plains
    6: '#2C412E',   # Forest
    7: '#2A4B46',   # Swamp
    8: '#273833',   # Mountains
    9: '#0F2227',   # Near Impassable
    0: '#142C55',   # Impassable/Ocean
    -1: '#9900FF',  # Marked
}
SETTLEMENT_COLORS = {
    'dome': '#80A9B6',
    'city': '#ADADAD',
    'town': '#A1662F',
    'city-state': '#581B63',
    'military_base': '#800000'
}
POLITICAL_COLORS = {
    0: '#00000000',   # Null (transparent)
    1: '#00000000',   # Desolate plains
    2: '#00000000',   # Desolate forest
    3: '#00000000',   # Desolate desert
    4: '#00000000',   # Desolate mountains
    5: '#00000000',   # Desolate 
    6: '#00000000',   # Desolate Swamp
    9: '#00000000',   # Device Detonation Zone
    10: '#D5A6BD',    # Chicago
    11: '#D5A6BD',    # Indianapolis
    13: '#D5A6BD',    # Detroit
    14: '#D5A6BD',    # Cleveland
    15: '#D5A6BD',    # Buffalo
    19: '#D5A6BD',    # The Heartland
    20: '#B4A7D6',    # Kansas City
    21: '#B4A7D6',    # St. Louis
    22: '#B4A7D6',    # Des Moines
    29: '#B4A7D6',    # The Breadbasket
    30: '#B6D7A8',    # Minneapolis
    31: '#B6D7A8',    # Fargo
    32: '#B6D7A8',    # Milwaukee
    39: '#B6D7A8',    # Northern Lights
    40: '#FFE599',    # New York
    41: '#FFE599',    # Boston
    42: '#FFE599',    # Philadelphia
    49: '#FFE599',    # New New England
    50: '#F6B26B',    # Nashville
    51: '#F6B26B',    # Memphis
    52: '#F6B26B',    # Knoxville
    59: '#F6B26B',    # Greater Tennessee
    60: '#E06666',    # Charlotte
    61: '#E06666',    # Norfolk
    62: '#E06666',    # Richmond
    63: '#E06666',    # Minot AFB
    64: '#E06666',    # Vandenberg AFB
    69: '#E06666',    # Republic of the South Atlantic
    70: '#38761E',    # Jacksonville
    71: '#38761E',    # Tallahassee
    72: '#38761E',    # Orlando
    73: '#38761E',    # Miami
    74: '#38761E',    # New Orleans
    79: '#38761E',    # Gulf Cities
    80: '#B45F05',    # Austin
    81: '#B45F05',    # San Antonio
    82: '#B45F05',    # Dallas
    83: '#B45F05',    # Houston
    85: '#B45F05',    # Oklahoma City
    89: '#B45F05',    # Republic of Texas
    90: '#0A5394',    # Denver
    91: '#0A5394',    # Cheyenne
    92: '#0A5394',    # Colorado Springs
    99: '#0A5394',    # Front Range Collective
    100: '#A61C00',   # Los Angeles
    101: '#A61C00',   # San Diego
    102: '#A61C00',   # Phoenix
    103: '#A61C00',   # Tucson
    109: '#A61C00',   # States of Solara
    110: '#674EA7',   # San Francisco
    111: '#674EA7',   # Fresno
    112: '#674EA7',   # Sacramento
    119: '#674EA7',   # The Golden Bay
    120: '#BF9000',   # Seattle
    121: '#BF9000',   # Portland
    122: '#BF9000',   # Spokane
    129: '#BF9000',   # Cascadia
    130: '#783F04',   # Be'eldííl Dah Sinil
    131: '#783F04',   # Ysleta
    139: '#783F04',   # Desert Twins
    140: '#FFF3CC',   # Las Vegas
    141: '#FFF3CC',   # Boise Mountain Commune
    142: '#FFF3CC',   # Salt Lake City
    143: '#FFF3CC',   # Little Rock
    144: '#FFF3CC',   # Birmingham
    145: '#FFF3CC',   # Atlanta
    146: '#FFF3CC',   # Charleston
    170: '#FF0000',   # Badlanders
    171: '#FF0000',   # Badland Outposts
    172: '#FF0000'    # Appalacian Wastelanders
}
ERROR_COLOR = '#FF00FF'  # Error/default color

POLITICAL_INLINE_OFFSET = 2                  # Number of pixels to offset the political inline
POLITICAL_INLINE_WIDTH = 1                   # Thickness of the political inline

DEFAULT_HIGHLIGHT_OUTLINE_COLOR = '#FFFF00'  # color for the highlight outline
HIGHLIGHT_OUTLINE_OFFSET = -1                # Number of pixels to offset the highlight outline
HIGHLIGHT_OUTLINE_WIDTH = 9                  # Thickness of the highlight outline

DEFAULT_LOWLIGHT_INLINE_COLOR = '#00FFFF'    # Purple color for lowlight inline
LOWLIGHT_INLINE_OFFSET = 2                   # Number of pixels to offset the lowlight inline
LOWLIGHT_INLINE_WIDTH = 5                    # Thickness of the lowlight inline


def render_map(
        tiles: list[dict],
        highlights: list[tuple] = None,
        lowlights: list[tuple] = None,
        highlight_color=DEFAULT_HIGHLIGHT_OUTLINE_COLOR,
        lowlight_color=DEFAULT_LOWLIGHT_INLINE_COLOR
) -> Image:
    '''
    Renders the game map as an image using Pillow and overlays symbols on specified tiles.
    Colors can be specified any way that PILlow can interpret; common color name, hex string, RGB tuple, etc
    
    Parameters:
        tiles (list[list[dict]]): The 2D list representing the game map.
        highlights (list[tuple[int, int]], optional): A list of (x, y) coordinates of the tiles to be highlighted.
        lowlights (list[tuple[int, int]], optional): A list of (x, y) coordinates of the tiles to be lowlighted.
        highlight_color (str, optional): Color for the highlights. Defaults to yellow.
        lowlight_color (str, optional): Color for the lowlights. Defaults to cyan.
    '''
    def draw_tile_bg(x, y, tile):
        if tile['settlements']:
            color = SETTLEMENT_COLORS.get(tile['settlements'][0]['sett_type'], ERROR_COLOR)
        else:
            color = TILE_COLORS.get(tile['terrain_difficulty'], ERROR_COLOR)

        draw.rectangle(
            [
                x * TILE_SIZE + GRID_SIZE,
                y * TILE_SIZE + GRID_SIZE,
                (x + 1) * TILE_SIZE - GRID_SIZE,
                (y + 1) * TILE_SIZE - GRID_SIZE
            ],
            fill=color
        )

    def draw_political_inline(x, y, tile):
        political_color = POLITICAL_COLORS.get(tile['region'], ERROR_COLOR)

        if ImageColor.getcolor(political_color, 'RGBA')[3] != 0:  # if the political color is not transparent
            draw.rectangle(  # Draw a political inline around the tile
                [
                    x * TILE_SIZE + POLITICAL_INLINE_OFFSET,
                    y * TILE_SIZE + POLITICAL_INLINE_OFFSET,
                    (x + 1) * TILE_SIZE - POLITICAL_INLINE_OFFSET,
                    (y + 1) * TILE_SIZE - POLITICAL_INLINE_OFFSET
                ],
                outline=political_color,
                width=POLITICAL_INLINE_WIDTH
            )

    def draw_highlight(x, y):
        if highlights and (x, y) in highlights:  # Check if this tile is in the highlights
            draw.rectangle(  # Draw an outline around this tile if it's a highlight
                [
                    x * TILE_SIZE + HIGHLIGHT_OUTLINE_OFFSET,
                    y * TILE_SIZE + HIGHLIGHT_OUTLINE_OFFSET,
                    (x + 1) * TILE_SIZE - HIGHLIGHT_OUTLINE_OFFSET,
                    (y + 1) * TILE_SIZE - HIGHLIGHT_OUTLINE_OFFSET
                ],
                outline=highlight_color,
                width=HIGHLIGHT_OUTLINE_WIDTH
            )

    def draw_lowlight(x, y):
        if lowlights and (x, y) in lowlights:  # Check if this tile is in the lowlights
            draw.rectangle(  # Draw an inline around this tile if it's a lowlight
                [
                    x * TILE_SIZE + LOWLIGHT_INLINE_OFFSET,
                    y * TILE_SIZE + LOWLIGHT_INLINE_OFFSET,
                    (x + 1) * TILE_SIZE - LOWLIGHT_INLINE_OFFSET,
                    (y + 1) * TILE_SIZE - LOWLIGHT_INLINE_OFFSET
                ],
                outline=lowlight_color,
                width=LOWLIGHT_INLINE_WIDTH
            )

    def annotate_settlements(x, y, tile):
        if tile['settlements']:
            settlement = tile['settlements'][0]  # Assume only one settlement per tile
            settlement_name = settlement['name']

            # Calculate the text bounding box
            bbox = draw.textbbox((0, 0), settlement_name, font=FONT)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]

            # Calculate the text position (centered on the tile below the current one)
            text_x = x * TILE_SIZE + (TILE_SIZE - text_width) // 2
            text_y = (y + 0.4) * TILE_SIZE + (TILE_SIZE - text_height) // 2

            draw.text(  # Annotate the settlement name with a black outline
                xy=(text_x, text_y),
                text=settlement_name,
                fill='white',
                font=FONT,
                align='center',
                stroke_width=FONT_OUTLINE_SIZE,
                stroke_fill=GRID_COLOR
            )

    # Calculate the size of the image
    rows = len(tiles)
    cols = len(tiles[0])
    width = cols * TILE_SIZE
    height = rows * TILE_SIZE

    # Create a new image with the grid color as the background
    map_img = Image.new('RGB', (width, height), GRID_COLOR)
    draw = ImageDraw.Draw(map_img)

    for y, row in enumerate(tiles):  # Render the map
        for x, tile in enumerate(row):
            draw_tile_bg(x, y, tile)
            draw_political_inline(x, y, tile)
            draw_lowlight(x, y)
            draw_highlight(x, y)

    for y, row in enumerate(tiles):  # Annotate settlements after drawing the tiles
        for x, tile in enumerate(row):
            annotate_settlements(x, y, tile)

    return map_img

async def add_map_to_embed(
        embed: discord.Embed,  # TODO: make this optional
        highlighted: Optional[list[tuple[int]]]=None,
        lowlighted: Optional[list[tuple[int]]]=None,
        top_left: Optional[tuple[int]]=None,
        bottom_right: Optional[tuple[int]]=None,
        highlight_color: Optional[str]=None,
        lowlight_color: Optional[str]=None
) -> discord.Embed | discord.File:
    '''Renders map as an image and formats it into a Discord embed object, and also returns a image file'''
    if top_left and bottom_right:
        map_edges = {
            'x_min': top_left[0],
            'x_max': bottom_right[0],
            'y_min': top_left[1],
            'y_max': bottom_right[1]
        }

        # Adjust the highlight and lowlight coordinates based on the top-left corner
        if highlighted:
            highlighted = [(x - top_left[0], y - top_left[1]) for x, y in highlighted]

        if lowlighted:
            lowlighted = [(x - top_left[0], y - top_left[1]) for x, y in lowlighted]
    else:
        map_edges = None

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                url=f'{DF_API_HOST}/map/get',
                params=map_edges
            )
            if response.status_code == API_UNPROCESSABLE_ENTITY_CODE:
                logging.log(level='INFO', msg='Error: 422 Unprocessable')
            elif response.status_code == API_SUCCESS_CODE:
                tiles = response.json()['tiles']
                rendered_map = render_map(tiles, highlighted, lowlighted, highlight_color, lowlight_color)

                # Create a BytesIO object to save the image in memory
                with BytesIO() as image_binary:
                    rendered_map.save(image_binary, 'PNG')  # Save the image to the BytesIO object
                    image_binary.seek(0)  # Move the cursor to the beginning of the BytesIO object

                    file_name = 'map.png'
                    img_file = discord.File(fp=image_binary, filename=file_name)  # Declare a discord.File object to include in the response

                    embed.set_image(url=f'attachment://{file_name}')  # I guess Discord.py handles files in the backend, and stores them as a filepath which you can access with attachment:// (i hope that makes sense)

                    return embed, img_file
                    # Now all you have to do to apply this is:
                    # await interaction.response.send_message(embed=embed, file=img_file)

    except Exception as e:
        msg = f'something went wrong rendering image: {e}'
        logging.log(msg=msg, level='INFO')


def truncate_2d_list(matrix, top_left, bottom_right):
    'just a "zoom" function for testing with'
    x1, y1 = top_left
    x2, y2 = bottom_right

    # Check bounds to avoid IndexError
    if x1 < 0 or y1 < 0 or x2 >= len(matrix[0]) or y2 >= len(matrix):
        raise ValueError('Coordinates are out of bounds')

    # Extract the submatrix
    return [row[x1:x2 + 1] for row in matrix[y1:y2 + 1]]


if __name__ == '__main__':
    import json
    with open('test_map_obj.json', 'r') as map_file:
        df_map_JSON = json.load(map_file)

    highlight_locations = [(40, 40), (41, 41)]
    lowlight_locations = [(4, 26), (5, 26), (6, 26)]
    map_img = render_map(df_map_JSON['tiles'], highlight_locations, lowlight_locations, 'red')

    # small_map = truncate_2d_list(df_map_JSON['tiles'], (25, 19), (39, 33))
    # map_img = render_map(small_map)

    map_img.show()
