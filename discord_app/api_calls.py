# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import           os
from uuid import UUID

import           httpx

from df_lib.map_struct import serialize_map, deserialize_map

DF_API_HOST = os.environ['DF_API_HOST']
DF_MAP_RENDERER = os.environ['DF_MAP_RENDERER']
API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
API_INTERNAL_SERVER_ERROR = 500


def _check_code(response: httpx.Response):
    if response.status_code == API_INTERNAL_SERVER_ERROR:
        msg = 'API Internal Server Error'
        raise RuntimeError(msg)
    elif response.status_code != API_SUCCESS_CODE:
        msg = response.json()['detail']
        raise RuntimeError(msg)


async def render_map(
        tiles: list[list[dict]],
        highlights: list[list] | None = None,
        lowlights: list[list] | None = None,
        highlight_color = None,
        lowlight_color = None
):
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_MAP_RENDERER}/render-map',
            headers={'Content-Type': 'application/octet-stream'},
            data=serialize_map({
                'tiles': tiles,
                'highlights': highlights,
                'lowlights': lowlights
            }),
            params={
                'highlight_color': highlight_color,
                'lowlight_color': lowlight_color
            }
        )
    
    # Check response status
    _check_code(response)

    # Read the response content as bytes
    return await response.aread()


async def get_map(
        x_min: int | None = None,
        x_max: int | None = None,
        y_min: int | None = None,
        y_max: int | None = None
) -> dict:
    params = {}

    if x_min is not None:  # Add parameters only if they are not None
        params['x_min'] = x_min
    if x_max is not None:
        params['x_max'] = x_max
    if y_min is not None:
        params['y_min'] = y_min
    if y_max is not None:
        params['y_max'] = y_max

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/map/get',
            params=params,
            timeout=10
        )

    _check_code(response)
    return deserialize_map(response.content)


async def get_tile(x: int, y: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/map/tile/get',
            params={
                'x': x,
                'y': y
            }
        )

    _check_code(response)
    return response.json()


async def new_user(username: str, discord_id: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/user/new',
            params={
                'username': username,
                'discord_id': discord_id
            }
        )

    _check_code(response)
    return response.json()


async def get_user(user_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/user/get',
            params={'user_id': user_id}
        )

    _check_code(response)
    return response.json()


async def get_user_by_discord(discord_id: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/user/get_by_discord_id',
            params={'discord_id': discord_id}
        )

    _check_code(response)
    return response.json()


async def update_user_metadata(user_id: UUID, new_metadata: dict) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/user/update_metadata',
            params={'user_id': user_id},
            json=new_metadata
        )

    _check_code(response)
    return response.json()


async def new_convoy(user_id: UUID, new_convoy_name: str) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/convoy/new',
            params={
                'user_id': user_id,
                'convoy_name': new_convoy_name
            }
        )

    _check_code(response)
    return response.json()


async def get_convoy(convoy_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/convoy/get',
            params={'convoy_id': convoy_id,}
        )

    _check_code(response)
    return response.json()


async def move_cargo(convoy_id: UUID, cargo_id: UUID, dest_vehicle_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/convoy/cargo/move',
            params={
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'dest_vehicle_id': dest_vehicle_id,
            }
        )

    _check_code(response)
    return response.json()


async def find_route(convoy_id: UUID, dest_x: int, dest_y: int) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/convoy/journey/find_route',
            params={
                'convoy_id': convoy_id,
                'dest_x': dest_x,
                'dest_y': dest_y
            },
            timeout=10
        )

    _check_code(response)
    return response.json()


async def send_convoy(convoy_id: UUID, journey_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/convoy/journey/send',
            params={
                'convoy_id': convoy_id,
                'journey_id': journey_id
            }
        )

    _check_code(response)
    return response.json()


async def cancel_journey(convoy_id: UUID, journey_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/convoy/journey/cancel',
            params={
                'convoy_id': convoy_id,
                'journey_id': journey_id
            }
        )

    _check_code(response)
    return response.json()


async def get_vendor(vendor_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/vendor/get',
            params={'vendor_id': vendor_id}
        )

    _check_code(response)
    return response.json()


async def buy_vehicle(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/vehicle/buy',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            }
        )

    _check_code(response)
    return response.json()


async def sell_vehicle(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/vehicle/sell',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            }
        )

    _check_code(response)
    return response.json()


async def buy_cargo(vendor_id: UUID, convoy_id: UUID, cargo_id: UUID, quantity: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/cargo/buy',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'quantity': quantity
            }
        )

    _check_code(response)
    return response.json()


async def sell_cargo(vendor_id: UUID, convoy_id: UUID, cargo_id: UUID, quantity: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/cargo/sell',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'quantity': quantity
            }
        )

    _check_code(response)
    return response.json()


async def buy_resource(vendor_id: UUID, convoy_id: UUID, resource_type: str, quantity: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/resource/buy',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'resource_type': resource_type,
                'quantity': round(quantity, 2)  # Rounding to catch floating point errors
            }
        )

    _check_code(response)
    return response.json()


async def sell_resource(vendor_id: UUID, convoy_id: UUID, resource_type: str, quantity: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/resource/sell',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'resource_type': resource_type,
                'quantity': round(quantity, 2)  # Rounding to catch floating point errors
            }
        )

    _check_code(response)
    return response.json()


async def add_part(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID, part_cargo_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/vehicle/part/add',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id,
                'part_cargo_id': part_cargo_id
            }
        )

    _check_code(response)
    return response.json()


async def get_vehicle(vehicle_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/vehicle/get',
            params={'vehicle_id': vehicle_id}
        )

    _check_code(response)
    return response.json()


async def check_part_compatibility(vehicle_id: UUID, part_cargo_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/vehicle/part_compatibility',
            params={
                'vehicle_id': vehicle_id,
                'part_cargo_id': part_cargo_id
            }
        )

    _check_code(response)
    return response.json()


async def send_message(sender_id: UUID, recipient_id: UUID, message: str) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/dialogue/send',
            params={  # Use JSON body for POST requests
                'sender_id': sender_id,
                'recipient_id': recipient_id,
                'message': message
            }
        )
    
    _check_code(response)
    return response.json()


async def get_dialogue_by_char_ids(char_a_id: UUID, char_b_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/dialogue/get_by_char_ids',
            params={
                'char_a_id': char_a_id,
                'char_b_id': char_b_id,
            }
        )

    _check_code(response)
    return response.json()


async def get_unseen_dialogue_for_user(user_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/dialogue/get_user_unseen_messages',
            params={'user_id': user_id}
        )

    _check_code(response)
    return response.json()


async def mark_dialogue_as_seen(user_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/dialogue/mark_user_dialogues_as_seen',
            params={'user_id': user_id}
        )

    _check_code(response)
    return response.json()


async def new_warehouse(sett_id: UUID, user_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/warehouse/new',
            params={
                'sett_id': sett_id,
                'user_id': user_id
            }
        )

    _check_code(response)
    return response.json()


async def get_warehouse(warehouse_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/warehouse/get',
            params={'warehouse_id': warehouse_id}
        )

    _check_code(response)
    return response.json()


async def expand_warehouse(
        warehouse_id: UUID,
        user_id: UUID,
        cargo_capacity_upgrade: int | None = None,
        vehicle_capacity_upgrade: int | None = None
) -> list[dict]:
    params = {
        'warehouse_id': warehouse_id,
        'user_id': user_id,
        'cargo_capacity_upgrade': cargo_capacity_upgrade,
        'vehicle_capacity_upgrade': vehicle_capacity_upgrade
    }

    # Filter out `None` values
    filtered_params = {key: value for key, value in params.items() if value is not None}

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/expand',
            params=filtered_params
        )

    _check_code(response)
    return response.json()


async def retrieve_cargo_from_warehouse(
        warehouse_id: UUID,
        convoy_id: UUID,
        cargo_id: UUID,
        quantity: int
) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/cargo/retrieve',
            params={
                'warehouse_id': warehouse_id,
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'quantity': quantity
            }
        )

    _check_code(response)
    return response.json()


async def store_cargo_in_warehouse(
        warehouse_id: UUID,
        convoy_id: UUID,
        cargo_id: UUID,
        quantity: int
) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/cargo/store',
            params={
                'warehouse_id': warehouse_id,
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'quantity': quantity
            }
        )

    _check_code(response)
    return response.json()


async def retrieve_vehicle_in_warehouse(warehouse_id: UUID, convoy_id: UUID, vehicle_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/vehicle/retrieve',
            params={
                'warehouse_id': warehouse_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            }
        )

    _check_code(response)
    return response.json()


async def store_vehicle_in_warehouse(warehouse_id: UUID, convoy_id: UUID, vehicle_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/vehicle/store',
            params={
                'warehouse_id': warehouse_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            }
        )

    _check_code(response)
    return response.json()


async def spawn_convoy_from_warehouse(warehouse_id: UUID, vehicle_id: UUID, new_convoy_name: str) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/convoy/spawn',
            params={
                'warehouse_id': warehouse_id,
                'vehicle_id': vehicle_id,
                'new_convoy_name': new_convoy_name
            }
        )

    _check_code(response)
    return response.json()


async def new_banner(
        user_id: UUID,
        name: str,
        description: str,
        banner_desc: str,
        public: bool,
        discord_id: int
) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/banner/new',
            params={
                'user_id': user_id,
                'name': name,
                'description': description,
                'banner_desc': banner_desc,
                'public': public,
                'discord_id': discord_id
            }
        )

    _check_code(response)
    return response.json()


async def get_banner_by_discord_id(discord_id: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/banner/get_by_discord_id',
            params={'discord_id': discord_id}
        )

    _check_code(response)
    return response.json()


async def get_settlement_banner(sett_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/banner/settlement/get',
            params={'sett_id': sett_id}
        )

    _check_code(response)
    return response.json()


async def get_banner_internal_leaderboard(banner_id: UUID) -> dict:
    import json
    return json.loads('''\
{
  "27a785ca-76fb-492b-ab84-d00130cd5a3e": {
    "user_id": "27a785ca-76fb-492b-ab84-d00130cd5a3e",
    "username": "Office Dogboy",
    "allegiance": {
      "user_id": "27a785ca-76fb-492b-ab84-d00130cd5a3e",
      "allegiance_id": "e37c9a8a-5042-4d2f-9a9e-09ad3b856029",
      "rank": 0,
      "creation_date": "2025-01-25",
      "stats": {
        "total_value_moved": 132,
        "total_volume_moved": 12,
        "total_weight_moved": 11
      },
      "banner": {
        "banner_id": "77ca7be2-3a10-4f20-acd0-1efd89cd649a",
        "name": "New New England",
        "description": "not",
        "banner_desc": "applicable",
        "discord_id": null,
        "player_founded": false,
        "founder_id": null,
        "political_id": 49,
        "public": true,
        "creation_date": "2046-03-12",
        "sett_ids": [
          "00000000-0000-0000-0000-000000000014",
          "00000000-0000-0000-0000-000000000013",
          "00000000-0000-0000-0000-000000000015"
        ],
        "cargo_class_ids": [],
        "stats": {},
        "banner_type": "civic"
      }
    },
    "leaderboard_position": 1
  },
  "d016b585-70bf-46c1-ab16-0df8e5fa028f": {
    "user_id": "d016b585-70bf-46c1-ab16-0df8e5fa028f",
    "username": "Office alienboy",
    "allegiance": {
      "user_id": "d016b585-70bf-46c1-ab16-0df8e5fa028f",
      "allegiance_id": "e81b23ad-ee1d-49be-8e14-e83e3f72af5e",
      "rank": 0,
      "creation_date": "2025-01-25",
      "stats": {
        "total_value_moved": 132,
        "total_volume_moved": 10,
        "total_weight_moved": 11
      },
      "banner": {
        "banner_id": "77ca7be2-3a10-4f20-acd0-1efd89cd649a",
        "name": "New New England",
        "description": "not",
        "banner_desc": "applicable",
        "discord_id": null,
        "player_founded": false,
        "founder_id": null,
        "political_id": 49,
        "public": true,
        "creation_date": "2046-03-12",
        "sett_ids": [
          "00000000-0000-0000-0000-000000000014",
          "00000000-0000-0000-0000-000000000013",
          "00000000-0000-0000-0000-000000000015"
        ],
        "cargo_class_ids": [],
        "stats": {},
        "banner_type": "civic"
      }
    },
    "leaderboard_position": 2
  },
  "b19f4c36-bfae-427c-833a-b4f91957b6eb": {
    "user_id": "b19f4c36-bfae-427c-833a-b4f91957b6eb",
    "username": "Office humanboy",
    "allegiance": {
      "user_id": "b19f4c36-bfae-427c-833a-b4f91957b6eb",
      "allegiance_id": "35510d97-a3a2-466a-91ea-6cbea88750c1",
      "rank": 0,
      "creation_date": "2025-01-25",
      "stats": {
        "total_value_moved": 132,
        "total_volume_moved": 8,
        "total_weight_moved": 11
      },
      "banner": {
        "banner_id": "77ca7be2-3a10-4f20-acd0-1efd89cd649a",
        "name": "New New England",
        "description": "not",
        "banner_desc": "applicable",
        "discord_id": null,
        "player_founded": false,
        "founder_id": null,
        "political_id": 49,
        "public": true,
        "creation_date": "2046-03-12",
        "sett_ids": [
          "00000000-0000-0000-0000-000000000014",
          "00000000-0000-0000-0000-000000000013",
          "00000000-0000-0000-0000-000000000015"
        ],
        "cargo_class_ids": [],
        "stats": {},
        "banner_type": "civic"
      }
    },
    "leaderboard_position": 3
  },
  "0c5c0702-0460-425d-9a00-fb6465f49a5e": {
    "user_id": "0c5c0702-0460-425d-9a00-fb6465f49a5e",
    "username": "Office birdboy",
    "allegiance": {
      "user_id": "0c5c0702-0460-425d-9a00-fb6465f49a5e",
      "allegiance_id": "100044f1-df48-4a16-965b-ba514d3856e6",
      "rank": 0,
      "creation_date": "2025-01-25",
      "stats": {
        "total_value_moved": 132,
        "total_volume_moved": 6,
        "total_weight_moved": 11
      },
      "banner": {
        "banner_id": "77ca7be2-3a10-4f20-acd0-1efd89cd649a",
        "name": "New New England",
        "description": "not",
        "banner_desc": "applicable",
        "discord_id": null,
        "player_founded": false,
        "founder_id": null,
        "political_id": 49,
        "public": true,
        "creation_date": "2046-03-12",
        "sett_ids": [
          "00000000-0000-0000-0000-000000000014",
          "00000000-0000-0000-0000-000000000013",
          "00000000-0000-0000-0000-000000000015"
        ],
        "cargo_class_ids": [],
        "stats": {},
        "banner_type": "civic"
      }
    },
    "leaderboard_position": 4
  },
  "d9b94f20-9604-404b-9632-98571d8ac695": {
    "user_id": "d9b94f20-9604-404b-9632-98571d8ac695",
    "username": "Office squirrelboy",
    "allegiance": {
      "user_id": "d9b94f20-9604-404b-9632-98571d8ac695",
      "allegiance_id": "4c9ec4c8-18b4-42fe-9d88-7f71c4488717",
      "rank": 0,
      "creation_date": "2025-01-25",
      "stats": {
        "total_value_moved": 132,
        "total_volume_moved": 4,
        "total_weight_moved": 11
      },
      "banner": {
        "banner_id": "77ca7be2-3a10-4f20-acd0-1efd89cd649a",
        "name": "New New England",
        "description": "not",
        "banner_desc": "applicable",
        "discord_id": null,
        "player_founded": false,
        "founder_id": null,
        "political_id": 49,
        "public": true,
        "creation_date": "2046-03-12",
        "sett_ids": [
          "00000000-0000-0000-0000-000000000014",
          "00000000-0000-0000-0000-000000000013",
          "00000000-0000-0000-0000-000000000015"
        ],
        "cargo_class_ids": [],
        "stats": {},
        "banner_type": "civic"
      }
    },
    "leaderboard_position": 5
  },
  "ae1ea4fa-da00-4fca-8bb1-084443fadfcb": {
    "user_id": "ae1ea4fa-da00-4fca-8bb1-084443fadfcb",
    "username": "Office Catboy",
    "allegiance": {
      "user_id": "ae1ea4fa-da00-4fca-8bb1-084443fadfcb",
      "allegiance_id": "9cd8cf76-ae47-4943-9ae9-c710901bb2c5",
      "rank": 0,
      "creation_date": "2025-01-25",
      "stats": {
        "total_value_moved": 132,
        "total_volume_moved": 3,
        "total_weight_moved": 11
      },
      "banner": {
        "banner_id": "77ca7be2-3a10-4f20-acd0-1efd89cd649a",
        "name": "New New England",
        "description": "not",
        "banner_desc": "applicable",
        "discord_id": null,
        "player_founded": false,
        "founder_id": null,
        "political_id": 49,
        "public": true,
        "creation_date": "2046-03-12",
        "sett_ids": [
          "00000000-0000-0000-0000-000000000014",
          "00000000-0000-0000-0000-000000000013",
          "00000000-0000-0000-0000-000000000015"
        ],
        "cargo_class_ids": [],
        "stats": {},
        "banner_type": "civic"
      }
    },
    "leaderboard_position": 6
  },
  "1655d93d-1576-4511-af80-6fd6acafbabc": {
    "user_id": "1655d93d-1576-4511-af80-6fd6acafbabc",
    "username": "Office lizardboy",
    "allegiance": {
      "user_id": "1655d93d-1576-4511-af80-6fd6acafbabc",
      "allegiance_id": "097db40a-e0b7-40e4-a3a2-0b1fde376868",
      "rank": 0,
      "creation_date": "2025-01-25",
      "stats": {
        "total_value_moved": 132,
        "total_volume_moved": 2,
        "total_weight_moved": 11
      },
      "banner": {
        "banner_id": "77ca7be2-3a10-4f20-acd0-1efd89cd649a",
        "name": "New New England",
        "description": "not",
        "banner_desc": "applicable",
        "discord_id": null,
        "player_founded": false,
        "founder_id": null,
        "political_id": 49,
        "public": true,
        "creation_date": "2046-03-12",
        "sett_ids": [
          "00000000-0000-0000-0000-000000000014",
          "00000000-0000-0000-0000-000000000013",
          "00000000-0000-0000-0000-000000000015"
        ],
        "cargo_class_ids": [],
        "stats": {},
        "banner_type": "civic"
      }
    },
    "leaderboard_position": 7
  }
}
    ''')

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/banner/leaderboard/internal',
            params={'banner_id': banner_id}
        )

    _check_code(response)
    return response.json()


async def get_banner_global_leaderboard(banner_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/banner/leaderboard/global',
            params={'banner_id': banner_id}
        )

    _check_code(response)
    return response.json()


async def form_allegiance(user_id: UUID, banner_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/banner/allegiance/form',
            params={
                'user_id': user_id,
                'banner_id': banner_id
            }
        )

    _check_code(response)
    return response.json()
