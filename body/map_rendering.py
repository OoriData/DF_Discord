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

HIGHLIGHT_OUTLINE_COLOR = '#FFFF00'  # color for the highlight outline
HIGHLIGHT_OUTLINE_OFFSET = -1        # Number of pixels to offset the highlight outline
HIGHLIGHT_OUTLINE_WIDTH = 9          # Thickness of the highlight outline

LOWLIGHT_INLINE_COLOR = '#00FFFF'  # Purple color for lowlight inline
LOWLIGHT_INLINE_OFFSET = 2         # Number of pixels to offset the lowlight inline
LOWLIGHT_INLINE_WIDTH = 5          # Thickness of the lowlight inline


def render_map(tiles: list[dict], highlights: list[tuple]=None, lowlights: list[tuple]=None) -> Image:
    '''
    Renders the game map as an image using Pillow and overlays symbols on specified tiles.
    
    Parameters:
        tiles (list[list[Tile]]): The 2D list representing the game map.
        highlights (list[tuple[int, int]], optional): A list of (x, y) coordinates of the tiles to be highlighted.
        lowlights (list[tuple[int, int]], optional): A list of (x, y) coordinates of the tiles to be lowlighted.
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

            if lowlights and (x, y) in lowlights:  # Check if this tile is in the route
                draw.rectangle(  # Draw an inline around the route tiles
                    [
                        x * TILE_SIZE + LOWLIGHT_INLINE_OFFSET,
                        y * TILE_SIZE + LOWLIGHT_INLINE_OFFSET,
                        (x + 1) * TILE_SIZE - LOWLIGHT_INLINE_OFFSET,
                        (y + 1) * TILE_SIZE - LOWLIGHT_INLINE_OFFSET
                    ],
                    outline=LOWLIGHT_INLINE_COLOR,
                    width=LOWLIGHT_INLINE_WIDTH
                )

            if highlights and (x, y) in highlights:  # Check if this tile is in the highlights
                draw.rectangle(  # Draw an outline around the highlight tiles
                    [
                        x * TILE_SIZE + HIGHLIGHT_OUTLINE_OFFSET,
                        y * TILE_SIZE + HIGHLIGHT_OUTLINE_OFFSET,
                        (x + 1) * TILE_SIZE - HIGHLIGHT_OUTLINE_OFFSET,
                        (y + 1) * TILE_SIZE - HIGHLIGHT_OUTLINE_OFFSET
                    ],
                    outline=HIGHLIGHT_OUTLINE_COLOR,
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


# ━━━━━━ ⬇ test map rendering ⬇ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# run with:
# python -m body.map_rendering
def to_dict(obj):
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, '__dict__'):
        return {k: to_dict(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [to_dict(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(to_dict(i) for i in obj)
    else:
        return obj


if __name__ == '__main__':
    from chassis.df_obj       import Map
    from trunk.df_terrain     import NA_TERRAIN
    from trunk.df_settlements import NA_SETTLEMENTS
    from trunk.df_politics    import NA_POLITICS

    df_map = Map.from_raw_lists(NA_TERRAIN, NA_SETTLEMENTS, NA_POLITICS)

    df_map_JSON = to_dict(df_map)

    highlight_locations = [(40, 40), (41, 41)]
    route = [(4, 26), (5, 26), (6, 26)]
    map_img = render_map(df_map_JSON['tiles'], highlight_locations, route)

    map_img.show()
