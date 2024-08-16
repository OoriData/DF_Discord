# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Discord Frontend'
from datetime import datetime


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
