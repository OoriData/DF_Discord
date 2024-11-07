# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap
import                                math

import                                discord
import                                logging

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, vehicle_views, cargo_views, dialogue_menus, discord_timestamp, df_embed_author
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


async def convoy_menu(df_state: DFState, edit: bool=True):
    await df_state.interaction.response.defer()
    # TODO: call an embed with the ConvoySelect if the df_state doesn't have a convoy_obj

    embed, image_file = await make_convoy_embed(df_state)

    view = ConvoyView(df_state)

    og_message: discord.InteractionMessage = await df_state.interaction.original_response()
    await df_state.interaction.followup.edit_message(og_message.id, embed=embed, view=view, attachments=[image_file])
    # await df_state.interaction.followup.send(embed=embed, view=view, files=[image_file])
    # await df_state.interaction.response.edit_message(embed=embed, view=view, attachments=[image_file])
    # if edit:
    #     await df_state.interaction.response.edit_message(embed=embed, view=view, attachments=[image_file])
    #     # await asyncio.sleep(5)
    #     # print(df_state.interaction.message.attachments[0].proxy_url)
    # else:
    #     await df_state.interaction.followup.send(embed=embed, view=view, files=[image_file])


async def make_convoy_embed(df_state: DFState, prospective_journey_plus_misc=None) -> list[discord.Embed, discord.File]:
    convoy_embed = discord.Embed(color=discord.Color.green())
    convoy_embed = df_embed_author(convoy_embed, df_state)

    convoy_embed.description = vehicles_embed_str(df_state.convoy_obj['vehicles'])

    convoy_embed.add_field(name='Fuel ⛽️', value=f'**{df_state.convoy_obj['fuel']:.2f}**\n/{df_state.convoy_obj['max_fuel']:.2f} liters')
    convoy_embed.add_field(name='Water 💧', value=f'**{df_state.convoy_obj['water']:.2f}**\n/{df_state.convoy_obj['max_water']:.2f} liters')
    convoy_embed.add_field(name='Food 🥪', value=f'**{df_state.convoy_obj['food']:.2f}**\n/{df_state.convoy_obj['max_food']:.2f} meals')

    convoy_embed.add_field(name='Fuel Efficiency', value=f'**{df_state.convoy_obj['fuel_efficiency']:.0f}**\n/100')
    convoy_embed.add_field(name='Top Speed', value=f'**{df_state.convoy_obj['top_speed']:.0f}**\n/100')
    convoy_embed.add_field(name='Offroad Capability', value=f'**{df_state.convoy_obj['offroad_capability']:.0f}**\n/100')

    convoy_x = df_state.convoy_obj['x']
    convoy_y = df_state.convoy_obj['y']

    if df_state.convoy_obj['journey']:  # If the convoy is in transit
        journey = df_state.convoy_obj['journey']
        route_tiles = []  # a list of tuples
        pos = 0  # bad way to do it but i'll fix later
        for x in journey['route_x']:
            y = journey['route_y'][pos]
            route_tiles.append((x, y))
            pos += 1

        destination = await api_calls.get_tile(journey['dest_x'], journey['dest_y'])
        convoy_embed.add_field(name='Destination 📍', value=f'**{destination['settlements'][0]['name']}**\n({journey['dest_x']}, {journey['dest_y']})')  # XXX: replace coords with `\n{territory_name}`

        eta = df_state.convoy_obj['journey']['eta']
        convoy_embed.add_field(name='ETA ⏰', value=f'**{discord_timestamp(eta, 'R')}**\n{discord_timestamp(eta, 't')}')

        progress_percent = ((df_state.convoy_obj['journey']['progress']) / len(df_state.convoy_obj['journey']['route_x'])) * 100
        progress_in_km = df_state.convoy_obj['journey']['progress'] * 50  # progress is measured in tiles; tiles are 50km to a side
        progress_in_miles = df_state.convoy_obj['journey']['progress'] * 30  # progress is measured in tiles; tiles are 50km to a side
        convoy_embed.add_field(name='Progress 🚗', value=f'**{progress_percent:.0f}%**\n{progress_in_km:.0f} km ({progress_in_miles:.0f} miles)')

        convoy_embed, image_file = await add_map_to_embed(
            embed=convoy_embed,
            highlighted=[(convoy_x, convoy_y)],
            lowlighted=route_tiles,
        )

    elif prospective_journey_plus_misc:  # If a journey is being considered
        route_tiles = []  # a list of tuples
        pos = 0  # bad way to do it but i'll fix later
        for x in prospective_journey_plus_misc['journey']['route_x']:
            y = prospective_journey_plus_misc['journey']['route_y'][pos]
            route_tiles.append((x, y))
            pos += 1

        destination = await api_calls.get_tile(prospective_journey_plus_misc['journey']['dest_x'], prospective_journey_plus_misc['journey']['dest_y'])

        convoy_embed.add_field(name='Fuel expense', value=f'**{prospective_journey_plus_misc['fuel_expense']:.2f}**')
        convoy_embed.add_field(name='Water expense', value=f'**{prospective_journey_plus_misc['water_expense']:.2f}**')
        convoy_embed.add_field(name='Food expense', value=f'**{prospective_journey_plus_misc['food_expense']:.2f}**')

        convoy_embed.add_field(name='Destination 📍', value=f'**{destination['settlements'][0]['name']}**\n({prospective_journey_plus_misc['journey']['dest_x']}, {prospective_journey_plus_misc['journey']['dest_y']})')  # XXX: replace coords with `\n{territory_name}`
        
        delta_t = discord_timestamp(datetime.now(timezone.utc) + timedelta(minutes=prospective_journey_plus_misc['delta_t']), 'R')
        eta_discord_time = discord_timestamp(datetime.now(timezone.utc) + timedelta(minutes=prospective_journey_plus_misc['delta_t']), 't')
        convoy_embed.add_field(name='ETA ⏰', value=f'**{delta_t}**\n{eta_discord_time}')

        distance_km = 50 * len(prospective_journey_plus_misc['journey']['route_x'])
        distance_miles = 30 * len(prospective_journey_plus_misc['journey']['route_x'])
        convoy_embed.add_field(name='Distance 🗺️', value=f'**{distance_km} km**\n{distance_miles} miles')

        convoy_embed, image_file = await add_map_to_embed(
            embed=convoy_embed,
            highlighted=[(convoy_x, convoy_y)],
            lowlighted=route_tiles,
        )

    else:  # If the convoy is just chilling somewhere
        convoy_embed, image_file = await add_map_to_embed(
            embed=convoy_embed,
            highlighted=[(convoy_x, convoy_y)],
        )

    return convoy_embed, image_file


def vehicles_embed_str(vehicles: list[dict], detailed: Optional[bool] = False) -> str:
    vehicles_list = []
    vehicles_str = '### Vehicles:\n'
    if vehicles:
        for vehicle in vehicles:
            vehicle_str = f'- **{vehicle['name']}**\n'
            if detailed:
                vehicle_str += f'  - AP: **{vehicle['ap']}** / {vehicle['max_ap']}\n'
                vehicle_str += f'  - Fuel Efficiency: **{vehicle['fuel_efficiency']}** / 100\n'
                vehicle_str += f'  - Top Speed: **{vehicle['top_speed']}** / 100\n'
                vehicle_str += f'  - Offroad Capability: **{vehicle['offroad_capability']}** / 100\n'
            
            vehicle_str += f'  - Cargo load: **{vehicle['total_cargo_volume']}** / {vehicle['cargo_capacity']} liters & **{vehicle['total_cargo_weight']}** / {vehicle['weight_capacity']} kg'
            vehicles_list.append(vehicle_str)

        vehicles_str += '\n'.join(vehicles_list)

    else:
        vehicles_str = '*No vehicles in convoy. Buy one at the dealership.*'

    return vehicles_str


class ConvoyView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(
            self,
            df_state: DFState
    ):
        self.df_state = df_state
        super().__init__()

        add_nav_buttons(self, df_state)

        self.add_item(vehicle_views.VehicleSelect(df_state=self.df_state, row=2))
        self.add_item(cargo_views.ConvoyCargoSelect(df_state=self.df_state, row=3))
        
        if not self.df_state.convoy_obj['vehicles']:  # If the convoy has vehicle(s)
            self.send_convoy_button.disabled = True

        if self.df_state.convoy_obj['journey']:  # If the convoy is already on a journey
            self.send_convoy_button.disabled = True

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

    @discord.ui.button(label='Embark on new Journey', style=discord.ButtonStyle.green, custom_id='send_convoy_button', row=1)
    async def send_convoy_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction
        await send_convoy_menu(self.df_state)

    @discord.ui.button(label='Dialogue', style=discord.ButtonStyle.blurple, custom_id='dialogue_button', row=1)
    async def dialogue_button(self, interaction: discord.Interaction, button: discord.Button):
        self.df_state.interaction = interaction
        await dialogue_menus.dialogue_menu(self.df_state, self.df_state.user_obj['user_id'], self.df_state.convoy_obj['convoy_id'])

    @discord.ui.button(label='All Cargo Destinations', style=discord.ButtonStyle.blurple, custom_id='all_cargo_destinations_button', row=4)
    async def all_cargo_destinations_button(self, interaction: discord.Interaction, button: discord.Button):
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
            highlighted=convoy_coords,
            lowlighted=recipient_coords
        )
        
        map_embed.set_footer(text='Your menu is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.followup.send(embed=map_embed, file=image_file, ephemeral=True)

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()


async def send_convoy_menu(df_state: DFState):
    await df_state.interaction.response.defer()

    embed, image_file = await make_convoy_embed(df_state)

    df_map = await api_calls.get_map()  # TODO: get this from cache somehow instead
    view = DestinationView(df_state=df_state, df_map=df_map)

    og_message: discord.InteractionMessage = await df_state.interaction.original_response()
    await df_state.interaction.followup.edit_message(og_message.id, embed=embed, view=view, attachments=[image_file])


class DestinationView(discord.ui.View):
    def __init__(self, df_state: DFState, df_map: dict, page=0):
        self.df_state = df_state
        super().__init__()

        add_nav_buttons(self, self.df_state)

        self.add_item(DestinationSelect(self.df_state, df_map, page))

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()


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
        
        settlements = [    # Flatten settlements list from map tiles, calculate distances, and filter out same-tile settlements
            (
                sett['name'],
                sett['x'],
                sett['y'],
                math.sqrt((sett['x'] - convoy_x) ** 2 + (sett['y'] - convoy_y) ** 2),
                [cargo_name for vendor in sett['vendors'] if vendor['vendor_id'] in recipient_to_cargo_names
                 for cargo_name in recipient_to_cargo_names[vendor['vendor_id']]]  # List of cargo names
            )
            for row in self.df_map['tiles']
            for tile in row
            for sett in tile['settlements']
            if not (sett['x'] == convoy_x and sett['y'] == convoy_y)  # Exclude settlements on the same tile as convoy
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
        options = self._create_pagination_options(sorted_settlements[page_start:page_end], page, max_pages)
        
        super().__init__(
            placeholder='Where to?',
            options=options,
            custom_id='destination_select',
        )

    def _create_pagination_options(self, settlements, current_page, max_pages):
        options = []
        
        if current_page > 0:  # Add 'previous page' option if not on the first page
            options.append(discord.SelectOption(label=f'Page {current_page}', value='prev_page'))
        
        for sett_name, x, y, _, cargo_names in settlements:
            # Label includes settlement name and cargo names if this is a cargo destination
            label = f'{sett_name} ({', '.join(cargo_names)})' if cargo_names else sett_name
            options.append(discord.SelectOption(label=label, value=f'{x},{y}'))
        
        if current_page < max_pages:  # Add 'next page' option if not on the last page
            options.append(discord.SelectOption(label=f'Page {current_page + 2}', value='next_page'))

        return options

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await self.df_state.interaction.response.defer()
        
        if self.values[0] in {'prev_page', 'next_page'}:  # If the choice is a page change
            self.page += -1 if self.values[0] == 'prev_page' else 1
            view = DestinationView(df_state=self.df_state, df_map=self.df_map, page=self.page)
            og_message = await self.df_state.interaction.original_response()
            await self.df_state.interaction.followup.edit_message(og_message.id, view=view)
        
        else:  # If the choice is a destination
            dest_x, dest_y = map(int, self.values[0].split(','))  # Extract destination coordinates

            route_choices = await api_calls.find_route(self.df_state.convoy_obj['convoy_id'], dest_x, dest_y)
            await route_menu(self.df_state, route_choices)


async def route_menu(df_state: DFState, route_choices):
    prospective_journey_plus_misc = route_choices[0]  # TODO: handle multiple routes

    embed, image_file = await make_convoy_embed(df_state, prospective_journey_plus_misc)

    view = SendConvoyConfirmView(
        df_state=df_state,
        prospective_journey_plus_misc=prospective_journey_plus_misc
    )

    og_message: discord.InteractionMessage = await df_state.interaction.original_response()
    await df_state.interaction.followup.edit_message(og_message.id, embed=embed, view=view, attachments=[image_file])


class SendConvoyConfirmView(discord.ui.View):
    '''Confirm button before sending convoy somewhere'''
    def __init__(
            self,
            df_state: DFState,
            prospective_journey_plus_misc: dict
    ):
        self.df_state = df_state
        self.prospective_journey_plus_misc = prospective_journey_plus_misc
        
        super().__init__(timeout=120)

        add_nav_buttons(self, self.df_state)

        self.add_item(ConfirmJourneyButton(df_state, self.prospective_journey_plus_misc))

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.blurple, custom_id='cancel_send', row=1)
    async def cancel_journey_button(self, interaction: discord.Interaction, button: discord.Button):
        # TODO: Make it so that when you press the cancel button it gives you some sort of feedback rather than just deleting the whole thing
        await convoy_menu(self.df_state)


class ConfirmJourneyButton(discord.ui.Button):
    def __init__(self, df_state: DFState, prospective_journey_plus_misc: dict, row: int=1):
        self.df_state = df_state
        self.prospective_journey_plus_misc = prospective_journey_plus_misc
        
        label = 'Embark upon Journey'
        disabled = False

        resource_constraints = []
        for resource in ['fuel', 'water', 'food']:
            if self.df_state.convoy_obj[resource] < self.prospective_journey_plus_misc[f'{resource}_expense']:
                resource_constraints.append(resource)
        
        if resource_constraints:
            label = f'Not enough {', '.join(resource_constraints)}'
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.green,
            label=label,
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
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
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()


class CargoView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(
            self,
            interaction: discord.Interaction,
            convoy_dict: dict,
    ):
        super().__init__(timeout=120)

        self.interaction = interaction
        self.convoy_dict = convoy_dict
        self.position = 0

    @discord.ui.button(label='◀', style=discord.ButtonStyle.blurple, custom_id='back')
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cargo_menu = self.convoy_dict['all_cargo']
        self.position = (self.position - 1) % len(cargo_menu)
        await self.update_menu(interaction, cargo_menu=cargo_menu)

    @discord.ui.button(label='▶', style=discord.ButtonStyle.blurple, custom_id='next')
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cargo_menu = self.convoy_dict['all_cargo']
        self.position = (self.position + 1) % len(cargo_menu)
        await self.update_menu(interaction, cargo_menu=cargo_menu)

    async def update_menu(self, interaction: discord.Interaction, cargo_menu: dict):
        index = self.position
        cargo_item = cargo_menu[index]
        if cargo_item['recipient']:  # API call to get recipient's vendor info
            recipient_info = await api_calls.get_vendor(vendor_id=cargo_item['recipient'])
                
            recipient = recipient_info
            # print(ansi_color(recipient, 'purple'))
            delivery_reward = cargo_item['delivery_reward']

            self.mapbutton = MapButton(convoy_info=self.convoy_dict, recipient_info=recipient, label = 'Map (Recipient)', style=discord.ButtonStyle.green, custom_id='map_button')
            self.add_item(self.mapbutton)
            
            cargo_vehicle_dict = await api_calls.get_vehicle(vehicle_id=cargo_item['vehicle_id'])

            embed = discord.Embed(
                title = cargo_menu[index]['name'],
                description=textwrap.dedent(f'''\
                    *{cargo_item['base_desc']}*

                    - Base (sell) Price: **${cargo_item['base_price']}**
                    - Recipient: **{recipient['name']}**
                    - Delivery Reward: **{delivery_reward}**
                    - Carrier Vehicle: **{cargo_vehicle_dict['name']}**
                    - Cargo quantity: **{cargo_item['quantity']}**
                ''')
            )

        else:  # No recipient, no worries
            recipient = 'None'
            delivery_reward = 'None'
            try:
                if self.mapbutton:
                    self.remove_item(self.mapbutton)
            except AttributeError as e:
                msg = 'MapButton is not in CargoView; skipping...'
                logger.debug(msg=msg)
                pass

            cargo_vehicle_dict = await api_calls.get_vehicle(vehicle_id=cargo_item['vehicle_id'])
            
            embed = discord.Embed(
                title = cargo_menu[index]['name'],
                description=textwrap.dedent(f'''\
                    *{cargo_item['base_desc']}*

                    - Base (sell) Price: **${cargo_item['base_price']}**
                    - Carrier Vehicle: **{cargo_vehicle_dict['name']}**
                    - Cargo quantity: **{cargo_item['quantity']}**
                ''')
            )

        convoy_balance = f'{self.convoy_dict['money']:,}'
        embed.set_author(
            name=f'{self.convoy_dict['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        embed.set_footer(text=f'Page [{index + 1} / {len(cargo_menu)}]')
        self.current_embed = embed
        await interaction.response.edit_message(embed=embed, view=self, attachments=[])

    async def on_timeout(self):
        timed_out_button = discord.ui.Button(
            label='Interaction timed out!',
            style=discord.ButtonStyle.gray,
            disabled=True
        )

        self.clear_items()
        self.add_item(timed_out_button)

        await self.df_state.interaction.edit_original_response(view=self)
        return await super().on_timeout()

    
class MapButton(discord.ui.Button):
    def __init__(self, convoy_info: dict, recipient_info: dict, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.convoy_info = convoy_info
        self.recipient_info = recipient_info
    
    async def callback(self, interaction: discord.Interaction):

        convoy_x = self.convoy_info['x']
        convoy_y = self.convoy_info['y']

        recipient_x = self.recipient_info['x']
        recipient_y = self.recipient_info['y']

        embed = discord.Embed(
            title=f'Map relative to {self.convoy_info['name']}',
            description=textwrap.dedent('''
                🟨 - Your convoy's location
                🟦 - Recipient vendor's location
            ''')
        )

        map_embed, image_file = await add_map_to_embed(
            embed=embed,
            highlighted=[(convoy_x, convoy_y)],
            lowlighted=[(recipient_x, recipient_y)],
        )

        map_embed.set_footer(text='Your menu is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.response.defer()
        await interaction.followup.send(
            embed=map_embed,
            file=image_file,
            ephemeral=True
        )


class ConvoySelect(discord.ui.Select):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        options = [
            discord.SelectOption(label=convoy['name'], value=convoy['convoy_id'])
            for convoy in df_state.user_obj['convoys']
        ]
        
        super().__init__(
            placeholder='Which convoy?',
            options=options,
            custom_id='select_convoy',
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.convoy_obj = next((
            c for c in self.df_state.user_obj['convoys']
            if c['convoy_id'] == self.values[0]
        ), None)

        await convoy_menu(self.df_state)
