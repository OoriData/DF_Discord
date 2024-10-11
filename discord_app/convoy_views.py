# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional
import                                textwrap

import                                discord
import                                httpx
import                                logging

from discord_app               import api_calls, discord_timestamp
from discord_app.vehicle_views import VehicleView, VehicleSelect
from discord_app.cargo_views   import CargoView, CargoSelect
from discord_app.map_rendering import add_map_to_embed
from utiloori.ansi_color       import ansi_color

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

logger = logging.getLogger('DF_Discord')
logging.basicConfig(format='%(levelname)s:%(name)s: %(message)s', level=LOG_LEVEL)


async def make_convoy_embed(interaction, convoy_obj, prospective_journey_plus_misc=None) -> discord.Embed:
    convoy_embed = discord.Embed(
        color=discord.Color.green(),
        title=f'{convoy_obj['name']} Information'
    )
    
    convoy_embed.description = vehicles_embed_str(convoy_obj['vehicles'])

    convoy_embed.set_author(
        name=f'{convoy_obj['name']} | ${convoy_obj['money']:,}',
        icon_url=interaction.user.avatar.url
    )

    convoy_embed.add_field(name='Fuel ⛽️', value=f'**{convoy_obj['fuel']:.2f}**\n/{convoy_obj['max_fuel']:.2f} liters')
    convoy_embed.add_field(name='Water 💧', value=f'**{convoy_obj['water']:.2f}**\n/{convoy_obj['max_water']:.2f} liters')
    convoy_embed.add_field(name='Food 🥪', value=f'**{convoy_obj['food']:.2f}**\n/{convoy_obj['max_food']:.2f} meals')

    convoy_embed.add_field(name='Fuel Efficiency', value=f'**{convoy_obj['fuel_efficiency']:.0f}**\n/100')
    convoy_embed.add_field(name='Top Speed', value=f'**{convoy_obj['top_speed']:.0f}**\n/100')
    convoy_embed.add_field(name='Offroad Capability', value=f'**{convoy_obj['offroad_capability']:.0f}**\n/100')

    convoy_x = convoy_obj['x']
    convoy_y = convoy_obj['y']

    if convoy_obj['journey']:  # If the convoy is in transit
        journey = convoy_obj['journey']
        route_tiles = []  # a list of tuples
        pos = 0  # bad way to do it but i'll fix later
        for x in journey['route_x']:
            y = journey['route_y'][pos]
            route_tiles.append((x, y))
            pos += 1

        destination = await api_calls.get_tile(journey['dest_x'], journey['dest_y'])
        convoy_embed.add_field(name='Destination 📍', value=f'**{destination['settlements'][0]['name']}**\n({journey['dest_x']}, {journey['dest_y']})')  # XXX: replace coords with `\n{territory_name}`

        eta = convoy_obj['journey']['eta']
        convoy_embed.add_field(name='ETA ⏰', value=f'**{discord_timestamp(eta, 'R')}**\n{discord_timestamp(eta, 't')}')

        progress_percent = ((convoy_obj['journey']['progress']) / len(convoy_obj['journey']['route_x'])) * 100
        progress_in_km = convoy_obj['journey']['progress'] * 50  # progress is measured in tiles; tiles are 50km to a side
        progress_in_miles = convoy_obj['journey']['progress'] * 30  # progress is measured in tiles; tiles are 50km to a side
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
        vehicles_str = '*No vehicles in convoy. Buy one by using /vendors and navigating one of your city\'s dealerships.*'

    return vehicles_str


class SendConvoyConfirmView(discord.ui.View):
    '''Confirm button before sending convoy somewhere'''
    def __init__(
            self,
            interaction: discord.Interaction,
            convoy_dict: dict,
            prospective_journey_dict: dict
    ):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.convoy_dict = convoy_dict
        self.prospective_journey_dict = prospective_journey_dict

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red, custom_id='cancel_send')
    async def cancel_journey_button(self, interaction: discord.Interaction, button: discord.Button):
        # TODO: Make it so that when you press the cancel button it gives you some sort of feedback rather than just deleting the whole thing
        await interaction.response.edit_message(content='Canceled!', delete_after=5, embed=None, view=None)

    @discord.ui.button(label='Confirm Journey', style=discord.ButtonStyle.green, custom_id='confirm_send')
    async def confirm_journey_button(self, interaction: discord.Interaction, button: discord.Button):
        try:
            confirmed_journey_dict = await api_calls.send_convoy(self.convoy_dict['convoy_id'], self.prospective_journey_dict['journey_id'])
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        await interaction.response.send_message('Look at them gooooooo :D\n(call `/df-convoy` to see their progress)')  # TODO: send more information than just 'look at them go'


class ConvoyView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(
            self,
            interaction: discord.Interaction,
            convoy_dict: dict,
            previous_embed: discord.Embed,
            previous_attachments: list[discord.Attachment] = None
    ):
        super().__init__(timeout=120)  # TODO: Add view timeout as a configurable option

        self.interaction = interaction
        self.convoy_dict = convoy_dict

        self.add_item(VehicleSelect(
            convoy_obj=convoy_dict,
            previous_embed=previous_embed,
            previous_view=self,
            previous_attachments=previous_attachments
        ))

        self.add_item(CargoSelect(
            convoy_obj=convoy_dict,
            previous_embed=previous_embed,
            previous_view=self,
            previous_attachments=previous_attachments
        ))

    @discord.ui.button(label='All Cargo Destinations', style=discord.ButtonStyle.blurple, custom_id='all_cargo_destinations', row=1)
    async def all_cargo_destinations(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()
        user_cargo = self.convoy_dict['all_cargo']
        recipients = []
        # Get all cargo recipient locations and put em in a tuple with the name of the cargo
        for cargo in user_cargo:
            if cargo['recipient']:
                cargo_tuple = (cargo['recipient'], cargo['name'])
                if cargo_tuple not in recipients:
                    # add vendor id and cargo name as a tuple
                    recipients.append(cargo_tuple)

        # For each vendor ID found in the cargo tuple, get vendor's location and add it to destinations
        destinations = []
        recipient_coords = []
        for cargo_tuple in recipients:
            vendor = await api_calls.get_vendor(cargo_tuple[0])
            destination = await api_calls.get_tile(vendor['x'], vendor['y'])

            # Grab destination name to display to user
            dest_name = destination['settlements'][0]['name']
            destinations.append(f'- **{dest_name}** ({cargo_tuple[1]})')
            # And recipient_coords for map rendering
            dest_coords = (destination['settlements'][0]['x'], destination['settlements'][0]['y'])
            recipient_coords.append(dest_coords)
        
        dest_string = '\n'.join(destinations)

        convoy_x = self.convoy_dict['x']
        convoy_y = self.convoy_dict['y']
        convoy_coords = [(convoy_x, convoy_y)]

        dest_embed = discord.Embed(
            title=f'All cargo destinations in {self.convoy_dict['name']}',
            description=dest_string
        )

        map_embed, image_file = await add_map_to_embed(
            embed=dest_embed,
            lowlighted=convoy_coords,
            highlighted=recipient_coords,
        )
        
        map_embed.set_footer(text='Your vendor interaction is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.followup.send(embed=map_embed, file=image_file, ephemeral=True)


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
            print(ansi_color(recipient, 'purple'))
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

        map_embed.set_footer(text='Your vendor interaction is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.response.defer()
        await interaction.followup.send(
            embed=map_embed,
            file=image_file,
            ephemeral=True
        )
