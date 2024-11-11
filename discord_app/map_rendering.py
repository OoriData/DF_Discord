# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Map image rendering functionality'
import                  os
from io          import BytesIO
from typing      import Optional
# import                  logging

import                  discord
# import                  httpx

from discord_app import api_calls

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.environ.get('DF_API_HOST')


from typing import Optional, Tuple
import discord
from io import BytesIO

async def add_map_to_embed(
        embed: Optional[discord.Embed] = None,
        highlighted: Optional[list[tuple[int, int]]] = None,
        lowlighted: Optional[list[tuple[int, int]]] = None,
        highlight_color: Optional[str] = None,
        lowlight_color: Optional[str] = None
) -> Tuple[discord.Embed, discord.File]:
    '''
    Renders map as an image and formats it into a Discord embed object, 
    and also returns an image file.
    
    Arguments:
    - embed: Optional discord.Embed object (can be None, in which case a new one is created).
    - highlighted: Optional list of (x, y) tuples for highlighting coordinates.
    - lowlighted: Optional list of (x, y) tuples for lowlighting coordinates.
    - highlight_color: Optional color to use for highlighting.
    - lowlight_color: Optional color to use for lowlighting.
    
    Returns:
    - A tuple containing the updated embed and the image file for the map.
    '''
    # Create a new embed if one is not provided
    if embed is None:
        embed = discord.Embed()
    
    # Initialize the boundaries for the API call and padding
    map_edges = {'x_min': None, 'x_max': None, 'y_min': None, 'y_max': None}
    x_padding = y_padding = 0  # Defaults, will adjust based on coordinates

    if highlighted or lowlighted:
        # Compute boundaries if any coordinates are provided
        if highlighted:
            highlight_x_values = [coord[0] for coord in highlighted]
            highlight_y_values = [coord[1] for coord in highlighted]
        else:
            highlight_x_values = []
            highlight_y_values = []

        if lowlighted:
            lowlight_x_values = [coord[0] for coord in lowlighted]
            lowlight_y_values = [coord[1] for coord in lowlighted]
        else:
            lowlight_x_values = []
            lowlight_y_values = []

        # Find the minimum and maximum x and y values for both highlights and lowlights
        if highlight_x_values or lowlight_x_values:
            x_min = min(highlight_x_values + lowlight_x_values, default=0)
            x_max = max(highlight_x_values + lowlight_x_values, default=0)
            y_min = min(highlight_y_values + lowlight_y_values, default=0)
            y_max = max(highlight_y_values + lowlight_y_values, default=0)

            # Apply some padding unless there's only one point
            if x_min == x_max and y_min == y_max:
                x_padding = 16
                y_padding = 9
            else:
                x_padding = 3
                y_padding = 3

            # Set the map edges, adjusted by padding
            map_edges = {
                'x_min': x_min - x_padding,
                'x_max': x_max + x_padding,
                'y_min': y_min - y_padding,
                'y_max': y_max + y_padding
            }

            # Adjust highlight and lowlight coordinates relative to the top-left corner
            top_left = (map_edges['x_min'], map_edges['y_min'])
            if highlighted:
                highlighted = [(x - top_left[0], y - top_left[1]) for x, y in highlighted]
            if lowlighted:
                lowlighted = [(x - top_left[0], y - top_left[1]) for x, y in lowlighted]

    else:
        # No highlights or lowlights provided, don't compute boundaries
        map_edges = None  # Pass nothing for boundaries to the API
    
    try:
        # Fetch tiles for the map (map_edges will be None if no boundaries are needed)
        if map_edges:
            tiles = (await api_calls.get_map(**map_edges))['tiles']
        else:
            tiles = (await api_calls.get_map())['tiles']

        # Render the map with the given tiles and any highlights or lowlights
        rendered_map_bytes = await api_calls.render_map(tiles, highlighted, lowlighted, highlight_color, lowlight_color)

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
        raise RuntimeError(msg)


def truncate_2d_list(matrix, top_left, bottom_right):
    'just a "zoom" function for testing with'
    x1, y1 = top_left
    x2, y2 = bottom_right

    # Check bounds to avoid IndexError
    if x1 < 0 or y1 < 0 or x2 >= len(matrix[0]) or y2 >= len(matrix):
        raise ValueError('Coordinates are out of bounds')

    # Extract the submatrix
    return [row[x1:x2 + 1] for row in matrix[y1:y2 + 1]]
