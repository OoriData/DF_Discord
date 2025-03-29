# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Map image rendering functionality'
import                  os
from io          import BytesIO

import                  discord

from discord_app import api_calls

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.environ.get('DF_API_HOST')


async def add_map_to_embed(
        embed: discord.Embed | None = None,
        highlights: list[tuple[int, int]] | None = None,
        lowlights: list[tuple[int, int]] | None = None,
        highlight_color: str | None = None,
        lowlight_color: str | None = None,
        map_obj = None
) -> tuple[discord.Embed, discord.File]:
    """
    Renders map as an image and formats it into a Discord embed object,
    and also returns an image file.

    Arguments:
    - embed: Optional discord.Embed object (can be None, in which case a new one is created).
    - highlights: Optional list of (x, y) tuples for highlighting coordinates.
    - lowlights: Optional list of (x, y) tuples for lowlighting coordinates.
    - highlight_color: Optional color to use for highlighting.
    - lowlight_color: Optional color to use for lowlighting.

    Returns:
    - A tuple containing the updated embed and the image file for the map.
    """
    # Create a new embed if one is not provided
    if embed is None:
        embed = discord.Embed()

    # Initialize the boundaries for the API call and padding
    map_edges = {'x_min': None, 'x_max': None, 'y_min': None, 'y_max': None}
    x_padding = y_padding = 0  # Defaults, will adjust based on coordinates

    if highlights or lowlights:
        # Compute boundaries if any coordinates are provided
        if highlights:
            highlight_x_values = [coord[0] for coord in highlights]
            highlight_y_values = [coord[1] for coord in highlights]
        else:
            highlight_x_values = []
            highlight_y_values = []

        if lowlights:
            lowlight_x_values = [coord[0] for coord in lowlights]
            lowlight_y_values = [coord[1] for coord in lowlights]
        else:
            lowlight_x_values = []
            lowlight_y_values = []

        # Find the minimum and maximum x and y values for both highlights and lowlights
        if highlight_x_values or lowlight_x_values:
            x_min = min(highlight_x_values + lowlight_x_values, default=0)
            x_max = max(highlight_x_values + lowlight_x_values, default=0)
            y_min = min(highlight_y_values + lowlight_y_values, default=0)
            y_max = max(highlight_y_values + lowlight_y_values, default=0)

            # Apply padding consistently and ensure minimum boundary is 0
            x_padding = 3 if x_min != x_max else 16
            y_padding = 3 if y_min != y_max else 9

            map_edges = {
                'x_min': max(0, x_min - x_padding),
                'x_max': x_max + x_padding,
                'y_min': max(0, y_min - y_padding),
                'y_max': y_max + y_padding
            }

            # Adjust highlight and lowlight coordinates relative to the top-left corner
            top_left = (map_edges['x_min'], map_edges['y_min'])
            if highlights:
                highlights = [(max(0, x - top_left[0]), max(0, y - top_left[1])) for x, y in highlights]
            if lowlights:
                lowlights = [(max(0, x - top_left[0]), max(0, y - top_left[1])) for x, y in lowlights]

    else:
        # No highlights or lowlights provided, don't compute boundaries
        map_edges = None  # Pass nothing for boundaries to the API

    try:
        # Fetch tiles for the map (map_edges will be None if no boundaries are needed)
        if map_edges:
            # tiles = (await api_calls.get_map(**map_edges))['tiles']
            tiles = truncate_2d_list(
                matrix=map_obj['tiles'],
                top_left=(map_edges['x_min'], map_edges['y_min']),
                bottom_right=(map_edges['x_max'], map_edges['y_max'])
            )
        else:
            # tiles = (await api_calls.get_map())['tiles']
            tiles = map_obj['tiles']

        # Render the map with the given tiles and any highlights or lowlights
        rendered_map_bytes = await api_calls.render_map(tiles, highlights, lowlights, highlight_color, lowlight_color)

        # Save the rendered map to an in-memory file (BytesIO object)
        with BytesIO(rendered_map_bytes) as image_binary:
            image_binary.seek(0)

            file_name = 'map.png'
            img_file = discord.File(fp=image_binary, filename=file_name)

        # Attach the image file to the embed
        embed.set_image(url=f'attachment://{file_name}')

        return embed, img_file

    except Exception as e:
        msg = f'something went wrong rendering image: {e}'
        raise RuntimeError(msg) from e


def truncate_2d_list(matrix, top_left, bottom_right):
    x1, y1 = top_left
    x2, y2 = bottom_right

    # Clamp coordinates to fit within bounds
    x1 = max(0, min(x1, len(matrix[0]) - 1))
    y1 = max(0, min(y1, len(matrix) - 1))
    x2 = max(0, min(x2, len(matrix[0]) - 1))
    y2 = max(0, min(y2, len(matrix) - 1))

    # Extract the submatrix
    return [row[x1:x2 + 1] for row in matrix[y1:y2 + 1]]
