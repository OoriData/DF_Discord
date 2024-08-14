# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Map image rendering functionality'
from PIL import Image, ImageDraw, ImageFont

TILE_SIZE = 32         # Pixels
GRID_SIZE = 2          # Number of pixels to reduce each side of the tile
FONT_SIZE = 12         # Pixels(?)
FONT_OUTLINE_SIZE = 2  # Pixels

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
ERROR_COLOR = '#FF00FF'  # Error/default color

DEFAULT_HIGHLIGHT_OUTLINE_COLOR = '#FFFF00'  # color for the highlight outline
HIGHLIGHT_OUTLINE_OFFSET = -1                # Number of pixels to offset the highlight outline
HIGHLIGHT_OUTLINE_WIDTH = 9                  # Thickness of the highlight outline

DEFAULT_LOWLIGHT_INLINE_COLOR = '#00FFFF'  # Purple color for lowlight inline
LOWLIGHT_INLINE_OFFSET = 2                 # Number of pixels to offset the lowlight inline
LOWLIGHT_INLINE_WIDTH = 5                  # Thickness of the lowlight inline


def render_map(
        tiles: list[dict],
        highlights: list[tuple]=None,
        lowlights: list[tuple]=None,
        highlight_color=DEFAULT_HIGHLIGHT_OUTLINE_COLOR,
        lowlight_color=DEFAULT_LOWLIGHT_INLINE_COLOR
) -> Image:
    '''
    Renders the game map as an image using Pillow and overlays symbols on specified tiles. Colors can be specified any way that PILlow can interpret; common color name, hex string, RGB tuple, etc
    
    Parameters:
        tiles (list[list[Tile]]): The 2D list representing the game map.
        highlights (list[tuple[int, int]], optional): A list of (x, y) coordinates of the tiles to be highlighted.
        lowlights (list[tuple[int, int]], optional): A list of (x, y) coordinates of the tiles to be lowlighted.
        highlight_color (str, optional): Color for the highlights. Defaults to yellow.
        lowlight_color (str, optional): Color for the lowlights. Defaults to cyan.
    '''

    # Calculate the size of the image
    rows = len(tiles)
    cols = len(tiles[0])
    width = cols * TILE_SIZE
    height = rows * TILE_SIZE

    # Create a new image with a white background
    map_img = Image.new('RGB', (width, height), GRID_COLOR)
    draw = ImageDraw.Draw(map_img)

    for y, row in enumerate(tiles):  # Draw each tile with a slight reduction in size for the grid size
        for x, tile in enumerate(row):
            if tile['settlements']:  # if the tile has a settlement
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

            if lowlights and (x, y) in lowlights:  # Check if this tile is in the lowlights
                draw.rectangle(  # Draw an inline around the lowlight tile
                    [
                        x * TILE_SIZE + LOWLIGHT_INLINE_OFFSET,
                        y * TILE_SIZE + LOWLIGHT_INLINE_OFFSET,
                        (x + 1) * TILE_SIZE - LOWLIGHT_INLINE_OFFSET,
                        (y + 1) * TILE_SIZE - LOWLIGHT_INLINE_OFFSET
                    ],
                    outline=lowlight_color,
                    width=LOWLIGHT_INLINE_WIDTH
                )

            if highlights and (x, y) in highlights:  # Check if this tile is in the highlights
                draw.rectangle(  # Draw an outline around the highlight tile
                    [
                        x * TILE_SIZE + HIGHLIGHT_OUTLINE_OFFSET,
                        y * TILE_SIZE + HIGHLIGHT_OUTLINE_OFFSET,
                        (x + 1) * TILE_SIZE - HIGHLIGHT_OUTLINE_OFFSET,
                        (y + 1) * TILE_SIZE - HIGHLIGHT_OUTLINE_OFFSET
                    ],
                    outline=highlight_color,
                    width=HIGHLIGHT_OUTLINE_WIDTH
                )

    for y, row in enumerate(tiles):  # Annotate the settlements after drawing the tiles
        for x, tile in enumerate(row):
            if tile['settlements']:
                settlement = tile['settlements'][0]  # Assume only one settlement per tile
                settlement_name = settlement['name']

                # Load a default font
                font = ImageFont.load_default(size=FONT_SIZE)

                # Calculate the text bounding box
                bbox = draw.textbbox((0, 0), settlement_name, font=font)
                text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                
                # Calculate the text position (centered on the tile below the current one)
                text_x = x * TILE_SIZE + (TILE_SIZE - text_width) // 2
                text_y = (y + 1) * TILE_SIZE + (TILE_SIZE - text_height) // 2

                draw.text(  # Annotate the settlement name with a black outline
                    xy=(text_x, text_y),
                    text=f'{settlement_name}\n({x}, {y})',
                    fill='white',
                    font=font,
                    align='center',
                    stroke_width=FONT_OUTLINE_SIZE,
                    stroke_fill=GRID_COLOR
                )

    return map_img


if __name__ == '__main__':  # run with: python -m body.df_discord.map_rendering
    import json
    with open('test_map_obj.json', 'r') as map_file:
        df_map_JSON = json.load(map_file)

    highlight_locations = [(40, 40), (41, 41)]
    lowlight_locations = [(4, 26), (5, 26), (6, 26)]
    map_img = render_map(df_map_JSON['tiles'], highlight_locations, lowlight_locations, 'red')

    map_img.show()
