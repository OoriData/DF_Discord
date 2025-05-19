# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
'Vendor Menus'
import                  math
from datetime           import datetime, timezone, timedelta

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
            if vehicle['couplings']:
                couplings = ', '.join(  # Normalize lists as a single string
                    val.replace('_', ' ').capitalize()
                    for val in set(vehicle['couplings'])  # Use a set to ensure only unique values
                )
            else:
                couplings = None

            vehicle_str += '\n' + '\n'.join([
                line for line in [
                    f'  - *{vehicle['make_model']}*',
                    f'  - Efficiency 🌿: **{vehicle['efficiency']:.0f}** / 100',
                    f'  - Top Speed 🚀: **{vehicle['top_speed']:.0f}** / 100',
                    f'  - Offroad Capability 🥾: **{vehicle['offroad_capability']:.0f}** / 100',
                    f'  - Volume Capacity: **{vehicle['cargo_capacity']:.0f}**L' if vehicle.get('cargo_capacity') else None,
                    f'  - Weight Capacity: **{vehicle['weight_capacity']:.0f}**kg',
                    f'  - Coupling: **{couplings}**' if couplings else None,
                ] if line is not None]
            )

        vehicle_list.append(vehicle_str)
    return '\n'.join(vehicle_list) if vehicle_list else '- None'


async def vendor_inv_md(df_state: DFState, *, verbose: bool = False) -> str:
    """ Build the vendor inventory markdown from df_state """
    vendor_obj = df_state.vendor_obj

    displayable_resources = format_resources(vendor_obj)
    displayable_vehicles = vehicles_md(vendor_obj['vehicle_inventory'], verbose=verbose)
    displayable_cargo = await format_cargo(df_state, verbose=verbose, vendor=True)

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
    emoji_map = {'fuel': '⛽️', 'water': '💧', 'food': '🥪'}

    for resource in ['fuel', 'water', 'food']:
        if vendor_obj[resource]:
            unit = 'meals' if resource == 'food' else 'Liters'
            emoji = emoji_map[resource]

            resources_list.append(
                f'- {resource.capitalize()} {emoji}: {vendor_obj[resource]} {unit}\n'
                f'  - *${vendor_obj[f"{resource}_price"]:,.0f} per {unit[:-1]}*'
            )

    return '\n'.join(resources_list) if resources_list else '- None'


async def format_cargo(df_state: DFState, *, verbose: bool, vendor: bool = False) -> str:
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

        if vendor:
            cargo_str += format_clearance_info(cargo)

        # Add parts info if applicable and verbose
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
    cargo_emoji_map = {'fuel': '🛢️', 'water': '🥤', 'food': '🥡'}     # For (container) cargo
    resource_emoji_map = {'fuel': '⛽️', 'water': '💧', 'food': '🥪'}  # For resources

    cargo_emoji = ''
    if cargo.get('recipient'):
        cargo_emoji = '| 📦'
    if cargo.get('parts'):
        cargo_emoji = '| ⚙️'

    resource_str = ''
    for resource in ['fuel', 'water', 'food']:
        if cargo.get(resource):
            cargo_emoji = f'| {cargo_emoji_map[resource]}'
            resource_emoji = resource_emoji_map[resource]

            unit = ' meals' if resource == 'food' else 'L'
            resource_str = (
                f'\n  - {resource.capitalize()} {resource_emoji}: '
                f'{cargo['unit_capacity']:,.0f}{unit} each'
            )
            break  # Cargo can only contain one resource

    cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) {cargo_emoji} | *${cargo['wet_unit_price']:,.0f} each*'
    cargo_str += resource_str

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

    # Add vendor's (source) position too — needed for distance calculation later
    cargo['vendor_x'] = df_state.vendor_obj['x']
    cargo['vendor_y'] = df_state.vendor_obj['y']


def format_delivery_info(cargo: dict) -> str:
    """ Format delivery details (destination, profit, distance, volume/weight) """
    vendor_obj = cargo['recipient_vendor']
    vendor_location = cargo['recipient_location']
    delivery_info = [
        f'\n  - Deliver to *{vendor_location}* | ***${cargo['unit_delivery_reward']:,.0f}*** *each on delivery*'
    ]

    margin = min(round(cargo['unit_delivery_reward'] / cargo['unit_price']), 24)
    delivery_info.append(f'\n  - Profit margin: {'💵 ' * margin}')

    tile_distance = math.sqrt(
        (vendor_obj['x'] - cargo['vendor_x']) ** 2 +
        (vendor_obj['y'] - cargo['vendor_y']) ** 2
    )
    distance_km = 50 * tile_distance
    distance_miles = 30 * tile_distance
    delivery_info.append(f'\n  - Distance: {distance_km:,.0f} km ({distance_miles:,.0f} miles)')

    delivery_info.append(f'\n  - Volume/Weight: {cargo['unit_volume']:,}L / {cargo['unit_weight']:,.2f}kg *each*')

    return ''.join(delivery_info)


def format_clearance_info(cargo: dict) -> str:
    """ Check if cargo is on clearance and return a discount string if so. """
    try:
        creation_date_str = cargo.get('creation_date')
        if not creation_date_str:
            return '' # No date to check against
        
        cargo_creation_dt = datetime.fromisoformat(creation_date_str).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        # Define constants for clarity
        MSRP_DURATION = timedelta(days=5)
        # Clearance sale starts if cargo is older than MSRP_DURATION by more than this grace period.
        # Original logic: sale if age > MSRP_DURATION + timedelta(days=1)
        CLEARANCE_SALE_GRACE_PERIOD = timedelta(days=1)

        DAILY_DISCOUNT_RATE = 20  # Percent per day
        MAX_DISCOUNT_PERCENTAGE = 40

        cargo_actual_age = now - cargo_creation_dt
        
        # Calculate how long ago the MSRP duration ended for this cargo.
        # If positive, MSRP duration has passed. If negative, still within MSRP.
        time_since_msrp_ended = cargo_actual_age - MSRP_DURATION

        # Check if cargo is old enough to be on clearance sale.
        # Sale starts if cargo_actual_age > MSRP_DURATION + CLEARANCE_SALE_GRACE_PERIOD
        if time_since_msrp_ended > CLEARANCE_SALE_GRACE_PERIOD:
            # Cargo is on clearance. Discount is based on the number of full days past MSRP_DURATION.
            # e.g., if time_since_msrp_ended is (1 day + 1 sec), discount_basis_days = 1 -> 20% discount.
            # e.g., if time_since_msrp_ended is (2 days), discount_basis_days = 2 -> 40% discount.
            discount_basis_days = time_since_msrp_ended.days
            
            discount_percentage = min(discount_basis_days * DAILY_DISCOUNT_RATE, MAX_DISCOUNT_PERCENTAGE)
            return f'\n  - *Clearance! {discount_percentage}% off!* 🏷️'  # + f' `CARGO IS {(now - cargo_age).days} DAYS OLD`'
    except (ValueError, TypeError):
        # Handle potential errors during date parsing/comparison gracefully
        return '' # Don't add clearance info if dates are problematic
    return '' # Not on sale or an error occurred


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
            total_installation_price = cargo['unit_price'] + sum(vp['installation_price'] for vp in compatibilities)
            parts_info += f'✅ Total installation price: **${total_installation_price:,.0f}**'

    return parts_info


def wet_price(cargo: dict, vendor: dict, quantity: int = 1) -> int:
    """ Get the wet price of a quantity of cargo based on a vendor's current resource pricing """
    resource_price = 0
    for resource, price_key in [('fuel', 'fuel_price'), ('water', 'water_price'), ('food', 'food_price')]:
        resource_amount = cargo.get(resource)
        if resource_amount:
            if not vendor[price_key]:
                resource_price = 0
                break

            unit_proportion = quantity / cargo['quantity']
            resource_price += resource_amount * unit_proportion * vendor[price_key]

    dry_price = cargo['unit_price'] * quantity

    return dry_price + resource_price
