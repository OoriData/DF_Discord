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
                f'  - Top Speed: **{vehicle['top_speed']:.0f}** / 100',
                f'  - Efficiency: **{vehicle['efficiency']:.0f}** / 100',
                f'  - Offroad Capability: **{vehicle['offroad_capability']:.0f}** / 100',
                f'  - Volume Capacity: **{vehicle['cargo_capacity']:.0f}**L',
                f'  - Weight Capacity: **{vehicle['weight_capacity']:.0f}**kg'
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
        if cargo['fuel'] is not None and vendor_obj['fuel_price'] is not None:
            unit_fuel = cargo['fuel'] / cargo['quantity']
            cargo['wet_unit_price'] = round(cargo['unit_price'] + unit_fuel * vendor_obj['fuel_price'], 2)
        elif cargo['water'] is not None and vendor_obj['water_price'] is not None:
            unit_water = cargo['water'] / cargo['quantity']
            cargo['wet_unit_price'] = round(cargo['unit_price'] + unit_water * vendor_obj['water_price'], 2)
        elif cargo['food'] is not None and vendor_obj['food_price'] is not None:
            unit_food = cargo['food'] / cargo['quantity']
            cargo['wet_unit_price'] = round(cargo['unit_price'] + unit_food * vendor_obj['food_price'], 2)
        else:
            cargo['wet_unit_price'] = cargo['unit_price']

        if vendor_obj['fuel_price'] is None and cargo['fuel'] is not None:
            continue
        if vendor_obj['water_price'] is None and cargo['water'] is not None:
            continue
        if vendor_obj['food_price'] is None and cargo['food'] is not None:
            continue

        cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *${cargo['wet_unit_price']:,.0f} each*'

        if verbose:
            for resource in ['fuel', 'water', 'food']:
                if cargo[resource]:
                    unit = ' meals' if resource == 'food' else 'L'
                    cargo_str += f'\n  - {resource.capitalize()}: {cargo[resource]:,.0f}{unit}'

            if cargo.get('recipient_vendor'):
                cargo_str += f'\n  - Deliver to *{cargo['recipient_location']}* | ***${cargo['unit_delivery_reward']:,.0f}*** *each*'
                margin = min(round(cargo['unit_delivery_reward'] / cargo['unit_price']), 24)  # limit emojis to 24
                cargo_str += f'\n  - Profit margin: {'💵 ' * margin}'
                tile_distance = math.sqrt(
                    (cargo['recipient_vendor']['x'] - vendor_obj['x']) ** 2
                    + (cargo['recipient_vendor']['y'] - vendor_obj['y']) ** 2
                )
                distance_km = 50 * tile_distance
                distance_miles = 30 * tile_distance
                cargo_str += f'\n  - Distance: {distance_km:,.0f} km ({distance_miles:,.0f} miles)'
                cargo_str += f'\n  - Volume/Weight: {cargo['unit_volume']:,}L / {cargo['unit_weight']:,}kg *each*'

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

def wet_price(cargo: dict, vendor: dict, quantity: int = 1) -> int:
    """ Get the wet price of a quantity of cargo based on a vendor's current resource pricing """
    resource_price = 0
    for resource, price_key in [('fuel', 'fuel_price'), ('water', 'water_price'), ('food', 'food_price')]:
        resource_amount = cargo.get(resource)
        if resource_amount:
            unit_proportion = quantity / cargo['quantity']
            resource_price += resource_amount * unit_proportion * vendor[price_key]

    return cargo['unit_price'] + resource_price
