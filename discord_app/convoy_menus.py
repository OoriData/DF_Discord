# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                math

import                                discord
import                                logging

from utiloori.ansi_color       import ansi_color

from discord_app               import (
    api_calls, dialogue_menus, handle_timeout, discord_timestamp, df_embed_author, add_tutorial_embed,
    get_user_metadata, validate_interaction, DF_LOGO_EMOJI, OORI_WHITE, get_vehicle_emoji, get_settlement_emoji,
    get_cargo_emoji
)
import discord_app.cargo_menus
import discord_app.vehicle_menus
import discord_app.vendor_views.buy_menus
from discord_app.map_rendering import add_map_to_embed
from discord_app.nav_menus     import add_nav_buttons
from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

logger = logging.getLogger('DF_Discord')
logging.basicConfig(format='%(levelname)s:%(name)s: %(message)s', level=LOG_LEVEL)


def fuzz(amount: float) -> int:
    """ Fuzzes the amount to the nearest integer or multiple of 10. """
    if amount < 20:  # If the amount is less than 10, round up to the nearest integer
        return int(amount) if amount == int(amount) else int(amount) + 1

    return int((amount + 9) // 10 * 10)  # Round up to the nearest multiple of 10


async def convoy_menu(df_state: DFState, edit: bool = True):
    df_state.append_menu_to_back_stack(func=convoy_menu)  # Add this menu to the back stack

    if not df_state.interaction.response.is_done():
        await df_state.interaction.response.defer()

    embeds, image_file = await make_convoy_embed(df_state)

    embeds = add_tutorial_embed(embeds, df_state)

    view = ConvoyView(df_state)

    tutorial_stage = get_user_metadata(df_state, 'tutorial')
    og_message = await df_state.interaction.original_response()

    if tutorial_stage in {1, 2, 3, 4}:  # If we are in the early tutorial:
        await df_state.interaction.followup.edit_message(og_message.id, embeds=embeds, view=view, attachments=[])

    else:  # Not in the tutorial
        await df_state.interaction.followup.edit_message(
            og_message.id,
            embeds=embeds,
            view=view,
            attachments=[image_file]
        )

async def make_convoy_embed(
        df_state: DFState,
        prospective_journey_plus_misc=None
) -> list[list[discord.Embed], discord.File]:
    convoy_embed = discord.Embed(color=discord.Color.from_rgb(*OORI_WHITE))
    convoy_embed = df_embed_author(convoy_embed, df_state)

    convoy_embed.description = vehicles_embed_str(df_state.convoy_obj['vehicles'])

    if get_user_metadata(df_state, 'mobile'):
        convoy_embed.description += '\n' + '\n'.join([
            '### Convoy Stats',
            f'Fuel ⛽️: **{df_state.convoy_obj['fuel']:,.2f}** / {df_state.convoy_obj['max_fuel']:.0f}L',
            f'Water 💧: **{df_state.convoy_obj['water']:,.2f}** / {df_state.convoy_obj['max_water']:.0f}L',
            f'Food 🥪: **{df_state.convoy_obj['food']:,.2f}** / {df_state.convoy_obj['max_food']:.0f} meals',
            f'Efficiency 🌿: **{df_state.convoy_obj['efficiency']:.0f}** / 100',
            f'Top Speed 🚀: **{df_state.convoy_obj['top_speed']:.0f}** / 100',
            f'Offroad Capability 🏔️: **{df_state.convoy_obj['offroad_capability']:.0f}** / 100'
        ])
    else:
        convoy_embed.add_field(
            name='Fuel ⛽️',
            value=f'**{df_state.convoy_obj['fuel']:,.2f}**\n/ {df_state.convoy_obj['max_fuel']:.0f} liters'
        )
        convoy_embed.add_field(
            name='Water 💧',
            value=f'**{df_state.convoy_obj['water']:,.2f}**\n/ {df_state.convoy_obj['max_water']:.0f} liters'
        )
        convoy_embed.add_field(
            name='Food 🥪',
            value=f'**{df_state.convoy_obj['food']:,.2f}**\n/ {df_state.convoy_obj['max_food']:.0f} meals'
        )

        convoy_embed.add_field(
            name='Efficiency 🌿',
            value=f'**{df_state.convoy_obj['efficiency']:.0f}**\n/ 100'
        )
        convoy_embed.add_field(
            name='Top Speed 🚀',
            value=f'**{df_state.convoy_obj['top_speed']:.0f}**\n/ 100'
        )
        convoy_embed.add_field(
            name='Offroad Capability 🏔️',
            value=f'**{df_state.convoy_obj['offroad_capability']:.0f}**\n/ 100'
        )

    convoy_x = df_state.convoy_obj['x']
    convoy_y = df_state.convoy_obj['y']

    if df_state.convoy_obj['journey']:  # If the convoy is in tra`nsit
        extra_embed = discord.Embed(color=discord.Color.from_rgb(*OORI_WHITE))

        journey = df_state.convoy_obj['journey']
        route_tiles = []  # a list of tuples
        pos = 0  # bad way to do it but i'll fix later
        for x in journey['route_x']:
            y = journey['route_y'][pos]
            route_tiles.append((x, y))
            pos += 1

        destination = await api_calls.get_tile(journey['dest_x'], journey['dest_y'])

        eta = df_state.convoy_obj['journey']['eta']
        progress_percent = ((journey['progress']) / len(journey['route_x'])) * 100
        progress_in_km = journey['progress'] * 50  # progress is measured in tiles; tiles are 50km to a side
        progress_in_miles = journey['progress'] * 30  # progress is measured in tiles; tiles are 50km to a side

        if get_user_metadata(df_state, 'mobile'):
            extra_embed.description = '\n' + '\n'.join([
                '### Journey',
                f'Destination 📍: **{destination['settlements'][0]['name']}**',
                f'ETA ⏰: **{discord_timestamp(eta, 'R')}** ({discord_timestamp(eta, 't')})',
                f'Progress 🏁: **{progress_percent:.1f}%** ({progress_in_miles:.0f} miles)'
            ])
        else:
            extra_embed.add_field(
                name='Destination 📍',
                value=(
                    f'**{destination['settlements'][0]['name']}**\n'
                    f'({journey['dest_x']}, {journey['dest_y']})'  # XXX: replace coords with `{territory_name}`
                )
            )
            extra_embed.add_field(
                name='ETA ⏰',
                value=f'**{discord_timestamp(eta, 'R')}**\n{discord_timestamp(eta, 't')}'
            )
            extra_embed.add_field(
                name='Progress 🏁',
                value=f'**{progress_percent:.1f}%**\n{progress_in_km:.0f} km ({progress_in_miles:.0f} miles)'
            )

        convoy_embed, image_file = await add_map_to_embed(  # Add map to main convoy embed
            embed=convoy_embed,
            highlights=[(convoy_x, convoy_y)],
            lowlights=route_tiles,
            map_obj=df_state.map_obj
        )

        embeds = [convoy_embed, extra_embed]

    elif prospective_journey_plus_misc:  # If a journey is being considered
        extra_embed = discord.Embed(color=discord.Color.from_rgb(*OORI_WHITE))

        route_tiles = []  # a list of tuples
        pos = 0  # bad way to do it but i'll fix later
        for x in prospective_journey_plus_misc['journey']['route_x']:
            y = prospective_journey_plus_misc['journey']['route_y'][pos]
            route_tiles.append((x, y))
            pos += 1

        destination = await api_calls.get_tile(
            x=prospective_journey_plus_misc['journey']['dest_x'],
            y=prospective_journey_plus_misc['journey']['dest_y']
        )

        delta_t = discord_timestamp(
            formatted_time=datetime.now(timezone.utc) + timedelta(minutes=prospective_journey_plus_misc['delta_t']),
            format_letter='R'
        )
        eta_discord_time = discord_timestamp(
            formatted_time=datetime.now(timezone.utc) + timedelta(minutes=prospective_journey_plus_misc['delta_t']),
            format_letter='t'
        )

        distance_km = 50 * len(prospective_journey_plus_misc['journey']['route_x'])
        distance_miles = 30 * len(prospective_journey_plus_misc['journey']['route_x'])

        # Print the expenses for debugging
        expenses_print = '\n'.join([
            f'(Sum) Fuel expenses: {sum(prospective_journey_plus_misc['fuel_expenses'].values()):.3f}',
            f'Water expense: {prospective_journey_plus_misc['water_expense']:.3f}',
            f'Food expense: {prospective_journey_plus_misc['food_expense']:.3f}',
            'kWh expenses:'
        ])
        for vehicle in df_state.convoy_obj['vehicles']:
            if vehicle['electric']:
                expenses_print += (
                    f'\n- {vehicle['name']}: '
                    f'{prospective_journey_plus_misc['kwh_expenses'][vehicle['vehicle_id']]:.3f}'
                )
        logger.debug(ansi_color(text=expenses_print, font_color='yellow'))
        
        # Fuzz the expenses
        fuzzed_fuel_expense = fuzz(sum(prospective_journey_plus_misc['fuel_expenses'].values()))
        fuzzed_water_expense = fuzz(prospective_journey_plus_misc['water_expense'])
        fuzzed_food_expense = fuzz(prospective_journey_plus_misc['food_expense'])

        # Add expense fields to the embed
        if get_user_metadata(df_state, 'mobile'):  # If the user is on mobile
            extra_embed.description = '\n' + '\n'.join([
                '### Estimated Journey Cost',
                f'- Fuel expense: **{fuzzed_fuel_expense:.0f}**L',
                f'- Water expense: **{fuzzed_water_expense:.0f}**L',
                f'- Food expense: **{fuzzed_food_expense:.0f}** meals',
                f'- Destination 📍: **{destination['settlements'][0]['name']}**',
                f'- ETA ⏰: **{delta_t}** ({eta_discord_time})',
                f'- Distance 🗺️: {distance_miles} miles',
            ])
        else:  # If the user is on desktop
            extra_embed.add_field(name='Journey fuel expense', value=f'**{fuzzed_fuel_expense:.0f}** liters')
            extra_embed.add_field(name='Journey water expense', value=f'**{fuzzed_water_expense:.0f}** liters')
            extra_embed.add_field(name='Journey food expense', value=f'**{fuzzed_food_expense:.0f}** meals')

            extra_embed.add_field(
                name='Destination 📍',
                value=(
                    f'**{destination['settlements'][0]['name']}**\n'
                    f'({prospective_journey_plus_misc['journey']['dest_x']}, '  # XXX: replace coords with `\n{territory_name}`
                    f'{prospective_journey_plus_misc['journey']['dest_y']})'    # XXX: replace coords with `\n{territory_name}`
                )
            )
            extra_embed.add_field(name='ETA ⏰', value=f'**{delta_t}**\n{eta_discord_time}')
            extra_embed.add_field(name='Distance 🗺️', value=f'**{distance_km:,} km**\n{distance_miles} miles')

        for vehicle in df_state.convoy_obj['vehicles']:  # Add vehicle-specific kWh expenses to the embed
            if vehicle['electric']:
                fuzzed_kwh_expense = fuzz(prospective_journey_plus_misc['kwh_expenses'][vehicle['vehicle_id']])

                battery = next(c for c in vehicle['cargo'] if c.get('kwh') is not None)
                battery_charge = battery['kwh']
                battery_size = battery['capacity']

                # Ensure kWh expense doesn't exceed battery charge
                fuzzed_kwh_expense = min(fuzzed_kwh_expense, battery_charge)

                remaining_charge = battery_charge - fuzzed_kwh_expense
                batt_emoji = '🔋' if remaining_charge > (battery_size * 0.2) else '🪫'

                if get_user_metadata(df_state, 'mobile'):
                    extra_embed.description += (
                        f'\n- {vehicle['name']} {get_vehicle_emoji(vehicle['shape'])} '
                        f'kWh expense: **{fuzzed_kwh_expense:.0f}** kWh {batt_emoji}\n'
                        f'({battery_charge}/{battery_size} kWh)'
                    )
                else:
                    extra_embed.add_field(
                        name=f'{vehicle['name']} {get_vehicle_emoji(vehicle['shape'])} kWh expense',
                        value=(
                            f'**{fuzzed_kwh_expense:.0f}** kWh {batt_emoji}\n'
                            f'({battery_charge:.0f} / {battery_size} kWh)'
                        )
                    )

        convoy_embed, image_file = await add_map_to_embed(  # Add map to main convoy embed
            embed=convoy_embed,
            highlights=[(convoy_x, convoy_y)],
            lowlights=route_tiles,
            map_obj=df_state.map_obj
        )

        embeds = [convoy_embed, extra_embed]

    else:  # If the convoy is just chilling somewhere
        convoy_embed, image_file = await add_map_to_embed(
            embed=convoy_embed,
            highlights=[(convoy_x, convoy_y)],
            map_obj=df_state.map_obj
        )

        embeds = [convoy_embed]

    return embeds, image_file

def vehicles_embed_str(vehicles: list[dict], verbose: bool | None = False) -> str:
    vehicles_list = []
    vehicles_str = '### Vehicles\n'

    sorted_vehicles = sorted(vehicles, key=lambda x: x['name'], reverse=True)
    if sorted_vehicles:
        for vehicle in sorted_vehicles:
            vehicle_str = f'**{vehicle['name']}** {get_vehicle_emoji(vehicle['shape'])}'
            # vehicle_str += f' | 🌿 {vehicle['efficiency']} | 🚀 {vehicle['top_speed']} | 🏔️ {vehicle['offroad_capability']}'
            vehicle_str += '\n'
            if verbose:
                vehicle_str += '\n'.join([
                    f'- AP: **{vehicle['ap']:.0f}** / {vehicle['max_ap']}',
                    f'- Efficiency: **{vehicle['efficiency']:.0f}** / 100',
                    f'- Top Speed: **{vehicle['top_speed']:.0f}** / 100',
                    f'- Offroad Capability: **{vehicle['offroad_capability']:.0f}** / 100',
                    ''
                ])

            if vehicle['electric']:
                battery = next(c for c in vehicle['cargo'] if c.get('kwh') is not None)
                battery_emoji = '🔋' if battery['kwh'] > (battery['capacity'] * 0.2) else '🪫'
                vehicle_str += f'- Charge {battery_emoji}: **{battery['kwh']:.2f}** / {battery['capacity']} kWh\n'

            vehicle_str += f'- Cargo load: **{vehicle['total_cargo_volume']:,.0f}** / {vehicle['cargo_capacity']} liters'
            vehicle_str += f' & **{vehicle['total_cargo_weight']:,.0f}** / {vehicle['weight_capacity']} kg'

            # more verbose option, can we find a way to have this as well, without being as wordy?
            # vehicle_str += f'- Cargo load: **{vehicle['total_cargo_volume']}** / {vehicle['cargo_capacity']} liters ({vehicle['cargo_capacity'] - vehicle['total_cargo_volume']} available)'
            # vehicle_str += f' & **{vehicle['total_cargo_weight']}** / {vehicle['weight_capacity']} kg ({vehicle['weight_capacity'] - vehicle['']} available)'

            vehicles_list.append(vehicle_str)

        vehicles_str += '\n'.join(vehicles_list)

        total_cargo_volume = sum(vehicle['total_cargo_volume'] for vehicle in vehicles)
        total_volume_capacity = sum(vehicle['cargo_capacity'] for vehicle in vehicles)

        total_cargo_weight = sum(vehicle['total_cargo_weight'] for vehicle in vehicles)
        total_weight_capacity = sum(vehicle['weight_capacity'] for vehicle in vehicles)

        vehicles_str += f'\n**Total space across convoy**: **{total_cargo_volume:,.2f}** / {total_volume_capacity} liters'
        vehicles_str += f' & **{total_cargo_weight:,.2f}** / {total_weight_capacity} kg'

    else:
        vehicles_str = '*No vehicles in convoy. Buy one at the dealership.*'

    return vehicles_str

class ConvoyView(discord.ui.View):
    """ Overarching convoy button menu """
    def __init__(
            self,
            df_state: DFState
    ):
        self.df_state = df_state
        super().__init__(timeout=600)

        add_nav_buttons(self, df_state)

        self.add_item(JourneyButton(df_state=self.df_state))
        self.add_item(ConvoyVehicleSelect(df_state=self.df_state, row=2))
        self.add_item(ConvoyCargoSelect(df_state=self.df_state, row=3))

        recipients = []
        # Get all cargo recipient locations and put em in a tuple with the name of the cargo
        for cargo in self.df_state.convoy_obj['all_cargo']:
            if cargo['recipient']:
                cargo_tuple = (cargo['recipient'], cargo['name'])
                if cargo_tuple not in recipients:
                    # add vendor id and cargo name as a tuple
                    recipients.append(cargo_tuple)

        if not recipients:
            self.all_cargo_destinations_button.disabled = True

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                match tutorial_stage:  # Use match-case to handle different tutorial stages
                    case 1 | 2 | 3 | 4:  # Enable 'nav_sett_button' only for stages 1-4, disable all others
                        item.disabled = item.custom_id not in (
                            'nav_back_button',
                            'nav_sett_button'
                        )
                    case 5:  # Enable 'send_convoy_button' for stage 5, disable all others
                        item.disabled = item.custom_id not in (
                            'nav_back_button',
                            'journey_button'
                        )

    @discord.ui.button(label='All Cargo Destinations', style=discord.ButtonStyle.blurple, custom_id='all_cargo_destinations_button', emoji='🗺️', row=4)
    async def all_cargo_destinations_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        await interaction.response.defer()

        cargo_for_delivery = [cargo for cargo in self.df_state.convoy_obj['all_cargo'] if cargo['recipient']]

        deliveries = []
        recipient_coords = []
        for cargo in cargo_for_delivery:  # For each deliverable cargo, get vendor's details and add it to destinations
            recipient_vendor = await api_calls.get_vendor(cargo['recipient'])

            # Grab destination name to display to user
            deliveries.append(f'- {cargo['name']}\n  - Deliver to **{recipient_vendor['name']}**\n  - ${cargo['delivery_reward'] * cargo['quantity']} total delivery reward')

            # And recipient_coords for map rendering
            recipient_coords.append((recipient_vendor['x'], recipient_vendor['y']))

        dest_string = '\n'.join(deliveries)

        convoy_coords = [(self.df_state.convoy_obj['x'], self.df_state.convoy_obj['y'])]

        dest_embed = discord.Embed(
            title=f'All cargo destinations in {self.df_state.convoy_obj['name']}',
            description=dest_string
        )

        map_embed, image_file = await add_map_to_embed(
            embed=dest_embed,
            highlights=convoy_coords,
            lowlights=recipient_coords,
            map_obj=self.df_state.map_obj
        )

        map_embed.set_footer(text='Your menu is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.followup.send(embed=map_embed, file=image_file, ephemeral=True)

    @discord.ui.button(label='Dialogue', style=discord.ButtonStyle.blurple, custom_id='dialogue_button', emoji='🗣️', row=4)
    async def dialogue_button(self, interaction: discord.Interaction, button: discord.Button):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        await dialogue_menus.dialogue_menu(self.df_state, self.df_state.user_obj['user_id'], self.df_state.convoy_obj['convoy_id'])

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class JourneyButton(discord.ui.Button):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        disabled = False
        if not self.df_state.convoy_obj['journey']:  # If the convoy is not in transit
            style = discord.ButtonStyle.green
            label = 'Embark on new Journey'
            emoji = '🗺️'
        else:  # If the convoy is already on a journey
            style = discord.ButtonStyle.red
            label = 'Cancel current Journey'
            emoji = None

        if not self.df_state.convoy_obj['vehicles']:  # If the convoy has vehicle(s)
            disabled = True

        super().__init__(
            style=style,
            label=label,
            disabled=disabled,
            custom_id='journey_button',
            emoji=emoji,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        if not self.df_state.convoy_obj['journey']:  # If the convoy is not in transit
            await send_convoy_menu(self.df_state)
        else:  # If the convoy is already on a journey
            self.df_state.convoy_obj = await api_calls.cancel_journey(
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                journey_id=self.df_state.convoy_obj['journey']['journey_id']
            )
            await convoy_menu(self.df_state)

class ConvoyVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Select vehicle to inspect'
        disabled = False

        options = [
            discord.SelectOption(
                label=vehicle['name'],
                value=vehicle['vehicle_id'],
                emoji=get_vehicle_emoji(vehicle['shape'])
            )
            for vehicle in self.df_state.convoy_obj['vehicles']
        ]
        if not options:
            placeholder = 'No vehicles in convoy'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options,
            custom_id='select_vehicle',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        self.df_state.vehicle_obj = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        await discord_app.vehicle_menus.vehicle_menu(self.df_state)

class ConvoyCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=1):
        self.df_state = df_state

        placeholder = 'Select cargo to inspect'
        disabled = False
        options = []

        for vehicle in self.df_state.convoy_obj['vehicles']:
            for cargo in vehicle['cargo']:
                if (
                    not cargo['intrinsic_part_id']     # Exclude intrinsic cargo
                    and not cargo['pending_deletion']  # Exclude cargo pending deletion
                    and cargo['quantity'] > 0          # Exclude 0-quantity cargo
                ):
                    options.append(discord.SelectOption(
                        label=f'{cargo['quantity']} {cargo['name']} ({vehicle['name']})',
                        value=cargo['cargo_id'],
                        emoji=get_cargo_emoji(cargo)
                    ))
        if not options:
            placeholder = 'No cargo in convoy'
            disabled = True
            options = [discord.SelectOption(label='None', value='None')]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options[:25],
            custom_id='select_cargo',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        self.df_state.cargo_obj = next((
            c for c in self.df_state.convoy_obj['all_cargo']
            if c['cargo_id'] == self.values[0]
        ), None)

        await discord_app.cargo_menus.cargo_menu(df_state=self.df_state)


async def send_convoy_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=send_convoy_menu)  # Add this menu to the back stack

    await df_state.interaction.response.defer()

    embeds, image_file = await make_convoy_embed(df_state)

    embeds = add_tutorial_embed(embeds, df_state)

    # df_map = await api_calls.get_map()  # TODO: get this from cache somehow instead
    df_map = df_state.map_obj
    view = DestinationView(df_state=df_state, df_map=df_map)

    og_message: discord.InteractionMessage = await df_state.interaction.original_response()
    await df_state.interaction.followup.edit_message(og_message.id, embeds=embeds, view=view, attachments=[image_file])

class DestinationView(discord.ui.View):
    def __init__(self, df_state: DFState, df_map: dict, page=0):
        self.df_state = df_state
        super().__init__(timeout=600)

        add_nav_buttons(self, self.df_state)

        self.add_item(DestinationSelect(self.df_state, df_map, page))

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                item.disabled = item.custom_id not in (
                    'nav_back_button',
                    'nav_convoy_button',
                    'destination_select'
                )

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class DestinationSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, df_map, page: int):
        self.df_state = df_state
        self.df_map = df_map
        self.page = page

        convoy_x, convoy_y = self.df_state.convoy_obj['x'], self.df_state.convoy_obj['y']

        # Gather recipient vendor IDs from the convoy's cargo, mapping them to cargo names
        recipient_to_cargo_names = {}
        for cargo in self.df_state.convoy_obj['all_cargo']:
            recipient = cargo['recipient']
            if recipient:
                recipient_to_cargo_names.setdefault(recipient, []).append(cargo['name'])

        # Create a set of warehouse settlement IDs for quick lookup
        warehouse_sett_ids = [warehouse['sett_id'] for warehouse in self.df_state.user_obj['warehouses']]

        settlements = [    # Flatten settlements list from map tiles, calculate distances, and filter out same-tile settlements
            (
                sett['name'],
                sett['x'],
                sett['y'],
                math.sqrt((sett['x'] - convoy_x) ** 2 + (sett['y'] - convoy_y) ** 2),
                [  # List of cargo names
                    cargo_name for vendor in sett['vendors'] if vendor['vendor_id'] in recipient_to_cargo_names
                    for cargo_name in recipient_to_cargo_names[vendor['vendor_id']]
                ],
                '🏭' if sett['sett_id'] in warehouse_sett_ids else get_settlement_emoji(sett['sett_type'])
            )
            for row in self.df_map['tiles']
            for tile in row
            for sett in tile['settlements']
            if not (sett['x'] == convoy_x and sett['y'] == convoy_y)  # Exclude settlements on the same tile as convoy
            and 'tutorial' not in sett['name'].lower()                # Exclude settlements with "tutorial" in their name
        ]

        # Sort settlements, prioritizing cargo destinations and then by distance
        sorted_settlements = sorted(
            settlements,
            key=lambda x: (not x[4], x[3])  # Sort by presence of cargo names (True first), then by distance
        )

        # Paginate the sorted settlements
        DESTS_PER_PAGE = 23
        page_start, page_end = self.page * DESTS_PER_PAGE, (self.page + 1) * DESTS_PER_PAGE
        max_pages = (len(sorted_settlements) - 1) // DESTS_PER_PAGE

        # Create the SelectOption list with pagination controls
        options = self._create_pagination_options(sorted_settlements[page_start:page_end], self.page, max_pages)

        super().__init__(
            placeholder=f'Where to? (page {self.page + 1})',
            options=options,
            custom_id='destination_select',
        )

    def _create_pagination_options(self, settlements, current_page, max_pages):
        options = []

        if current_page > 0:  # Add 'previous page' option if not on the first page
            options.append(discord.SelectOption(label=f'Page {current_page}', value='prev_page'))

        for sett_name, x, y, _, cargo_names, emoji in settlements:
            unique_cargo_names = set(cargo_names) if cargo_names else None  # Use a set to remove duplicate cargo names
            # Label includes settlement name and unique cargo names if this is a cargo destination
            label = f'{sett_name} ({', '.join(unique_cargo_names)})' if unique_cargo_names else sett_name
            options.append(discord.SelectOption(
                label=label[:100],  # Only the first 100 chars of the label string
                value=f'{x},{y}',
                emoji=DF_LOGO_EMOJI if cargo_names else emoji  # Add the tutorial emoji if cargo destination, else use city based emoji
            ))

        if current_page < max_pages:  # Add 'next page' option if not on the last page
            options.append(discord.SelectOption(label=f'Page {current_page + 2}', value='next_page'))

        return options

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        if self.values[0] in {'prev_page', 'next_page'}:  # If the choice is a page change
            self.page += -1 if self.values[0] == 'prev_page' else 1
            view = DestinationView(df_state=self.df_state, df_map=self.df_map, page=self.page)
            await self.df_state.interaction.response.edit_message(view=view)

        else:  # If the choice is a destination
            dest_x, dest_y = map(int, self.values[0].split(','))  # Extract destination coordinates

            await route_finder(self.df_state, dest_x, dest_y, route_index=0)  # Call the route finder with the selected destination


async def route_finder(
        df_state: DFState,
        dest_x: int,
        dest_y: int,
        route_index: int,
        follow_on_embeds: list[discord.Embed] | None = None
):
    """ Find a route to the destination """
    df_state.append_menu_to_back_stack(func=route_finder, args={
        'dest_x': dest_x,
        'dest_y': dest_y,
        'route_index': route_index
    })  # Add this menu to the back stack

    if not df_state.interaction.response.is_done():
        await df_state.interaction.response.defer()

    route_choices = await api_calls.find_route(df_state.convoy_obj['convoy_id'], dest_x, dest_y)
    await route_menu(
        df_state=df_state,
        dest_x=dest_x,
        dest_y=dest_y,
        route_choices=route_choices,
        route_index=route_index,
        follow_on_embeds=follow_on_embeds
    )

async def route_menu(
        df_state: DFState,
        dest_x: int,
        dest_y: int,
        route_choices: list[dict],
        route_index: int = 0,
        follow_on_embeds: list[discord.Embed] | None = None
):
    """
    Displays the details of a potential journey route and checks for resource constraints.

    Args:
        df_state: The current state of the Discord application.
        dest_x: The x-coordinate of the destination tile.
        dest_y: The y-coordinate of the destination tile.
        route_choices: A list of possible route dictionaries calculated by the API.
        route_index: The index of the currently selected route from route_choices.
        follow_on_embeds: Optional list of embeds to append after the main convoy/route embeds.
    """
    follow_on_embeds = [] if follow_on_embeds is None else follow_on_embeds  # Initialize follow_on_embeds if None

    prospective_journey_plus_misc = route_choices[route_index]  # Get the specific route data for the selected index

    # Generate the base convoy embed and the map image file, including prospective journey details
    embeds, image_file = await make_convoy_embed(df_state, prospective_journey_plus_misc)

    convoy_embed = embeds[0]  # The first embed is the main convoy embed

    # Add a footer indicating which route is being shown out of the available choices
    convoy_embed.set_footer(text=f'Showing route [{route_index + 1} / {len(route_choices)}]')

    # --- Resource Constraint Checking ---
    # Lists to store resources that fall below critical or safety thresholds
    critical_resources = [] # Below minimum required
    safety_resources = []   # Below recommended safety margin (2x required)

    for resource in ['fuel', 'water', 'food']:  # Check standard resources constraints
        available = df_state.convoy_obj.get(resource, 0)  # Get available amount from the convoy object

        # Get required amount for the journey
        if resource == 'fuel':  # Special case for fuel, since it is a dictionary of vehicle IDs to fuel expenses
            required = sum(prospective_journey_plus_misc['fuel_expenses'].values())
        else:  # For water and food, use the respective keys directly
            required = prospective_journey_plus_misc.get(f'{resource}_expense', 0)

        required = fuzz(required)  # Fuzz the required amount

        recommended = 2 * required  # Recommended amount is double the required amount

        # Check against thresholds and append to lists if necessary
        if available < required:  # Below minimum required
            critical_resources.append((resource, available, required))
        elif available < recommended:  # Below recommended safety margin
            safety_resources.append((resource, available, recommended))

    for vehicle in df_state.convoy_obj['vehicles']:  # Check electric vehicle kWh constraints
        # Check if the vehicle is (purely) electric
        if vehicle.get('electric') and not vehicle.get('internal_combustion'):
            # Find the battery component in the vehicle's cargo
            battery = next(c for c in vehicle['cargo'] if c.get('kwh') is not None)

            available_kwh = battery.get('kwh', 0)  # Get available charge from the battery

            # Get required charge for this vehicle for the journey
            required_kwh = prospective_journey_plus_misc.get('kwh_expenses', {}).get(vehicle['vehicle_id'], 0)

            required_kwh = fuzz(required_kwh)  # Fuzz the required amount
          
            recommended_kwh = 2 * required_kwh  # Recommended charge is double the required

            resource_name = f'{vehicle['name']} (kWh)'  # Use vehicle name for clarity in warnings

            # Check against thresholds and append to lists if necessary
            if available_kwh < required_kwh:  # Below minimum required
                critical_resources.append((resource_name, available_kwh, required_kwh))
            elif available_kwh < recommended_kwh:  # Below recommended safety margin
                safety_resources.append((resource_name, available_kwh, recommended_kwh))


    # --- Generate Warning Embeds (if necessary) ---
    # Default button style and emoji (can be overridden by warnings)
    override_style = None
    override_emoji = None
    safety_margin_emoji = '⚠️'  # Emoji for safety warnings
    critical_margin_emoji = '🛑' # Emoji for critical warnings

    def _create_warning_embed(  # Helper function to create resource warning embeds
        color: discord.Color,
        title: str,
        header: str,
        subheader: str,
        threshold_type: str,
        resources_list: list[tuple[str, float, float]],
        mobile_view: bool
    ) -> discord.Embed:
        """ Creates a formatted embed for resource warnings. """
        embed = discord.Embed(color=color)
        description_lines = [title, header, subheader]

        resource_details = {  # Define resource details (name, units) for formatting
            'fuel': ('Fuel ⛽️', 'liters', 'L'),
            'water': ('Water 💧', 'liters', 'L'),
            'food': ('Food 🥪', 'meals', 'meals'),
            # Default for kWh (name is already specific, e.g., "VehicleName (kWh)")
            'default_kwh': ('🔋', 'kWh', 'kWh')
        }

        for resource, available, threshold in resources_list:  # Add details for each resource in the list
            details_key = resource if resource in resource_details else 'default_kwh'
            name, unit, short_unit = resource_details[details_key]
            # Use vehicle name directly if it's a kWh resource
            display_name = resource if details_key == 'default_kwh' else name

            if mobile_view:  # Compact format for mobile
                description_lines.append(
                    f'- {display_name}: **{available:.0f}** {short_unit}\n'
                    f'  - *{threshold_type}: {threshold:.0f}*'
                )
            else:  # Field format for desktop
                embed.add_field(
                    name=display_name,
                    value=f'**{available:.0f}** {unit}\n *{threshold_type}: {threshold:.0f}*',
                )

        embed.description = '\n'.join(description_lines)
        return embed

    if critical_resources:  # Check if there are critical resource shortages
        override_style = discord.ButtonStyle.red  # Red button style for critical issues
        override_emoji = critical_margin_emoji    # Stop emoji

        critical_embed = _create_warning_embed(  # Create the critical warning embed using the helper function
            color=discord.Color.red(),
            title=f'# {critical_margin_emoji} Critical resource shortage!',
            header=f'**{df_state.convoy_obj['name']} lacks the minimum resources needed for this journey!**',
            subheader=(
                'The convoy needs more supplies just to reach its destination.\n'
                '## Resources below minimum:'
            ),
            threshold_type='required',
            resources_list=critical_resources,
            mobile_view=get_user_metadata(df_state, 'mobile')  # Check if user prefers mobile view
        )
        follow_on_embeds.insert(0, critical_embed)

    # Check if there are safety margin shortages (only if no critical issues, or potentially show both)
    if safety_resources:
        # If no critical issues, set button style to red as a safety warning.
        if not critical_resources:
            override_style = discord.ButtonStyle.red
            override_emoji = safety_margin_emoji
        # Ensure emoji reflects the most severe warning (critical takes precedence)
        override_emoji = override_emoji or safety_margin_emoji # Use safety emoji if no critical emoji set

        safety_embed = _create_warning_embed(  # Create the safety warning embed using the helper function
            color=discord.Color.yellow(),
            title=f'# {safety_margin_emoji} Insufficient reserves for safe travel!',
            header=f'**{df_state.convoy_obj['name']} does not have enough emergency supplies for this journey!**',
            subheader=(
                'It is recommended to carry **double** the required resources.\n'
                '## Resources below recommended reserves:'
            ),
            threshold_type='recommended',
            resources_list=safety_resources,
            mobile_view=get_user_metadata(df_state, 'mobile')  # Check if user prefers mobile view
        )
        follow_on_embeds.insert(0, safety_embed)

    # --- Final Embed and View Preparation ---
    embeds.extend(follow_on_embeds)  # Add any generated warning embeds to the main list of embeds

    embeds = add_tutorial_embed(embeds, df_state)  # Add tutorial embed if applicable

    view = SendConvoyConfirmView(  # Create the confirmation view with buttons (Confirm, Next Route, Top Up)
        df_state=df_state,
        prospective_journey_plus_misc=prospective_journey_plus_misc,
        override_style=override_style, # Pass the determined button style
        override_emoji=override_emoji, # Pass the determined button emoji
        dest_x=dest_x,
        dest_y=dest_y,
        route_choices=route_choices,
        route_index=route_index
    )

    # --- Edit Message ---
    if df_state.interaction.response.is_done():  # Check if the interaction response has already been sent/deferred
        # If already responded (e.g., deferred), edit the original message via followup
        og_message = await df_state.interaction.original_response()
        await df_state.interaction.followup.edit_message(
            og_message.id,
            embeds=embeds,
            view=view,
            attachments=[image_file] # Include the map image file
        )
    else:  # If not responded yet, edit the initial deferred response
        await df_state.interaction.response.edit_message(
            embeds=embeds,
            view=view,
            attachments=[image_file] # Include the map image file
        )

class SendConvoyConfirmView(discord.ui.View):
    """ Confirm button before sending convoy somewhere """
    def __init__(
            self,
            df_state: DFState,
            dest_x: int,
            dest_y: int,
            route_choices: list,
            prospective_journey_plus_misc: dict,
            override_style: discord.ButtonStyle | None = None,
            override_emoji: str | None = None,
            route_index: int = 0
    ):
        self.df_state = df_state
        self.prospective_journey_plus_misc = prospective_journey_plus_misc
        self.route_choices = route_choices
        self.route_index = route_index

        super().__init__(timeout=600)

        add_nav_buttons(self, self.df_state)

        if len(route_choices) > 1:
            self.add_item(NextJourneyButton(
                df_state=self.df_state,
                dest_x=dest_x,
                dest_y=dest_y,
                routes=route_choices,
                index=self.route_index
            ))
        self.add_item(ConfirmJourneyButton(
            df_state=df_state,
            prospective_journey_plus_misc=self.prospective_journey_plus_misc,
            override_style=override_style,
            override_emoji=override_emoji
        ))
        self.add_item(discord_app.vendor_views.buy_menus.TopUpButton(
            df_state=self.df_state,
            menu=route_finder,
            menu_args={
                'dest_x': dest_x,
                'dest_y': dest_y,
                'route_index': self.route_index
            },
            row=2
        ))

        tutorial_stage = get_user_metadata(self.df_state, 'tutorial')  # TUTORIAL BUTTON DISABLING
        if tutorial_stage in {1, 2, 3, 4, 5}:  # Only proceed if tutorial stage is in a relevant set of stages (1 through 5)
            for item in self.children:
                if item.custom_id not in {'alt_route', 'confirm_journey_button'}:
                    item.disabled = item.custom_id not in (
                        'nav_back_button',
                        'nav_convoy_button'
                    )

class NextJourneyButton(discord.ui.Button):
    """ Loads alternative journey """
    def __init__(self, df_state: DFState, dest_x: int, dest_y: int, routes: list, index: int, row: int=1):
        self.df_state = df_state
        self.dest_x = dest_x
        self.dest_y = dest_y
        self.routes = routes
        self.index = index

        super().__init__(
            label='Show Next Route',
            custom_id='alt_route',
            style=discord.ButtonStyle.blurple,
            emoji='🗺️',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        await self.df_state.interaction.response.defer()

        self.index += 1  # ensures that route index will route
        self.index = self.index % len(self.routes)

        await route_menu(self.df_state, self.dest_x, self.dest_y, self.routes, self.index)

class ConfirmJourneyButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            prospective_journey_plus_misc: dict,
            override_style: discord.ButtonStyle | None = None,
            override_emoji: str | None = None,
            row: int = 1
    ):
        self.df_state = df_state
        self.prospective_journey_plus_misc = prospective_journey_plus_misc

        style = override_style or discord.ButtonStyle.green
        emoji = override_emoji or '🛣️'

        if emoji == '🛑':  # XXX: REMOVE ME WHEN YOU CAN SEND CONVOYS TO THEIR DEATHS
            disabled = True
        else:
            disabled = False

        super().__init__(
            style=style,
            label='Embark upon Journey',
            disabled=disabled,
            custom_id='confirm_journey_button',
            emoji=emoji,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.send_convoy(
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                journey_id=self.prospective_journey_plus_misc['journey']['journey_id']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        
        await convoy_menu(self.df_state)

    async def on_timeout(self):
        await handle_timeout(self.df_state)
