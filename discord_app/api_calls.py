# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                        os
from uuid              import UUID
from datetime          import datetime, timezone, timedelta, UTC

import                        httpx
from jose              import jwt

from df_lib.map_struct import serialize_map, deserialize_map

DF_API_HOST = os.environ['DF_API_HOST']
DF_MAP_RENDERER = os.environ['DF_MAP_RENDERER']
API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
API_INTERNAL_SERVER_ERROR = 500

SKELETON_KEY = os.environ['DF_SKELETON_KEY']


def create_session(user_id) -> str:
    exp = datetime.now(UTC) + timedelta(minutes=10)
    return jwt.encode(
        claims={
            'sub': str(user_id),
            'exp': exp,
            'provider': 'oori'
        },
        key=SKELETON_KEY,
        algorithm='HS256',
    )


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
        y_max: int | None = None,
        user_id: UUID | None = None
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

    headers = {'Authorization': f'Bearer {create_session('DF_DISCORD_APP')}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/map/get',
            params=params,
            headers=headers,
            timeout=30
        )

    _check_code(response)
    return deserialize_map(response.content)


async def get_tile(x: int, y: int, user_id: UUID | None = None) -> dict:
    headers = {'Authorization': f'Bearer {create_session('DF_DISCORD_APP')}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/map/tile/get',
            params={
                'x': x,
                'y': y
            },
            headers=headers
        )

    _check_code(response)
    return response.json()

async def resource_weights() -> dict:
    """ Fetch the weight per unit of each resource type from the API. """
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/cargo/resource/weights'
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
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/user/get',
            params={},
            headers=headers,
        )

    _check_code(response)
    return response.json()


async def get_user_by_discord(discord_id: int) -> dict:
    headers = {'Authorization': f'Bearer {create_session('DF_DISCORD_APP')}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/user/get_by_discord_id',
            params={
                'discord_id': discord_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def get_discord_users() -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session('DF_DISCORD_APP')}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/user/discord_users',
            headers=headers
        )

    _check_code(response)
    return response.json()


async def update_user_metadata(user_id: UUID, new_metadata: dict) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/user/update_metadata',
            params={},
            headers=headers,
            json=new_metadata
        )

    _check_code(response)
    return response.json()


async def new_convoy(user_id: UUID, new_convoy_name: str) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/convoy/new',
            params={
                'convoy_name': new_convoy_name
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def redeem_referral(user_id: UUID, referral_code: str) -> dict:  # XXX i think this is depricated
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/user/redeem_referral',
            params={
                'referral_code': referral_code
            },
            headers=headers
        )
        return response.json()


async def get_convoy(convoy_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/convoy/get',
            params={
                'convoy_id': convoy_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def move_cargo(convoy_id: UUID, cargo_id: UUID, dest_vehicle_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/convoy/cargo/move',
            params={
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'dest_vehicle_id': dest_vehicle_id,
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def find_route(convoy_id: UUID, dest_x: int, dest_y: int, user_id: UUID) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/convoy/journey/find_route',
            params={
                'convoy_id': convoy_id,
                'dest_x': dest_x,
                'dest_y': dest_y
            },
            headers=headers,
            timeout=20
        )

    _check_code(response)
    return response.json()


async def send_convoy(convoy_id: UUID, journey_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/convoy/journey/send',
            params={
                'convoy_id': convoy_id,
                'journey_id': journey_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def cancel_journey(convoy_id: UUID, journey_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/convoy/journey/cancel',
            params={
                'convoy_id': convoy_id,
                'journey_id': journey_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def get_vendor(vendor_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/vendor/get',
            params={
                'vendor_id': vendor_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def buy_vehicle(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/vehicle/buy',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def sell_vehicle(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/vehicle/sell',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def buy_cargo(vendor_id: UUID, convoy_id: UUID, cargo_id: UUID, quantity: int, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/cargo/buy',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'quantity': quantity
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def sell_cargo(vendor_id: UUID, convoy_id: UUID, cargo_id: UUID, quantity: int, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/cargo/sell',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'quantity': quantity
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def buy_resource(vendor_id: UUID, convoy_id: UUID, resource_type: str, quantity: int, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/resource/buy',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'resource_type': resource_type,
                'quantity': round(quantity, 3)  # Rounding to catch floating point errors
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def sell_resource(vendor_id: UUID, convoy_id: UUID, resource_type: str, quantity: int, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/resource/sell',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'resource_type': resource_type,
                'quantity': round(quantity, 3)  # Rounding to catch floating point errors
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def add_part(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID, part_cargo_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/vehicle/part/add',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id,
                'part_cargo_id': part_cargo_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def remove_part(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID, part_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/vehicle/part/remove',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id,
                'part_id': part_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def vendor_scrap_vehicle(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/vendor/vehicle/scrap',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            },
            headers=headers
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


async def check_part_compatibility(vehicle_id: UUID, part_cargo_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/vehicle/part/check_compatibility',
            params={
                'vehicle_id': vehicle_id,
                'part_cargo_id': part_cargo_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def check_scrap(vehicle_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/vehicle/check_scrap',
            params={
                'vehicle_id': vehicle_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def send_message(sender_id: UUID, recipient_id: UUID, message: str, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/dialogue/send',
            params={  # Use JSON body for POST requests
                'sender_id': sender_id,
                'recipient_id': recipient_id,
                'message': message
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def get_dialogue_by_char_ids(char_a_id: UUID, char_b_id: UUID, user_id: UUID) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/dialogue/get_by_char_ids',
            params={
                'char_a_id': char_a_id,
                'char_b_id': char_b_id,
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def get_unseen_dialogue_for_user(user_id: UUID) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/dialogue/get_user_unseen_messages',
            params={},
            headers=headers
        )

    _check_code(response)
    return response.json()


async def mark_dialogue_as_seen(user_id: UUID) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/dialogue/mark_user_dialogues_as_seen',
            params={},
            headers=headers
        )

    _check_code(response)
    return response.json()


async def new_warehouse(sett_id: UUID, user_id: UUID) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/warehouse/new',
            params={
                'sett_id': sett_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def get_warehouse(warehouse_id: UUID, user_id: UUID) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/warehouse/get',
            params={
                'warehouse_id': warehouse_id
            },
            headers=headers
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
        'cargo_capacity_upgrade': cargo_capacity_upgrade,
        'vehicle_capacity_upgrade': vehicle_capacity_upgrade
    }

    # Filter out `None` values
    filtered_params = {key: value for key, value in params.items() if value is not None}

    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/expand',
            params=filtered_params,
            headers=headers
        )

    _check_code(response)
    return response.json()


async def retrieve_cargo_from_warehouse(
        warehouse_id: UUID,
        convoy_id: UUID,
        cargo_id: UUID,
        quantity: int,
        user_id: UUID
) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/cargo/retrieve',
            params={
                'warehouse_id': warehouse_id,
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'quantity': quantity
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def store_cargo_in_warehouse(
        warehouse_id: UUID,
        convoy_id: UUID,
        cargo_id: UUID,
        quantity: int,
        user_id: UUID
) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/cargo/store',
            params={
                'warehouse_id': warehouse_id,
                'convoy_id': convoy_id,
                'cargo_id': cargo_id,
                'quantity': quantity
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def retrieve_vehicle_in_warehouse(
        warehouse_id: UUID,
        convoy_id: UUID,
        vehicle_id: UUID,
        user_id: UUID
) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/vehicle/retrieve',
            params={
                'warehouse_id': warehouse_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def store_vehicle_in_warehouse(
        warehouse_id: UUID,
        convoy_id: UUID,
        vehicle_id: UUID,
        user_id: UUID
) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/vehicle/store',
            params={
                'warehouse_id': warehouse_id,
                'convoy_id': convoy_id,
                'vehicle_id': vehicle_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def spawn_convoy_from_warehouse(
        warehouse_id: UUID,
        vehicle_id: UUID,
        new_convoy_name: str,
        user_id: UUID
) -> list[dict]:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/warehouse/convoy/spawn',
            params={
                'warehouse_id': warehouse_id,
                'vehicle_id': vehicle_id,
                'new_convoy_name': new_convoy_name
            },
            headers=headers
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
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/banner/new',
            params={
                'name': name,
                'description': description,
                'banner_desc': banner_desc,
                'public': public,
                'discord_id': discord_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def get_banner_by_discord_id(discord_id: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/banner/get_by_discord_id',
            params={
                'discord_id': discord_id
            }
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


async def get_banner_internal_leaderboard(banner_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/banner/leaderboard/internal',
            params={
                'banner_id': banner_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def get_banner_global_leaderboard(banner_id: UUID, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            url=f'{DF_API_HOST}/banner/leaderboard/global',
            params={
                'banner_id': banner_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def form_allegiance(user_id: UUID, banner_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url=f'{DF_API_HOST}/banner/allegiance/form',
            params={
                'banner_id': banner_id
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def get_global_civic_leaderboard() -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(url=f'{DF_API_HOST}/banner/leaderboard/civic/all')

    _check_code(response)
    return response.json()


async def get_global_syndicate_leaderboard() -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(url=f'{DF_API_HOST}/banner/leaderboard/syndicate/all')

    _check_code(response)
    return response.json()


async def change_username(user_id: UUID, new_name: str) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/user/update_username',
            params={
                'new_name': new_name
            },
            headers=headers
        )

    _check_code(response)
    return response.json()


async def change_convoy_name(convoy_id: UUID, new_name: str, user_id: UUID) -> dict:
    headers = {'Authorization': f'Bearer {create_session(user_id)}'}
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            url=f'{DF_API_HOST}/convoy/update_convoy_name',
            params={
                'convoy_id': convoy_id,
                'new_name': new_name
            },
            headers=headers
        )

    _check_code(response)
    return response.json()
