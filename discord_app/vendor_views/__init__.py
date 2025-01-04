# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Vendor Menus'
import                  math

from discord_app import api_calls

def vehicles_md(vehicles, verbose: bool = False):
    vehicle_list = []
    for vehicle in vehicles:
        vehicle_str = f'- {vehicle['name']} | *${vehicle['value']:,}*'

        if verbose:
            vehicle_str += '\n' + '\n'.join([
                f'  - *{vehicle['make_model']}*',
                f'  - Top Speed: **{vehicle['top_speed']}** / 100',
                f'  - Fuel Efficiency: **{vehicle['fuel_efficiency']}** / 100',
                f'  - Offroad Capability: **{vehicle['offroad_capability']}** / 100',
                f'  - Volume Capacity: **{vehicle['cargo_capacity']}**L',
                f'  - Weight Capacity: **{vehicle['weight_capacity']}**kg'
            ])

        vehicle_list.append(vehicle_str)
    return '\n'.join(vehicle_list) if vehicle_list else '- None'


async def vendor_inv_md(vendor_obj, *, verbose: bool = False) -> str:
    resources_list = []
    for resource in ['fuel', 'water', 'food']:
        if vendor_obj[resource]:
            unit = 'meals' if resource == 'food' else 'Liters'
            resources_list.append(f'- {resource.capitalize()}: {vendor_obj[resource]} {unit}\n  - *${vendor_obj[f'{resource}_price']:,.0f} per {unit[:-1]}*')
    displayable_resources = '\n'.join(resources_list) if resources_list else '- None'

    displayable_vehicles = vehicles_md(vendor_obj['vehicle_inventory'], verbose=verbose)

    cargo_list = []
    for cargo in vendor_obj['cargo_inventory']:
        cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *${cargo['price']:,} each*'

        if verbose:
            for resource in ['fuel', 'water', 'food']:
                if cargo[resource]:
                    unit = ' meals' if resource == 'food' else 'L'
                    cargo_str += f'\n  - {resource.capitalize()}: {cargo[resource]:,.0f}{unit}'

            if cargo.get('recipient_vendor'):
                cargo_str += f'\n  - Deliver to *{cargo['recipient_location']}* | ***${cargo['delivery_reward']:,.0f}*** *each*'
                margin = round(cargo['delivery_reward'] / cargo['price'])
                cargo_str += f'\n  - Profit margin: {'💵 ' * margin}'
                tile_distance = math.sqrt(
                    (cargo['recipient_vendor']['x'] - vendor_obj['x']) ** 2
                    + (cargo['recipient_vendor']['y'] - vendor_obj['y']) ** 2
                )
                distance_km = 50 * tile_distance
                distance_miles = 30 * tile_distance
                cargo_str += f'\n  - Distance: {distance_km:,.0f} km ({distance_miles:,.0f} miles)'
                cargo_str += f'\n  - Volume/Weight: {cargo['volume']:,}L / {cargo['weight']:,}kg *each*'

        cargo_list.append(cargo_str)
    displayable_cargo = '\n'.join(cargo_list) if cargo_list else '- None'

    return '\n'.join([
        f'## {vendor_obj['name']}',
        '### Available for Purchase',
        '**Resources:**',
        f'{displayable_resources}',
        '',
        '**Vehicles:**',
        f'{displayable_vehicles}',
        '',
        '**Cargo:**',
        f'{displayable_cargo}'
    ])
