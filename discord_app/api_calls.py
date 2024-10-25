# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import           os
from uuid import UUID

import           httpx

DF_API_HOST = os.environ.get('DF_API_HOST')
API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
API_INTERNAL_SERVER_ERROR = 500


def _check_code(response: httpx.Response):
    if response.status_code == API_INTERNAL_SERVER_ERROR:
        raise RuntimeError('API Internal Server Error')
    elif response.status_code != API_SUCCESS_CODE:
        msg = response.json()['detail']
        raise RuntimeError(msg)


async def get_map(x_min: int = None, x_max: int = None, y_min: int = None, y_max: int = None) -> dict:
    params = {}

    # Add parameters only if they are not None
    if x_min is not None:
        params['x_min'] = x_min
    if x_max is not None:
        params['x_max'] = x_max
    if y_min is not None:
        params['y_min'] = y_min
    if y_max is not None:
        params['y_max'] = y_max

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            f'{DF_API_HOST}/map/get',
            params=params,
            timeout=10
        )

    _check_code(response)
    return response.json()


async def get_tile(x: int, y: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            f'{DF_API_HOST}/map/tile/get',
            params={
                'x': x,
                'y': y
            }
        )

    _check_code(response)
    return response.json()


async def get_user_by_discord(discord_id: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            f'{DF_API_HOST}/user/get_by_discord_id',
            params={
                'discord_id': discord_id
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
            params={
                'convoy_id': convoy_id,
            }
        )

    _check_code(response)
    return response.json()


async def move_cargo(convoy_id: UUID, cargo_id: UUID, dest_vehicle_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            f'{DF_API_HOST}/convoy/cargo/move',
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
            f'{DF_API_HOST}/convoy/find_route',
            params={
                'convoy_id': convoy_id,
                'dest_x': dest_x,
                'dest_y': dest_y
            }
        )

    _check_code(response)
    return response.json()


async def send_convoy(convoy_id: UUID, journey_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            f'{DF_API_HOST}/convoy/send',
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
            f'{DF_API_HOST}/vendor/get',
            params={'vendor_id': vendor_id}
        )

    _check_code(response)
    return response.json()


async def buy_vehicle(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            f'{DF_API_HOST}/vendor/vehicle/buy',
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
            f'{DF_API_HOST}/vendor/vehicle/sell',
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
            f'{DF_API_HOST}/vendor/cargo/buy',
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
            f'{DF_API_HOST}/vendor/cargo/sell',
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
            f'{DF_API_HOST}/vendor/resource/buy',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'resource_type': resource_type,
                'quantity': quantity
            }
        )

    _check_code(response)
    return response.json()


async def sell_resource(vendor_id: UUID, convoy_id: UUID, resource_type: str, quantity: int) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            f'{DF_API_HOST}/vendor/resource/sell',
            params={
                'vendor_id': vendor_id,
                'convoy_id': convoy_id,
                'resource_type': resource_type,
                'quantity': quantity
            }
        )

    _check_code(response)
    return response.json()


async def add_part(vendor_id: UUID, convoy_id: UUID, vehicle_id: UUID, part_cargo_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            f'{DF_API_HOST}/vendor/vehicle/part/add',
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
            f'{DF_API_HOST}/vehicle/get',
            params={'vehicle_id': vehicle_id}
        )

    _check_code(response)
    return response.json()


async def check_part_compatibility(vehicle_id: UUID, part_cargo_id: UUID) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            f'{DF_API_HOST}/vehicle/part_compatibility',
            params={
                'vehicle_id': vehicle_id,
                'part_cargo_id': part_cargo_id
            }
        )

    _check_code(response)
    return response.json()


async def get_dialogue_by_char_ids(char_a_id: UUID, char_b_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(
            f'{DF_API_HOST}/dialogue/get_by_char_ids',
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
            f'{DF_API_HOST}/dialogue/get_user_unseen_messages',
            params={'user_id': user_id}
        )

    _check_code(response)
    return response.json()


async def mark_dialogue_as_seen(user_id: UUID) -> list[dict]:
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.patch(
            f'{DF_API_HOST}/dialogue/mark_user_dialogues_as_seen',
            params={'user_id': user_id}
        )

    _check_code(response)
    return response.json()
