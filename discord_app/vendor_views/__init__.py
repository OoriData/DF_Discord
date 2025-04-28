# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Vendor Menus'
import                  math

from discord_app import api_calls, DFState, get_vehicle_emoji


def vehicles_md(vehicles, verbose: bool = False):
    vehicle_list = []
    for vehicle in vehicles:
        if vehicle.get('internal_combustion') and vehicle.get('electric'):
            powered_by_emoji = '⛽️🔋'
        elif vehicle.get('internal_combustion'):
            powered_by_emoji = '⛽️'
        elif vehicle.get('electric'):
            powered_by_emoji = '🔋'
        vehicle_str = f'- {get_vehicle_emoji(vehicle['shape'])} | **{vehicle['name']}** | {powered_by_emoji} | *${vehicle['value']:,}*'

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


async def vendor_inv_md(df_state: DFState, *, verbose: bool = False) -> str:
    """ Build the vendor inventory markdown from df_state """
    vendor_obj = df_state.vendor_obj

    displayable_resources = format_resources(vendor_obj)
    displayable_vehicles = vehicles_md(vendor_obj['vehicle_inventory'], verbose=verbose)
    displayable_cargo = await format_cargo(df_state, verbose=verbose)

    md = '\n'.join([
        f'## {vendor_obj['name']}',
        '### Available for Purchase',
        '**Resources:**',
        displayable_resources,
        '',
        '**Vehicles:**',
        displayable_vehicles,
        '',
        '**Cargo:**',
        displayable_cargo
    ])

    return md


def format_resources(vendor_obj: dict) -> str:
    """ Format available resources for sale into markdown """
    resources_list = []
    for resource in ['fuel', 'water', 'food']:
        if vendor_obj[resource]:
            unit = 'meals' if resource == 'food' else 'Liters'
            resources_list.append(
                f'- {resource.capitalize()}: {vendor_obj[resource]} {unit}\n  - *${vendor_obj[f'{resource}_price']:,.0f} per {unit[:-1]}*'
            )
    return '\n'.join(resources_list) if resources_list else '- None'


async def format_cargo(df_state: DFState, *, verbose: bool) -> str:
    """ Format the vendor's cargo inventory into markdown """
    vendor_obj = df_state.vendor_obj
    convoy_obj = df_state.convoy_obj
    cargo_list = []

    for cargo in vendor_obj['cargo_inventory']:
        update_wet_unit_price(cargo, vendor_obj)

        if is_cargo_invalid(cargo, vendor_obj):
            continue

        cargo_str = format_basic_cargo(cargo)

        if cargo['recipient']:
            await enrich_delivery_info(df_state, cargo, verbose)

            if verbose and cargo.get('recipient_vendor'):
                cargo_str += format_delivery_info(cargo)

        if verbose and cargo.get('parts'):
            await enrich_parts_compatibility(convoy_obj, cargo)
            cargo_str += format_parts_compatibility(convoy_obj, cargo, verbose=verbose)

        cargo_list.append(cargo_str)

    return '\n'.join(cargo_list) if cargo_list else '- None'


def update_wet_unit_price(cargo: dict, vendor_obj: dict) -> None:
    """ Update cargo pricing based on resource consumption (fuel, water, food) """
    for resource in ['fuel', 'water', 'food']:
        if cargo.get(resource) is not None and vendor_obj.get(f'{resource}_price') is not None:
            unit_resource = cargo[resource] / cargo['quantity']
            cargo['wet_unit_price'] = round(cargo['unit_price'] + unit_resource * vendor_obj[f'{resource}_price'], 2)
            return
    # Fallback: no adjustment needed
    cargo['wet_unit_price'] = cargo['unit_price']


def is_cargo_invalid(cargo: dict, vendor_obj: dict) -> bool:
    """ Determine if cargo should be skipped because required vendor pricing is missing """
    for resource in ['fuel', 'water', 'food']:
        if cargo.get(resource) is not None and vendor_obj.get(f'{resource}_price') is None:
            return True
    return False


def format_basic_cargo(cargo: dict) -> str:
    """ Format basic cargo listing (quantity, price, attached resources) """
    cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *${cargo['wet_unit_price']:,.0f} each*'
    for resource in ['fuel', 'water', 'food']:
        if cargo.get(resource):
            unit = ' meals' if resource == 'food' else 'L'
            cargo_str += f'\n  - {resource.capitalize()}: {cargo['unit_capacity']:,f}{unit} each'
    return cargo_str


async def enrich_delivery_info(df_state: DFState, cargo: dict, verbose: bool) -> None:
    """ Attach vendor and location info to deliverable cargo """
    if not cargo.get('recipient_vendor'):
        cargo['recipient_vendor'] = await api_calls.get_vendor(vendor_id=cargo['recipient'])

    if cargo.get('recipient_vendor'):
        cargo['recipient_location'] = next((
            s['name']
            for row in df_state.map_obj['tiles']
            for t in row
            for s in t['settlements']
            if s['sett_id'] == cargo['recipient_vendor']['sett_id']
        ), None)


def format_delivery_info(cargo: dict) -> str:
    """ Format delivery details (destination, profit, distance, volume/weight) """
    vendor_obj = cargo['recipient_vendor']
    vendor_location = cargo['recipient_location']
    delivery_info = [
        f'\n  - Deliver to *{vendor_location}* | ***${cargo['unit_delivery_reward']:,.0f}*** *each*'
    ]

    margin = min(round(cargo['unit_delivery_reward'] / cargo['unit_price']), 24)
    delivery_info.append(f'\n  - Profit margin: {"💵 " * margin}')

    tile_distance = math.sqrt(
        (vendor_obj['x'] - cargo['vendor_x']) ** 2 +
        (vendor_obj['y'] - cargo['vendor_y']) ** 2
    )
    distance_km = 50 * tile_distance
    distance_miles = 30 * tile_distance
    delivery_info.append(f'\n  - Distance: {distance_km:,.0f} km ({distance_miles:,.0f} miles)')

    delivery_info.append(f'\n  - Volume/Weight: {cargo['unit_volume']:,}L / {cargo['unit_weight']:,}kg *each*')

    return ''.join(delivery_info)


async def enrich_parts_compatibility(convoy_obj: dict, cargo: dict) -> None:
    """ Attach parts compatibility check results to cargo """
    cargo['compatibilities'] = {}
    for vehicle in convoy_obj['vehicles']:
        try:
            cargo['compatibilities'][vehicle['vehicle_id']] = await api_calls.check_part_compatibility(
                vehicle_id=vehicle['vehicle_id'],
                part_cargo_id=cargo['cargo_id']
            )
        except RuntimeError as e:
            cargo['compatibilities'][vehicle['vehicle_id']] = e


def format_parts_compatibility(convoy_obj: dict, cargo: dict, verbose: bool = False) -> str:
    """ Format parts compatibility details for vehicles """
    parts_info = ''
    for vehicle in convoy_obj['vehicles']:
        compatibilities = cargo['compatibilities'].get(vehicle['vehicle_id'])
        parts_info += f'\n  - {get_vehicle_emoji(vehicle['shape'])} | {vehicle['name']} | '

        if isinstance(compatibilities, RuntimeError):
            parts_info += '❌ Incompatible'
            
            if verbose:
                parts_info += f': *{compatibilities}*'

        else:
            total_installation_price = sum(vp['installation_price'] for vp in compatibilities)
            
            parts_info += f'✅ Total installation price: *${total_installation_price:,.0f}*'

    return parts_info


def wet_price(cargo: dict, vendor: dict, quantity: int = 1) -> int:
    """ Get the wet price of a quantity of cargo based on a vendor's current resource pricing """
    resource_price = 0
    for resource, price_key in [('fuel', 'fuel_price'), ('water', 'water_price'), ('food', 'food_price')]:
        resource_amount = cargo.get(resource)
        if resource_amount:
            unit_proportion = quantity / cargo['quantity']
            resource_price += resource_amount * unit_proportion * vendor[price_key]
    
    dry_price = cargo['unit_price'] * quantity

    return dry_price + resource_price
