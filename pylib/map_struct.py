# SPDX-FileCopyrightText: 2023-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
# dflib.map_struct
import struct
import warnings
from typing import Any
from io import BytesIO

from dflib.datastruct import (TERRAIN_FORMAT, CARGO_HEADER_FORMAT, VEHICLE_HEADER_FORMAT, VENDOR_HEADER_FORMAT,
                              SETTLEMENT_HEADER_FORMAT)

#
# client-side serialization
#

ZERO_UUID = '00000000-0000-0000-0000-000000000000'

# Helper function to handle UUID fields
def process_uuid(uuid_val: str | None) -> str:
    if uuid_val is None or uuid_val == '':
        return ZERO_UUID
    assert len(uuid_val) == 36, f"Invalid UUID length: {uuid_val}"
    return uuid_val

def pack_string(s: str, length: int) -> bytes:
    '''Pack a string into fixed-length bytes with UTF-8 encoding'''
    if not s:
        return b'\0' * length

    # XXX: A bit flaky to use the length as the UUID check. Ponder this
    # Special handling for UUIDs to ensure they're properly formatted
    if length == 36:  # UUID length
        if s == ZERO_UUID or not s:
            return ZERO_UUID.encode('utf-8')
        # Ensure UUID is properly formatted
        if len(s) != 36:
            warnings.warn(f'Invalid UUID length ({len(s)}): {s}', stacklevel=2)
            return ZERO_UUID.encode('utf-8')

    encoded = s.encode('utf-8')
    if len(encoded) > length:
        warnings.warn(f'String too long ({len(encoded)} > {length}): {s}', stacklevel=2)
        encoded = encoded[:length]
    return encoded.ljust(length, b'\0')

def serialize_cargo(cargo: dict[str, Any]) -> bytes:
    '''Serialize a single cargo item'''
    # Validate UUIDs
    for uuid_field in ['cargo_id', 'distributor', 'vehicle_id', 'warehouse_id', 'vendor_id']:
        if cargo.get(uuid_field) and cargo[uuid_field] != ZERO_UUID:
            assert len(cargo[uuid_field]) == 36, f"Invalid UUID length for {uuid_field}: {cargo[uuid_field]}"
    assert len(cargo.get('name', '')) <= 64
    assert len(cargo.get('base_desc', '') or '') <= 512
    return struct.pack(
        CARGO_HEADER_FORMAT,
        pack_string(cargo['cargo_id'], 36),
        pack_string(cargo['name'], 64),
        pack_string(cargo.get('base_desc', ''), 512),
        int(cargo.get('quantity', 0) or 0),
        int(cargo.get('volume', 0) or 0),
        int(cargo.get('weight', 0) or 0),
        float(cargo.get('capacity', 0.0) or 0.0),
        float(cargo.get('fuel', 0.0) or 0.0),
        float(cargo.get('water', 0.0) or 0.0),
        float(cargo.get('food', 0.0) or 0.0),
        int(cargo.get('base_price', 0) or 0),
        int(cargo.get('delivery_reward', 0) or 0),
        pack_string(process_uuid(cargo.get('distributor')), 36),
        pack_string(process_uuid(cargo.get('vehicle_id')), 36),
        pack_string(process_uuid(cargo.get('warehouse_id')), 36),
        pack_string(process_uuid(cargo.get('vendor_id')), 36)
        # int(cargo.get('part', 0) or 0),  # part for now is either 0 or 1 of them—0 stored as null at present; in theory could be multiple in future
    )

def serialize_vehicle(vehicle: dict[str, Any]) -> bytes:
    '''Serialize a single vehicle'''
    assert len(vehicle.get('name', '')) <= 64
    assert len(vehicle.get('base_desc', '')) <= 512
    assert vehicle.get('convoy_id') is None
# wear(f), base fuel eff & top speed & offroad capab (HHH), base cargo & weight capac (II), towing capacity(i), ap(H), base max ap(H), value(I)

    return struct.pack(
        VEHICLE_HEADER_FORMAT,
        pack_string(vehicle['vehicle_id'], 36),
        pack_string(vehicle['name'], 64),
        pack_string(vehicle.get('base_desc', ''), 512),
        float(vehicle.get('wear', 0.0) or 0.0),
        int(vehicle.get('base_fuel_efficiency', 0) or 0),
        int(vehicle.get('base_top_speed', 0) or 0),
        int(vehicle.get('base_offroad_capability', 0) or 0),
        int(vehicle.get('base_cargo_capacity', 0) or 0),
        int(vehicle.get('base_weight_capacity', 0) or 0),
        int(vehicle.get('base_towing_capacity', 0) or 0),
        int(vehicle.get('ap', 0) or 0),
        int(vehicle.get('base_max_ap', 0) or 0),
        int(vehicle.get('base_value', 0) or 0),
        pack_string(process_uuid(vehicle.get('vendor_id')), 36),
        pack_string(process_uuid(vehicle.get('warehouse_id')), 36)
    )

def serialize_vendor(vendor: dict[str, Any]) -> bytes:
    '''Serialize a single vendor'''
    # TODO: Vendor to handle supply_request
    # Axiom: Cargo item should have exactly one UUID of vehicle_id, warehouse_id, vendor_id; others are explicitly null
    # assert len(sum(vendor['vehicle_id']))
    assert len(vendor.get('name', '')) <= 64
    assert len(vendor.get('base_desc', '') or '') <= 512

    header = struct.pack(
        VENDOR_HEADER_FORMAT,
        pack_string(vendor['vendor_id'], 36),
        pack_string(vendor['name'], 64),
        pack_string(vendor.get('base_desc', ''), 512),
        int(vendor['money']),
        int(vendor.get('fuel') or 0),
        int(vendor.get('fuel_price', -1) or 0),
        int(vendor.get('water') or 0),
        int(vendor.get('water_price', -1) or 0),
        int(vendor.get('food') or 0),
        int(vendor.get('food_price', -1) or 0),
        int(vendor.get('repair_price', -1) or 0),
        len(vendor['_cargo_inventory']),
        len(vendor['_vehicle_inventory'])
    )

    cargo_data = b''.join(serialize_cargo(c) for c in vendor['_cargo_inventory'])
    vehicle_data = b''.join(serialize_vehicle(v) for v in vendor['_vehicle_inventory'])

    return header + cargo_data + vehicle_data

def serialize_settlement(settlement: dict[str, Any]) -> bytes:
    '''Serialize a single settlement'''
    assert len(settlement.get('name', '')) <= 64
    assert len(settlement.get('base_desc', '') or '') <= 1024, settlement.get('base_desc')
    header = struct.pack(
        SETTLEMENT_HEADER_FORMAT,
        pack_string(settlement['sett_id'], 36),  # 0-filled UUID is a valid case (happened to be Chicago)
        pack_string(settlement['name'], 64),
        pack_string(settlement.get('base_desc') or '', 1024),
        {'dome': 1, 'city': 2, 'town': 3, 'city-state': 4, 'military_base': 5}.get(settlement['sett_type'], 0),
        len(settlement.get('imports', []) or []),
        len(settlement.get('exports', []) or []),
        len(settlement['vendors'])
    )

    vendors_data = b''.join(serialize_vendor(v) for v in settlement['vendors'])
    return header + vendors_data

def serialize_tile(tile: dict[str, Any], x, y) -> bytes:
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

    # Write tiles. Note that tiles have x, y coordinates; redundant because they come in order
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            buffer.write(serialize_tile(tile, x, y))
    
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
    # First handle empty or None cases
    if not data:
        return ''

    # Find the first null terminator
    null_pos = data.find(b'\0')
    if null_pos != -1:
        data = data[:null_pos]

    # If the data is empty after removing nulls, return empty string
    if not data:
        return ''

    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        # If it's a UUID-length string that fails to decode, return zero UUID
        if len(data) == 36:
            return ZERO_UUID
        # For any other string, return empty rather than crashing
        warnings.warn(f'Failed to decode bytes: {data}, returning empty string', stacklevel=2)
        return ''

def deserialize_cargo(buffer: BytesIO) -> dict[str, Any]:
    '''Deserialize a single cargo item'''
    data = struct.unpack(CARGO_HEADER_FORMAT, buffer.read(struct.calcsize(CARGO_HEADER_FORMAT)))

    cargo = {
        'cargo_id': unpack_string(data[0]),
        'name': unpack_string(data[1]),
        'base_desc': unpack_string(data[2]),
        'quantity': data[3],
        'volume': data[4],
        'weight': data[5],
        'capacity': data[6],
        'fuel': data[7],
        'water': data[8],
        'food': data[9],
        'base_price': data[10],
        'delivery_reward': data[11],
    }

    # Handle UUIDs separately to ensure proper null handling
    distributor = unpack_string(data[12])
    cargo['distributor'] = None if distributor == ZERO_UUID else distributor

    vehicle_id = unpack_string(data[13])
    cargo['vehicle_id'] = None if vehicle_id == ZERO_UUID else vehicle_id

    warehouse_id = unpack_string(data[14])
    cargo['warehouse_id'] = None if warehouse_id == ZERO_UUID else warehouse_id

    vendor_id = unpack_string(data[15])
    cargo['vendor_id'] = None if vendor_id == ZERO_UUID else vendor_id

    return cargo

def deserialize_vehicle(buffer: BytesIO) -> dict[str, Any]:
    '''Deserialize a single vehicle'''
    data = struct.unpack(VEHICLE_HEADER_FORMAT, buffer.read(struct.calcsize(VEHICLE_HEADER_FORMAT)))

    return {
        'vehicle_id': unpack_string(data[0]),
        'name': unpack_string(data[1]),
        'base_desc': unpack_string(data[2]),
        'wear': data[3],
        'base_fuel_efficiency': data[4],
        'base_top_speed': data[5],
        'base_offroad_capability': data[6],
        'base_cargo_capacity': data[7],
        'base_weight_capacity': data[8],
        'base_towing_capacity': data[9],
        'ap': data[10],
        'base_max_ap': data[11],
        'base_value': data[12],
        'vendor_id': unpack_string(data[13]),
        'warehouse_id': unpack_string(data[14])
    }

def deserialize_vendor(buffer: BytesIO) -> dict[str, Any]:
    '''Deserialize a single vendor'''
    header = struct.unpack(VENDOR_HEADER_FORMAT, buffer.read(struct.calcsize(VENDOR_HEADER_FORMAT)))

    cargo_count = header[11]
    vehicle_count = header[12]

    cargo_inventory = [deserialize_cargo(buffer) for _ in range(cargo_count)]
    vehicle_inventory = [deserialize_vehicle(buffer) for _ in range(vehicle_count)]

    return {
        'vendor_id': unpack_string(header[0]),
        'name': unpack_string(header[1]),
        'base_desc': unpack_string(header[2]),
        'money': header[3],
        'fuel': header[4],
        'fuel_price': header[5],
        'water': header[6],
        'water_price': header[7],
        'food': header[8],
        'food_price': header[9],
        'repair_price': header[10],
        '_cargo_inventory': cargo_inventory,
        '_vehicle_inventory': vehicle_inventory
    }

def deserialize_settlement(buffer: BytesIO) -> dict[str, Any]:
    '''Deserialize a single settlement'''
    header = struct.unpack(SETTLEMENT_HEADER_FORMAT, buffer.read(struct.calcsize(SETTLEMENT_HEADER_FORMAT)))
    sett_id = unpack_string(header[0])
    sett_types = {1: 'dome', 2: 'city', 3: 'town', 4: 'city-state', 5: 'military_base'}
    vendor_count = header[6]

    vendors = [deserialize_vendor(buffer) for _ in range(vendor_count)]
    [ v.update({'sett_id': sett_id}) for v in vendors ]

    return {
        'sett_id': sett_id,
        'name': unpack_string(header[1]),
        'sett_type': sett_types.get(header[3], 'unknown'),
        'vendors': vendors
    }

def deserialize_map(binary_data: bytes) -> dict[str, Any]:
    '''Deserialize the entire map structure'''
    buffer = BytesIO(binary_data)
    
    # Read map dimensions
    height, width = struct.unpack("!HH", buffer.read(4))
    
    # Read tiles
    tiles = []
    for y, _ in enumerate(range(height)):
        row = []
        for x, _ in enumerate(range(width)):
            header = struct.unpack(TERRAIN_FORMAT, buffer.read(struct.calcsize(TERRAIN_FORMAT)))
            settlement_count = header[4]
            
            settlements = [deserialize_settlement(buffer) for _ in range(settlement_count)]
            [ s.update({'x': x, 'y': y}) for s in settlements ]

            row.append({
                'x': x,
                'y': y,
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
    
    for location_list in (highlight_locations, lowlight_locations):
        count = struct.unpack("!H", buffer.read(2))[0]
        for _ in range(count):
            x, y = struct.unpack("!HH", buffer.read(4))
            location_list.append([x, y])
    
    return {
        'tiles': tiles,
        'highlight_locations': highlight_locations,
        'lowlight_locations': lowlight_locations
    }
