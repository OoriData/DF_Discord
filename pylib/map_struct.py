# SPDX-FileCopyrightText: 2023-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
# dflib.map_struct
import struct
from typing import Any
from io import BytesIO

from dflib.datastruct import (TERRAIN_FORMAT, CARGO_HEADER_FORMAT, VEHICLE_HEADER_FORMAT, VENDOR_HEADER_FORMAT,
                              SETTLEMENT_HEADER_FORMAT)

#
# client-side serialization
#

ZERO_UUID = '00000000-0000-0000-0000-0000000000000000'

def pack_string(s: str, length: int) -> bytes:
    '''Pack a string into fixed-length bytes with UTF-8 encoding'''
    encoded = s.encode('utf-8')
    return encoded[:length].ljust(length, b'\0')

def serialize_cargo(cargo: dict[str, Any]) -> bytes:
    '''Serialize a single cargo item'''
    # from rich import print
    # print(cargo)
    # print([
    #     pack_string(cargo['cargo_id'], 36),
    #     pack_string(cargo['name'], 100),
    #     cargo['quantity'],
    #     cargo['volume'],
    #     cargo['weight'],
    #     cargo.get('capacity', 0.0) or 0.0,
    #     cargo.get('fuel', 0.0) or 0.0,
    #     cargo.get('water', 0.0) or 0.0,
    #     int(cargo.get('food', 0) or 0),
    #     int(cargo.get('part', 0) or 0),
    #     int(cargo.get('distributor', 0) or 0),
    #     cargo.get('base_price', 0) or 0,
    #     cargo.get('delivery_reward', 0) or 0
    # ])
    return struct.pack(
        CARGO_HEADER_FORMAT,
        pack_string(cargo['cargo_id'], 36),
        pack_string(cargo['name'], 100),
        cargo['quantity'],
        cargo['volume'],
        cargo['weight'],
        cargo.get('capacity', 0.0) or 0.0,
        cargo.get('fuel', 0.0) or 0.0,
        cargo.get('water', 0.0) or 0.0,
        int(cargo.get('food', 0) or 0),
        int(cargo.get('part', 0) or 0),
        int(cargo.get('distributor', 0) or 0),
        cargo.get('base_price', 0) or 0,
        cargo.get('delivery_reward', 0) or 0
    )

def serialize_vehicle(vehicle: dict[str, Any]) -> bytes:
    '''Serialize a single vehicle'''
    # from rich import print
    # print(vehicle)
    # print([
    #     pack_string(vehicle['vehicle_id'], 36),
    #     pack_string(vehicle['name'], 100),
    #     vehicle['wear'],
    #     vehicle['base_fuel_efficiency'],
    #     vehicle['base_top_speed'],
    #     vehicle['base_offroad_capability'],
    #     vehicle['base_cargo_capacity'],
    #     vehicle['base_weight_capacity'],
    #     vehicle.get('base_towing_capacity', -1) or -1,
    #     vehicle['ap'],
    #     vehicle['base_max_ap'],
    #     vehicle['base_value'],
    #     vehicle.get('convoy_id', ZERO_UUID) or ZERO_UUID,
    #     vehicle.get('warehouse_id', ZERO_UUID) or ZERO_UUID
    # ])
    # "!36s100sfHHHIIiHHI36s36s"
    return struct.pack(
        VEHICLE_HEADER_FORMAT,
        pack_string(vehicle['vehicle_id'], 36),
        pack_string(vehicle['name'], 100),
        vehicle['wear'],

        vehicle['base_fuel_efficiency'],
        vehicle['base_top_speed'],
        vehicle['base_offroad_capability'],

        vehicle['base_cargo_capacity'],
        vehicle['base_weight_capacity'],
        vehicle.get('base_towing_capacity', -1) or -1,

        vehicle['ap'],
        vehicle['base_max_ap'],

        vehicle['base_value'],

        pack_string(vehicle.get('vendor_id', ZERO_UUID) or ZERO_UUID, 36),
        pack_string(vehicle.get('warehouse_id', ZERO_UUID) or ZERO_UUID, 36)
    )


def serialize_vendor(vendor: dict[str, Any]) -> bytes:
    '''Serialize a single vendor'''
    # from rich import print
    # print(vendor)
    # print()
    # print([pack_string(vendor['vendor_id'], 36),
    #     pack_string(vendor['name'], 100),
    #     vendor['money'],
    #     vendor.get('fuel', 0) or 0,
    #     vendor.get('water', 0) or 0,
    #     vendor.get('food', 0) or 0,
    #     len(vendor['_cargo_inventory']),
    #     len(vendor['_vehicle_inventory'])])
    header = struct.pack(
        VENDOR_HEADER_FORMAT,
        pack_string(vendor['vendor_id'], 36),
        pack_string(vendor['name'], 100),
        vendor['money'],
        vendor.get('fuel', 0) or 0,
        vendor.get('water', 0) or 0,
        vendor.get('food', 0) or 0,
        len(vendor['_cargo_inventory']),
        len(vendor['_vehicle_inventory'])
    )
    
    cargo_data = b''.join(serialize_cargo(c) for c in vendor['_cargo_inventory'])
    vehicle_data = b''.join(serialize_vehicle(v) for v in vendor['_vehicle_inventory'])
    
    return header + cargo_data + vehicle_data

def serialize_settlement(settlement: dict[str, Any]) -> bytes:
    '''Serialize a single settlement'''
    header = struct.pack(
        SETTLEMENT_HEADER_FORMAT,
        pack_string(settlement['sett_id'], 36),  # 0-filled UUID is a valid case (happened to be Chicago)
        pack_string(settlement['name'], 100),
        {'dome': 1, 'outpost': 2}.get(settlement['sett_type'], 0),
        len(settlement.get('imports', []) or []),
        len(settlement.get('exports', []) or []),
        len(settlement['vendors'])
    )
    
    vendors_data = b''.join(serialize_vendor(v) for v in settlement['vendors'])
    return header + vendors_data

def serialize_tile(tile: dict[str, Any]) -> bytes:
    '''Serialize a single tile'''
    header = struct.pack(
        TERRAIN_FORMAT,
        tile['terrain_difficulty'],
        tile['region'],
        tile['weather'],
        tile['special'],
        len(tile['settlements'])
    )
    
    settlements_data = b''.join(serialize_settlement(s) for s in tile['settlements'])
    return header + settlements_data

def serialize_map(data: dict[str, Any]) -> bytes:
    '''Serialize the entire map structure'''
    buffer = BytesIO()
    
    # Write map dimensions
    tiles = data['tiles']
    buffer.write(struct.pack("!HH", len(tiles), len(tiles[0])))
    
    # Write tiles
    for row in tiles:
        for tile in row:
            buffer.write(serialize_tile(tile))
    
    # Write highlight/lowlight locations
    for location_list in [(data.get('highlight_locations', []) or []), (data.get('lowlight_locations', []) or [])]:
        buffer.write(struct.pack("!H", len(location_list)))
        for x, y in location_list:
            buffer.write(struct.pack("!HH", x, y))
    
    return buffer.getvalue()


#
# Server-side deserialization
#

def unpack_string(data: bytes) -> str:
    '''Unpack a null-terminated string from bytes'''
    null_pos = data.find(b'\0')
    if null_pos != -1:
        data = data[:null_pos]
    return data.decode('utf-8')

def deserialize_cargo(buffer: BytesIO) -> dict[str, Any]:
    '''Deserialize a single cargo item'''
    data = struct.unpack(CARGO_HEADER_FORMAT, buffer.read(struct.calcsize(CARGO_HEADER_FORMAT)))
    
    return {
        'cargo_id': unpack_string(data[0]),
        'name': unpack_string(data[1]),
        'quantity': data[2],
        'volume': data[3],
        'weight': data[4],
        'capacity': data[5],
        'fuel': data[6],
        'water': data[7],
        'food': bool(data[8]),
        'part': bool(data[9]),
        'distributor': bool(data[10]),
        'base_price': data[11],
        'delivery_reward': data[12]
    }

def deserialize_vehicle(buffer: BytesIO) -> dict[str, Any]:
    '''Deserialize a single vehicle'''
    data = struct.unpack(VEHICLE_HEADER_FORMAT, buffer.read(struct.calcsize(VEHICLE_HEADER_FORMAT)))
    
    return {
        'vehicle_id': unpack_string(data[0]),
        'name': unpack_string(data[1]),
        'wear': data[2],
        'base_fuel_efficiency': data[3],
        'base_top_speed': data[4],
        'base_offroad_capability': data[5],
        'base_cargo_capacity': data[6],
        'base_weight_capacity': data[7],
        'base_towing_capacity': data[8],
        'ap': data[9],
        'base_max_ap': data[10],
        'base_value': data[11]
    }

def deserialize_vendor(buffer: BytesIO) -> dict[str, Any]:
    '''Deserialize a single vendor'''
    header = struct.unpack(VENDOR_HEADER_FORMAT, buffer.read(struct.calcsize(VENDOR_HEADER_FORMAT)))
    
    cargo_count = header[6]
    vehicle_count = header[7]
    
    cargo_inventory = [deserialize_cargo(buffer) for _ in range(cargo_count)]
    vehicle_inventory = [deserialize_vehicle(buffer) for _ in range(vehicle_count)]
    
    return {
        'vendor_id': unpack_string(header[0]),
        'name': unpack_string(header[1]),
        'money': header[2],
        'fuel': header[3],
        'water': header[4],
        'food': header[5],
        '_cargo_inventory': cargo_inventory,
        '_vehicle_inventory': vehicle_inventory
    }

def deserialize_settlement(buffer: BytesIO) -> dict[str, Any]:
    '''Deserialize a single settlement'''
    header = struct.unpack(SETTLEMENT_HEADER_FORMAT, buffer.read(struct.calcsize(SETTLEMENT_HEADER_FORMAT)))
    
    sett_types = {1: 'dome', 2: 'outpost'}
    vendor_count = header[5]
    
    vendors = [deserialize_vendor(buffer) for _ in range(vendor_count)]
    
    return {
        'sett_id': unpack_string(header[0]),
        'name': unpack_string(header[1]),
        'sett_type': sett_types.get(header[2], 'unknown'),
        'vendors': vendors
    }

def deserialize_map(binary_data: bytes) -> dict[str, Any]:
    '''Deserialize the entire map structure'''
    buffer = BytesIO(binary_data)
    
    # Read map dimensions
    height, width = struct.unpack("!HH", buffer.read(4))
    
    # Read tiles
    tiles = []
    for _ in range(height):
        row = []
        for _ in range(width):
            header = struct.unpack(TERRAIN_FORMAT, buffer.read(struct.calcsize(TERRAIN_FORMAT)))
            settlement_count = header[4]
            
            settlements = [deserialize_settlement(buffer) for _ in range(settlement_count)]
            
            row.append({
                'terrain_difficulty': header[0],
                'region': header[1],
                'weather': header[2],
                'special': header[3],
                'settlements': settlements
            })
        tiles.append(row)
    
    # Read highlight/lowlight locations
    highlight_locations = []
    lowlight_locations = []
    
    for location_list in [highlight_locations, lowlight_locations]:
        count = struct.unpack("!H", buffer.read(2))[0]
        for _ in range(count):
            x, y = struct.unpack("!HH", buffer.read(4))
            location_list.append([x, y])
    
    return {
        'tiles': tiles,
        'highlight_locations': highlight_locations,
        'lowlight_locations': lowlight_locations
    }
