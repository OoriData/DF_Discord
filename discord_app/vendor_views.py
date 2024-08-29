# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls
from discord_app.map_rendering import add_map_to_embed

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')

# TODO: send message if user tries to iterate through menu with a length of zero
# TODO: Add universal BackButtonView that just allows users to go back to the main vendor menu after they complete a transaction

def vendor_services(vendor: dict):
    service_keys = {
        'fuel': 'Fuel Refilling',
        'water': 'Drinking Water',
        'food': 'Food',
        'cargo_inventory': 'Surplus Items',
        'vehicle_inventory': 'Vehicles',
        'repair_price': 'Mechanical Repairs'
    }
    # XXX stop being lazy! list comprehension this
    services = []
    for key in list(service_keys.keys()):
        if vendor[key]:
            services.append((service_keys[key], '✅ **Available!**'))

    return services

def vendor_resources(vendor: dict):
    ''' Quickly get which resources a vendor sells/buys '''
    resources = []
    if vendor['fuel']:
        resources.append('fuel')
    elif vendor['water']:
        resources.append('water')
    elif vendor['food']:
        resources.append('food')
    
    return resources

class BackButtonView(discord.ui.View):
    ''' A menu for a button that sends users back to the previous view. '''
    def __init__(
            self,
            interaction: discord.Interaction,
            previous_embed: discord.Embed,
            previous_view: discord.ui.View
    ):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.previous_embed = previous_embed
        self.previous_view = previous_view

    @discord.ui.button(label='Back to Vendors', style=discord.ButtonStyle.green, custom_id='back_button')
    async def back_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()

        try:
            user_info = await api_calls.get_user_by_discord(
                discord_id=interaction.user.id
            )

            tile_info = await api_calls.get_tile(
                x=user_info['convoys'][0]['x'],
                y=user_info['convoys'][0]['y']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        # TODO: handle multiple settlements eventually
        # wtf does this mean
        if not tile_info['settlements']:
            await interaction.response.send_message(content='There aint no settle ments here dawg!!!!!', ephemeral=True, delete_after=10)
            return

        node_embed = discord.Embed(
            title=f'{tile_info['settlements'][0]['name']} vendors and services',
        )
        for vendor in tile_info['settlements'][0]['vendors']:
            node_embed.add_field(
                name=vendor['name'],
                value=f'${vendor['money']}'
            )
        convoy_balance = f'{user_info['convoys'][0]['money']:,}'
        node_embed.set_author(name=f'{user_info['convoys'][0]['name']} | ${convoy_balance}', icon_url=interaction.user.avatar.url)

        view=VendorMenuView(
            interaction=interaction,
            user_info=user_info,
            menu=tile_info['settlements'][0]['vendors'],
            menu_type='vendor'
        )
        await interaction.followup.send(embed=node_embed, view=view)
        # await interaction.response.edit_message(view=self.previous_view, embed=self.previous_embed)

class VendorMenuView(discord.ui.View):
    '''
    Main view for selecting and viewing vendors. 
    
    - Appears when `/vendors` command is called on the Discord frontend.
    
    - Depending on whether user is buying or selling, directs to either SellSelectView or BuyView
    '''
    def __init__(
            self,
            interaction: discord.Interaction,
            user_info: dict,  # dictionary object containing user's overall info
            menu: list,  # can either be a list of a node's vendors, a list of a vendor's vehicle or cargo inventory, etc
            menu_type: str,  # Which type of menu is being displayed ('vendor', 'vehicle', 'cargo', 'resource')
    ):
        super().__init__(timeout=120)
        self.position = -1
        self.interaction = interaction
        self.user_info = user_info
        self.menu = menu
        self.menu_type = menu_type
        self.user_info = user_info

        self.current_embed = None
    
    # menu_types = ['vendor', 'vehicle', 'cargo', 'food', 'resource']

    @discord.ui.button(label='◀', style=discord.ButtonStyle.blurple, custom_id='back')
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        '''Simple button to bring user back and forth between the menu list'''
        self.position = (self.position - 1) % len(self.menu)
        await self.update_menu(interaction)

    # Renaming this to 'buy' instead
    @discord.ui.button(label='Buy', style=discord.ButtonStyle.green, custom_id='buy')  # TODO: Create an actual 'trade' button which diverges into a sell and buy button
    async def buy_button(self, interaction: discord.Interaction, button: discord.Button):
        if self.current_embed is None:
            await interaction.response.send_message('Select a vendor to buy from', ephemeral=True, delete_after=10)
            return
        
        convoy_balance = f'{self.user_info['convoys'][0]['money']:,}'
        index = self.position
        current_vendor = self.menu[index]  # set variable for menu user is currently interacting with
        if current_vendor['cargo_inventory']:  # if the vendor has a cargo inventory
            menu_type = 'cargo'
            # display cargo available for purchase in current vendor's inventory
            cargo_list = []
            for cargo in current_vendor['cargo_inventory']:  # could maaaaaaybe list comprehension this, not super important
                cargo_str = f'- {cargo['name']} - ${cargo['base_price']}'
                cargo_list.append(cargo_str)
            displayable_cargo = '\n'.join(cargo_list)

            menu_embed = discord.Embed(
                title=current_vendor['name'],
                description=textwrap.dedent(f'''\
                    Available for Purchase:
                    {displayable_cargo}
                    
                    **Use the arrows to select the item you want to buy**'
                ''')
            )
            convoy_balance = f'{self.user_info['convoys'][0]['money']:,}'
            menu_embed.set_author(
                name=f'{self.user_info['convoys'][0]['name']} | ${convoy_balance}',
                icon_url=interaction.user.avatar.url
            )
            view = BuyView(
                interaction=interaction,
                user_info=self.user_info,
                menu=current_vendor['cargo_inventory'],
                menu_type=menu_type,
                vendor_obj=current_vendor,
                previous_menu=self,
                previous_embed=self.current_embed
                )
        elif current_vendor['vehicle_inventory']:
            # XXX: there's gotta be a way to reuse the code from the cargo embed stuff
            menu_type = 'vehicle'
            vehicle_list = []
            for vehicle in current_vendor['vehicle_inventory']:
                vehicle_str = f'- {vehicle['name']} - ${vehicle['value']}'
                vehicle_list.append(vehicle_str)
            displayable_vehicles = '\n'.join(vehicle_list)

            menu_embed = discord.Embed(
                title=current_vendor['name'],
                description=textwrap.dedent(f'''\
                    Available for Purchase:
                    {displayable_vehicles}
                ''')
            )
            menu_embed.set_author(
                name=f'{self.user_info['convoys'][0]['name']} | ${convoy_balance}',
                icon_url=interaction.user.avatar.url
            )
            view = BuyView(
                interaction=interaction,
                user_info=self.user_info,
                menu=current_vendor['vehicle_inventory'],
                menu_type=menu_type,
                vendor_obj=current_vendor,
                previous_menu=self,
                previous_embed=self.current_embed
            )
        else:  # weird case, means there is no cargo or vehicles at the vendor.
            menu_type = 'resource'
            menu_embed = discord.Embed(
                title=current_vendor['name'],
                description=('Vendor low on stock. Resources may be available here, but try coming back later.')
            )
            menu_embed.set_author(
                name=f'{self.user_info['convoys'][0]['name']} | ${convoy_balance}',
                icon_url=interaction.user.avatar.url
            )
            await interaction.response.edit_message(
                embed=menu_embed,
                view=BuyView(
                    interaction=interaction,
                    user_info=self.user_info,
                    menu=[],  # XXX: sorry
                    menu_type=menu_type,
                    vendor_obj=current_vendor,
                    previous_menu=self,
                    previous_embed=self.current_embed
                )
            )
        await interaction.response.edit_message(embed=menu_embed, view=view)

    @discord.ui.button(label='Sell', style=discord.ButtonStyle.green, custom_id='sell')
    async def sell_button(self, interaction: discord.Interaction, button: discord.Button):
        if self.current_embed is None:
            await interaction.response.send_message('Select a vendor to sell to', ephemeral=True, delete_after=10)
            return

        convoy_balance = f'{self.user_info['convoys'][0]['money']:,}'
        current_vendor = self.menu[self.position]
        user_convoy = self.user_info['convoys'][0]
        sell_embed = discord.Embed(
            title=f'Selling to {current_vendor['name']}',
            description='*All vendors will buy all cargo. Resources may only be sold to their respecive vendor types (ex: fuel to gasoline refineries, water to water reclamation plants), and vehicles may only be sold to dealerships.*',
            color=discord.Color.blurple()
        )
        
        sell_embed.set_author(
            name=f'{user_convoy['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        # Create a list of items in the user's convoy that can be sold to the vendor.
        # This list isn't for display, we're sending it to the next view as a list menu.
        sellable_cargo = []
        user_info = self.user_info['convoys'][0]
        for vehicle in user_info['vehicles']:
            for cargo_item in vehicle['cargo']:
                sellable_cargo.append(cargo_item)
        
        await interaction.response.edit_message(
            embed=sell_embed,
            view=SellSelectView(
                interaction=interaction,
                user_info=self.user_info,
                vendor_obj=current_vendor,
                sellable_cargo=sellable_cargo,
                previous_embed=self.current_embed,
                previous_view=self,
                current_embed=sell_embed
            ))
        
    @discord.ui.button(label='▶', style=discord.ButtonStyle.blurple, custom_id='next')
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        '''Simple button to bring user back and forth between the menu list'''
        self.position = (self.position + 1) % len(self.menu)
        await self.update_menu(interaction)
    
    async def update_menu(self, interaction: discord.Interaction):
        '''Update embed to send user back and forth between list menu items.'''
        # TODO: give this method a 'menu_type' argument to make it dynamic
        # coming back to this later, chances are 'menu_type' can go entirely. it'd make more sense to create seperate menu views for each menu type.
        convoy_balance = f'{self.user_info['convoys'][0]['money']:,}'
        index = self.position
        current_vendor = self.menu[index]
        item_embed = discord.Embed(
            title=self.menu[index]['name'],
            description='Available Services:'
        )

        self.current_embed = item_embed
        
        for service, availability in vendor_services(current_vendor):
            item_embed.add_field(
                name=service,
                value=availability,
            )

        # display stuff
        item_embed.set_footer(text=f'Vendor [{index + 1} / {len(self.menu)}]')
        item_embed.set_author(  # TODO: make a basic function for this, it would help reduce a few lines of code and would be easy.
            name=f'{self.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(embed=item_embed)


class BuyView(discord.ui.View):
    '''
    Menu for selecting and buying items from vendors.
    
    - Appears when `Buy` button from VendorMenuView is pressed. 

    - Directs to `VehicleConfirmView` if user is buying a vehicle, `ResourceView` if user is buying resources,
    and `CargoQuantityView` if user is buying cargo.
    '''
    def __init__(
            self,
            interaction: discord.Interaction,
            user_info: dict,
            vendor_obj: str,  # TODO: Change this to vendor_obj (actual vendor object rather than id) for ALL view classes
            menu: list[dict],  # can either be a list of a node's vendors, a list of a vendor's vehicle or cargo inventory, etc
            menu_type: str,  # Which type of menu is being displayed
            previous_menu: discord.ui.View,  # parameters for back buttons  # XXX: change this to previous_view
            previous_embed: discord.Embed
    ):
        super().__init__(timeout=120)

        self.position = -1
        self.interaction = interaction
        self.user_info = user_info
        self.vendor_obj = vendor_obj
        self.menu = menu
        self.menu_type = menu_type
        self.previous_menu = previous_menu
        self.previous_embed = previous_embed

        self.current_embed = None
        self.recipient = None

        # Logic to decide which buttons are added to the view
        
        # hacky af and a temporary solution
        resources = []
        if self.vendor_obj['food']:
            resources.append('food')
        if self.vendor_obj['water']:
            resources.append('water')
        if self.vendor_obj['fuel']:
            resources.append('fuel')
        
        if len(resources) > 0:
            self.add_item(BuyResourceButton(
                self,
                label='Buy Resources',
                style=discord.ButtonStyle.green,
                custom_id='buy_resources'
            ))

        if self.vendor_obj['cargo_inventory']:
            self.add_item(BuyCargoButton(
                self,
                label='Buy Cargo',
                style=discord.ButtonStyle.green,
                custom_id='buy_cargo'
            ))

        if self.vendor_obj['vehicle_inventory']:
            self.add_item(BuyVehicleButton(
                self,
                label='Buy Vehicle',
                style=discord.ButtonStyle.green,
                custom_id='buy_vehicle'
            ))

        self.add_item(MapButton(
            self,
            label='Destination Map (appears in new message)',
            style=discord.ButtonStyle.blurple,
            custom_id='map'
            )
        )
    
    # menu_types = ['vendor', 'vehicle', 'cargo', 'food', 'resource']

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='back_button')
    async def back_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(view=self.previous_menu, embed=self.previous_embed)

    @discord.ui.button(label='◀', style=discord.ButtonStyle.blurple, custom_id='back')
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = (self.position - 1) % len(self.menu)
        await self.update_menu(interaction)

    @discord.ui.button(label='▶', style=discord.ButtonStyle.blurple, custom_id='next')
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = (self.position + 1) % len(self.menu)
        await self.update_menu(interaction)

    # async def buy_resource(self, interaction: discord.Interaction, resource_type: str):

    async def update_menu(self, interaction: discord.Interaction):
        '''Update menu based on whether user pressed back or next button'''
        convoy_balance = f'{self.user_info['convoys'][0]['money']:,}'
        index = self.position
        current_item = self.menu[index]
        if self.menu_type == 'cargo':
            if current_item['recipient']:
                recipient_dict = await api_calls.get_vendor(current_item['recipient'])

                self.recipient = recipient_dict
                recipient_name = recipient_dict['name']
                delivery_reward = current_item['delivery_reward']
            else:
                self.recipient = None
                recipient_name = 'None'
                delivery_reward = 'None'
            image_file = None
            item_embed = discord.Embed(
                title=current_item['name'],
                description=textwrap.dedent(f'''\
                    *{current_item['base_desc']}*

                    - Base Price: **${current_item['base_price']}**
                    - Recipient: **{recipient_name}**
                    - Delivery Reward: **{delivery_reward}**
                ''')
            )

            item_embed.add_field(name='Quantity', value=current_item['quantity'])
            item_embed.add_field(name='Volume', value=f'{current_item['volume']} liter(s)')
            item_embed.add_field(name='Weight', value=f'{current_item['weight']} kilogram(s)')

            item_embed.set_footer(text=f'Page [{index + 1} / {len(self.menu)}]')

        if self.menu_type == 'vehicle':
            item_embed = discord.Embed(
                title=f'{current_item['name']}',
                description=textwrap.dedent(f'''\
                    ### ${current_item['value']:,}
                    - Fuel Efficiency: **{current_item['base_fuel_efficiency']}**/100
                    - Offroad Capability: **{current_item['offroad_capability']}**/100
                    - Top Speed: **{current_item['top_speed']}**/100
                    - Cargo Capacity: **{current_item['cargo_capacity']}** liter(s)
                    - Weight Capacity: **{current_item['weight_capacity']}** kilogram(s)
                    - Towing Capacity: **{current_item['towing_capacity']}** kilogram(s)

                    *{current_item['base_desc']}*
                ''')
            )
            
            item_embed.add_field(name='Wear', value=current_item['wear'])
            item_embed.add_field(name='Armor Points', value=f'{current_item['ap']}/{current_item['max_ap']}')
            item_embed.add_field(name='Offroad Capability', value=f'{current_item['offroad_capability']}/100')

            item_embed.set_footer(text=f'Page [{index + 1} / {len(self.menu)}]')

        item_embed.set_author(
            name=f'{self.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        self.current_embed = item_embed

        await interaction.response.edit_message(embed=item_embed)


class ResourceView(discord.ui.View):
    '''
    A simple view that allows users to select a resource to buy or sell.

    - Appears if user presses button to buy resources while in `BuyView`

    - Directs to `ResourceQuantityView` when user presses a `ResourceButton`
    '''
    def __init__(
            self,
            interaction: discord.Interaction,
            user_info: dict,
            vendor_obj: dict,
            buttons: list[str],  # ['fuel', 'water', 'food']
            trade_type: str,
            previous_embed: discord.Embed,
            previous_menu: discord.ui.View
        ):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.user_info = user_info
        self.vendor_obj = vendor_obj
        self.buttons = buttons
        self.trade_type = trade_type
        self.previous_embed = previous_embed
        self.previous_menu = previous_menu

        for button in buttons:
            if button == 'food':
                self.add_item(ResourceButton(
                    self,
                    trade_type=self.trade_type,
                    label='Food',
                    style=discord.ButtonStyle.blurple,
                    custom_id=button
                )
            )
            elif button == 'water':
                self.add_item(ResourceButton(
                    self,
                    trade_type=self.trade_type,
                    label='Water',
                    style=discord.ButtonStyle.blurple,
                    custom_id=button
                )
            )
            elif button == 'fuel':
                self.add_item(ResourceButton(
                    self,
                    trade_type=self.trade_type,
                    label='Fuel',
                    style=discord.ButtonStyle.blurple,
                    custom_id=button
                )
            )
        
    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='back_button')
    async def back_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(view=self.previous_menu, embed=self.previous_embed)


# View Classes:
class CargoQuantityView(discord.ui.View):
    '''
    Final button menu for buying from, and selling cargo to vendors. Contains quantity buttons so user can decide
    how much of a cargo to sell or buy, and contains the final button that makes the API call to buy or sell cargo.
    
    - Appears when 'sell' button is pressed while `CargoSellView` is active

    - This is a final view, so it doesn't direct to any other menu view unless if the back button is pressed.
    '''
    def __init__(
            self,
            interaction: discord.Interaction,  # Using interaction.user, we can get user's ID and therefore relevant information
            user_info: dict,
            vendor_obj: dict,
            cargo_obj: dict,
            trade_type: str,  # 'buy', 'sell'
            previous_embed: discord.Embed,
            previous_view: discord.ui.View,
            # TODO: add max_quantity parameter to this view (and QuantityButton) so that users cannot attempt to purchase or sell more cargo than they or the vendor have
        ):
        super().__init__(timeout=120)
        # args
        self.interaction = interaction
        self.vendor_obj = vendor_obj
        self.previous_embed = previous_embed
        self.cargo_obj = cargo_obj
        self.trade_type = trade_type
        self.user_info = user_info
        self.previous_view = previous_view


        self.quantity = 0

        # FIXME: maybe find a way to add this that isn't so ugly? don't know how i would do it but it would be nice
        # went over this before but I think what i'm going to do instead is have quantity buttons as static decorator buttons
        # and add buy/sell buttons as dynamic button classes. It's more lines of code, but it'll make the display look so much better.
        self.add_item(QuantityButton(self, item=self.cargo_obj['name'], label='-5', style=discord.ButtonStyle.gray, custom_id='-5'))
        self.add_item(QuantityButton(self, item=self.cargo_obj['name'], label='-1', style=discord.ButtonStyle.gray, custom_id='-1'))
        self.add_item(QuantityButton(self, item=self.cargo_obj['name'], label='+1', style=discord.ButtonStyle.gray, custom_id='1'))
        self.add_item(QuantityButton(self, item=self.cargo_obj['name'], label='+5', style=discord.ButtonStyle.gray, custom_id='5'))

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='back_button')
    async def back_button(self, interaction: discord.Interaction, button: discord.Button):
        self.previous_embed.remove_footer()
        await interaction.response.edit_message(view=self.previous_view, embed=self.previous_embed)

    # TODO: Implement dynamic button strategy used when buying resources
    @discord.ui.button(label='Buy Cargo', style=discord.ButtonStyle.green, custom_id='buy_cargo')
    async def buy_button(self, interaction: discord.Interaction, button: discord.Button):
        # API call to buy cargo item from vendor
        convoy_before_money = self.user_info['convoys'][0]['money']
        try:
            convoy_after_dict = await api_calls.buy_cargo(
                vendor_id=self.vendor_obj['vendor_id'],
                convoy_id=self.user_info['convoys'][0]['convoy_id'],
                cargo_id=self.cargo_obj['cargo_id'],
                quantity=self.quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        delta_cash = convoy_after_dict['money'] - convoy_before_money

        # set up buy embed for editing and display for user
        embed = discord.Embed(
            title = f'You bought {self.quantity} {self.cargo_obj['name']}',
            description=f'Your convoy spent ${delta_cash} in the transaction',
            color=discord.Color.green()
        )

        # if the cargo has a recipient, say so in the buy embed
        if self.cargo_obj['recipient']:
            # API call to get recipient vendor's info
            dest_vendor_dict = await api_calls.get_vendor(vendor_id=self.cargo_obj['recipient'])

            # recipient_id = cargo_obj['recipient']
            recipient = dest_vendor_dict['name']
            embed.description = textwrap.dedent(f'''\
                Deliver it to {recipient} for a cash reward of $**{self.cargo_obj['delivery_reward']}** (each)
                                                    
                *{self.cargo_obj['base_desc']}*
            ''')
        else:
            embed.description = textwrap.dedent(f'''\
                Cargo has been added to your convoy.

                *{self.cargo_obj['base_desc']}*
            ''')

        convoy_balance = f'{convoy_after_dict['money']:,}'
        embed.set_author(
            name=f'{convoy_after_dict['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(
            embed=embed,
            view=BackButtonView(
                interaction=interaction,
                previous_embed=self.previous_embed,
                previous_view=self
            )
        )

    @discord.ui.button(label='Sell Cargo', style=discord.ButtonStyle.green, custom_id='sell_cargo')
    async def sell_button(self, interaction: discord.Interaction, button: discord.Button):
        convoy_before_money = self.user_info['convoys'][0]['money']
        try:
            convoy_after_dict = await api_calls.sell_cargo(
                vendor_id=self.vendor_obj['vendor_id'],
                convoy_id=self.user_info['convoys'][0]['convoy_id'],
                cargo_id=self.cargo_obj['cargo_id'],
                quantity=self.quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        delta_cash = convoy_after_dict['money'] - convoy_before_money
        
        print()
        print(f'{convoy_after_dict['money']} - {convoy_before_money} = {delta_cash}')
        print()

        embed = discord.Embed(
            title=f'You sold {self.quantity} {self.cargo_obj['name']} to {self.vendor_obj['name']}',
            description=f'Your convoy made ${delta_cash} from the transaction.'
        )
        convoy_balance = f'{convoy_after_dict['money']:,}'
        embed.set_author(
            name=f'{convoy_after_dict['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=BackButtonView(interaction, previous_embed=self.previous_embed, previous_view=self))

class ResourceQuantityView(discord.ui.View):
    '''
    Final button menu for buying from, and selling resources to `vendors`. Contains quantity buttons so user can decide
    how much of a resource to sell or buy, and contains the final button that makes the API call to buy or sell the resource.

    - Appears when `ResourceButton` is pressed (button of `ResourceSelectView`)

    - This is a final view, so it doesn't direct to any other menu view unless if the back button is pressed.
    '''
    def __init__(
            self,
            interaction: discord.Interaction,
            user_info: dict,
            vendor_obj: dict,
            resource_type: str,
            trade_type: str,
            previous_embed: discord.Embed,
            previous_view: discord.ui.View,
    ):
        super().__init__(timeout=120)
        # args
        self.interaction = interaction
        self.vendor_obj = vendor_obj
        self.previous_embed = previous_embed
        self.user_info = user_info
        self.resource_type = resource_type
        self.previous_view = previous_view
        self.trade_type = trade_type

        self.quantity = 0

        if self.trade_type == 'buy':
            self.add_item(ResourceBuyButton(self, label='Buy Resource', style=discord.ButtonStyle.green, custom_id='buy_resource'))
        elif self.trade_type == 'sell':
            self.add_item(ResourceSellButton(self, label='Sell Resource', style=discord.ButtonStyle.green, custom_id='sell_resource'))

        self.add_item(QuantityButton(self, item=self.resource_type, label='-10', style=discord.ButtonStyle.gray, custom_id='-10'))
        self.add_item(QuantityButton(self, item=self.resource_type, label='-1', style=discord.ButtonStyle.gray, custom_id='-1'))
        self.add_item(QuantityButton(self, item=self.resource_type, label='+1', style=discord.ButtonStyle.gray, custom_id='1'))
        self.add_item(QuantityButton(self, item=self.resource_type, label='+10', style=discord.ButtonStyle.gray, custom_id='10'))
        
    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='back_button')
    async def back_button(self, interaction: discord.Interaction, button: discord.Button):
        self.previous_embed.remove_footer()
        await interaction.response.edit_message(view=self.previous_view, embed=self.previous_embed)

# TODO: Also need to implement Sell vehicle view
# TODO: future also implement vehicle repair AP, vehicle repair wear

# class VehicleBuyView(discord.ui.View):
#     pass

class VehicleConfirmView(discord.ui.View):
    '''
    Confirmation view for either buying or selling vehicles.

    - Appears when 'Buy Vehicle' button is pressed in `BuyView` or when 'Sell Vehicle' button is pressed in `VehicleSellView`

    - This is a final view, so it doesn't direct to any other menu view unless if the back button is pressed.
    '''
    def __init__(
            self,
            interaction: discord.Interaction,
            user_info: dict,
            vendor_obj: dict,
            vehicle_obj: dict,
            trade_type: str,
            previous_embed: discord.Embed,
            previous_view: discord.ui.View
    ):
        super().__init__(timeout=120)
        # args
        self.interaction = interaction
        self.user_info = user_info
        self.vendor_obj = vendor_obj
        self.vehicle = vehicle_obj
        self.trade_type = trade_type
        self.previous_embed = previous_embed
        self.previous_view = previous_view

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='previous_menu')
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, custom_id='confirm')
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        '''Confirm button for selling and buying vehicles'''
        if self.trade_type == 'sell':  # XXX: Trying to sell a vehicle will most likely throw an error becuase there's still cargo in it; we need error handling
            try:
                convoy_after = await api_calls.sell_vehicle(
                    vendor_id=self.vendor_obj['vendor_id'],
                    convoy_id=self.user_info['convoys'][0]['convoy_id'],
                    vehicle_id=self.vehicle['vehicle_id']
                )
            except RuntimeError as e:
                await interaction.response.send_message(content=e, ephemeral=True)
                return

            embed = discord.Embed(
                title=f'You sold your convoy\'s {self.vehicle['name']}',
                description=f'Money gained: ${self.vehicle['value']}'
            )

        elif self.trade_type == 'buy':
            vehicle_info = self.vehicle
            # API call to buy vehicle from vendor
            try:
                convoy_after = await api_calls.buy_vehicle(
                    vendor_id=self.vendor_obj['vendor_id'],
                    convoy_id=self.user_info['convoys'][0]['convoy_id'],
                    vehicle_id=self.vehicle['vehicle_id']
                )
            except RuntimeError as e:
                await interaction.response.send_message(content=e, ephemeral=True)
                return

            embed = discord.Embed(
                title=f'Your convoy\'s new vehicle: {vehicle_info['name']}',
                description=f'*{vehicle_info['base_desc']}*'
            )

        convoy_balance = f'{convoy_after['money']:,}'
        embed.set_author(
            name=f'{convoy_after['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=BackButtonView(interaction, previous_embed=self.previous_embed, previous_view=self))

class VehicleSellView(discord.ui.View):
    '''
    Select menu for selling vehicles to vendors. 

    - Appears when 'Vehicle' button is pressed in `VehicleSellView`

    - Directs to `VehicleConfirmView` when 'Sell Vehicle' button is pressed
    '''
    def __init__(
            self,
            interaction: discord.Interaction,
            user_info: dict,
            vendor_obj: dict,
            vehicle_menu: list,
            previous_embed: discord.Embed,
            previous_view: discord.ui.View
    ):
        
        super().__init__(timeout=120)
        # args
        self.interaction = interaction
        self.user_info = user_info
        self.vendor_obj = vendor_obj
        self.vehicle_menu = vehicle_menu
        self.previous_embed = previous_embed
        self.previous_view = previous_view

        self.current_embed = None

        self.position = -1

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='previous_menu')
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)
    
    @discord.ui.button(label='◀', style=discord.ButtonStyle.blurple, custom_id='back')
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = (self.position - 1) % len(self.vehicle_menu)
        await self.update_menu(interaction)

    @discord.ui.button(label='Sell Vehicle', style=discord.ButtonStyle.green, custom_id='sell_vehicle')
    async def sell_vehicle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_embed is None:
            await interaction.response.send_message('Select a vehicle to sell to the vendor', ephemeral=True, delete_after=10)
            return

        index = self.position
        current_vehicle = self.vehicle_menu[index]

        await interaction.response.edit_message(
            view=VehicleConfirmView(
                interaction=interaction,
                user_info=self.user_info,
                vendor_obj=self.vendor_obj,
                vehicle_obj=current_vehicle,
                trade_type='sell',
                previous_embed=self.previous_embed,
                previous_view=self
            )
        )

    @discord.ui.button(label='▶', style=discord.ButtonStyle.blurple, custom_id='next')
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = (self.position + 1) % len(self.vehicle_menu)
        await self.update_menu(interaction)

    async def update_menu(self, interaction: discord.Interaction):
        index = self.position
        current_vehicle = self.vehicle_menu[index]

        embed = discord.Embed(
            title=f'{current_vehicle['name']}',
            description=textwrap.dedent(f'''\
                ### ${current_vehicle['value']:,}
                - Fuel Efficiency: **{current_vehicle['base_fuel_efficiency']}**/100
                - Offroad Capability: **{current_vehicle['offroad_capability']}**/100
                - Top Speed: **{current_vehicle['top_speed']}**/100
                - Cargo Capacity: **{current_vehicle['cargo_capacity']}** liter(s)
                - Weight Capacity: **{current_vehicle['weight_capacity']}** kilogram(s)
                - Towing Capacity: **{current_vehicle['towing_capacity']}** kilogram(s)

                *{current_vehicle['base_desc']}*
            ''')  # FIXME: add wear and other values that aren't in this embed
        )
        convoy_balance = f'{self.user_info['convoys'][0]['money']:,}'
        embed.set_author(
            name=f'{self.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        embed.set_footer(
            text=textwrap.dedent(f'''\
            Page [{index + 1} / {len(self.vehicle_menu)}]
            '''
            )
        )

        self.current_embed = embed

        await interaction.response.edit_message(embed=embed)

class SellSelectView(discord.ui.View):
    '''
    Select what type of item the user is trying to sell to the vendor (vehicle, resources, cargo)

    - Appears when 'sell' button is pressed in `VendorMenuView`

    - Directs to `ResourceSelectView` if user is selling resources, `CargoSellView` if user is selling cargo, or (eventually) `VehicleSellView`
    if user is selling a vehicle to the vendor.
    
    '''
    def __init__(
            self,
            interaction: discord.Interaction,  # Using interaction.user, we can get user's ID and therefore relevant information
            user_info: dict,
            vendor_obj: dict,
            sellable_cargo: list,
            previous_embed: discord.Embed,
            previous_view: discord.ui.View,
            current_embed: discord.Embed  # an argument that shouldn't be needed often, only when a response's view is being changed but not its embed.
        ):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.user_info = user_info
        self.vendor_obj = vendor_obj
        self.sellable_cargo = sellable_cargo
        self.previous_embed = previous_embed
        self.previous_view = previous_view
        self.current_embed = current_embed
        self.quantity = 1
        self.position = -1

        if self.vendor_obj['cargo_inventory']:
            self.add_item(SellSelectCargo(parent_view=self, label='Cargo', style=discord.ButtonStyle.blurple, custom_id='cargo'))

        if self.vendor_obj['vehicle_inventory']:
            self.add_item(SellSelectVehicle(parent_view=self, label='Vehicle', style=discord.ButtonStyle.blurple, custom_id='vehicle'))

        if len(vendor_resources(self.vendor_obj)) > 0:
            self.add_item(SellSelectResource(parent_view=self, label='Resource', style=discord.ButtonStyle.blurple, custom_id='resource'))


    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='previous_menu')
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)

class SellSelectResource(discord.ui.Button):
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if not self.parent_view.vendor_obj['cargo_inventory']:
            await interaction.response.send_message(f'{self.parent_view.vendor_obj['name']} does not buy cargo', ephemeral=True, delete_after=10)
            return
        
        embed = discord.Embed(
            title=f'Selling cargo to {self.parent_view.vendor_obj['name']}',
            description='Use buttons to navigate selling menu',
        )

        convoy_balance = f'{self.parent_view.user_info['convoys'][0]['money']:,}'
        embed.set_author(
            name=f'{self.parent_view.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(
            embed=embed,
            view=CargoSellView(
                interaction=interaction,
                user_info=self.parent_view.user_info,
                vendor_obj=self.parent_view.vendor_obj,
                sellable_cargo=self.parent_view.sellable_cargo,
                previous_embed=self.parent_view.current_embed,
                previous_view=self.parent_view
            )
        )

class SellSelectCargo(discord.ui.Button):
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if not self.parent_view.vendor_obj['cargo_inventory']:
            await interaction.response.send_message(f'{self.parent_view.vendor_obj['name']} does not buy cargo', ephemeral=True, delete_after=10)
            return
        
        embed = discord.Embed(
            title=f'Selling cargo to {self.parent_view.vendor_obj['name']}',
            description='Use buttons to navigate selling menu',
        )

        convoy_balance = f'{self.parent_view.user_info['convoys'][0]['money']:,}'
        embed.set_author(
            name=f'{self.parent_view.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(
            embed=embed,
            view=CargoSellView(
                interaction=interaction,
                user_info=self.parent_view.user_info,
                vendor_obj=self.parent_view.vendor_obj,
                sellable_cargo=self.parent_view.sellable_cargo,
                previous_embed=self.parent_view.current_embed,
                previous_view=self.parent_view
            )
        )

class SellSelectVehicle(discord.ui.Button):
    '''
    Directly tied to `SellSelectView`, and only used there.
    '''
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if not self.parent_view.vendor_obj['vehicle_inventory']:
            await interaction.response.send_message(f'{self.parent_view.vendor_obj['name']} does not buy vehicles', ephemeral=True, delete_after=10)
        embed = discord.Embed(
            title=f'Selling vehicle to {self.parent_view.vendor_obj['name']}',
            description='Use buttons to navigate selling menu'
        )

        convoy_balance = f'{self.parent_view.user_info['convoys'][0]['money']:,}'
        embed.set_author(
            name=f'{self.parent_view.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(
            embed=embed,
            view=VehicleSellView(
                interaction=interaction,
                user_info=self.parent_view.user_info,
                vendor_obj=self.parent_view.vendor_obj,
                vehicle_menu=self.parent_view.user_info['convoys'][0]['vehicles'],
                previous_embed=self.parent_view.current_embed,
                previous_view=self.parent_view
            )
        )

class ResourceSelectView(discord.ui.View):
    '''
    A simple view that allows users to select a resource to buy or sell.

    - Appears if user presses button to buy resources while in `BuyView`, or if 'Resource' button
    is pressed in `SellSelectView`

    - Contains `ResourceButton`s that direct to `ResourceQuantityView` when pressed
    '''
    def __init__(
            self,
            interaction: discord.Interaction,
            user_info: dict,
            vendor_obj: dict,
            trade_type: str,  # 'buy', 'sell'
            previous_embed: discord.Embed,
            previous_view: discord.ui.View,
    ):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.vendor_obj = vendor_obj
        self.previous_embed = previous_embed
        self.trade_type = trade_type
        self.user_info = user_info
        self.previous_view = previous_view

        if vendor_obj['fuel']:
            self.add_item(ResourceButton(
                self,
                trade_type=self.trade_type,
                embed=self.previous_embed,
                label='Fuel',
                style=discord.ButtonStyle.blurple,
                custom_id='fuel'
            ))
        elif vendor_obj['water']:
            self.add_item(ResourceButton(
                self,
                trade_type=self.trade_type,
                embed=self.previous_embed,
                label='Water',
                style=discord.ButtonStyle.blurple,
                custom_id='water'
            ))
        elif vendor_obj['food']:
            self.add_item(ResourceButton(
                self,
                trade_type=self.trade_type,
                embed=self.previous_embed,
                label='Food',
                style=discord.ButtonStyle.blurple,
                custom_id='food'
            ))

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='back_button')
    async def back_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(view=self.previous_view, embed=self.previous_embed)

class CargoSellView(discord.ui.View):
    def __init__(
            self,
            interaction: discord.Interaction,
            user_info: dict,
            vendor_obj: dict,
            sellable_cargo: list,
            previous_embed: discord.Embed,
            previous_view: discord.ui.View
    ):
        super().__init__(timeout=120)
        # args
        self.interaction = interaction
        self.user_info = user_info
        self.vendor_obj = vendor_obj
        self.sellable_cargo = sellable_cargo
        self.previous_embed = previous_embed
        self.previous_view = previous_view

        self.current_embed = None

        self.quantity = 1
        self.position = -1

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='previous_menu')
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)

    @discord.ui.button(label='◀', style=discord.ButtonStyle.blurple, custom_id='back')
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = (self.position - 1) % len(self.sellable_cargo)
        await self.update_menu(interaction)

    @discord.ui.button(label='Sell', style=discord.ButtonStyle.green, custom_id='sell')
    async def sell_button(self, interaction: discord.Interaction, button: discord.Button):
        if self.current_embed is None:
            await interaction.response.send_message('Select a cargo to sell to the vendor', ephemeral=True, delete_after=10)
            return
        await interaction.response.edit_message(view=CargoQuantityView(
            interaction=interaction,
            user_info=self.user_info,
            vendor_obj=self.vendor_obj,
            cargo_obj=self.sellable_cargo[self.position],
            trade_type='sell',
            previous_embed=self.current_embed,
            previous_view=self
        ))

    @discord.ui.button(label='▶', style=discord.ButtonStyle.blurple, custom_id='next')
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.position = (self.position + 1) % len(self.sellable_cargo)
        await self.update_menu(interaction)

    async def update_menu(self, interaction: discord.Interaction):
        index = self.position
        sell_item = self.sellable_cargo[index]
        if sell_item['recipient']:  # API call to get recipient's vendor info
            vendor_dict = await api_calls.get_vendor(vendor_id=sell_item['recipient'])
                
            recipient = vendor_dict['name']
            delivery_reward = sell_item['delivery_reward']
        else:  # No recipient, no worries
            recipient = 'None'
            delivery_reward = 'None'

        # API call to get vehicle
        cargo_vehicle_dict = await api_calls.get_vehicle(vehicle_id=sell_item['vehicle_id'])

        embed = discord.Embed(
            title=self.sellable_cargo[index]['name'],
            description=textwrap.dedent(f'''\
                *{sell_item['base_desc']}*

                - Base (sell) Price: **${sell_item['base_price']}**
                - Recipient: **{recipient}**
                - Delivery Reward: **{delivery_reward}**
                - Carrier Vehicle: **{cargo_vehicle_dict['name']}**
                - Cargo quantity: **{sell_item['quantity']}**
            ''')
        )

        convoy_balance = f'{self.user_info['convoys'][0]['money']:,}'
        embed.set_author(
            name=f'{self.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        embed.set_footer(text=f'Page [{index + 1} / {len(self.sellable_cargo)}]')
        self.current_embed = embed
        # self.previous_embed = embed
        await interaction.response.edit_message(embed=embed)

class BuyResourceButton(discord.ui.Button):
    '''
    Not to be confused with ResourceBuyButton, which executes the API call to buy resources.
    This button is simply to choose which resource the user would like to buy from the vendor.

    Applied to `BuyView` if there are any resources at the vendor the user is shopping at.
    '''
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # Make list of buttons depending on which resources are available at this vendor
        buttons = []
        if self.parent_view.vendor_obj['food']:
            buttons.append('food')
        if self.parent_view.vendor_obj['water']:
            buttons.append('water')
        if self.parent_view.vendor_obj['fuel']:
            buttons.append('fuel')
        
        if len(buttons) == 0:
            await interaction.response.send_message(content=f'{self.parent_view.vendor_obj['name']} has no resource services', ephemeral=True, delete_after=10)

        embed = discord.Embed(
            title=f'Shopping for resources at {self.parent_view.vendor_obj['name']}',
            description='Use buttons to navigate the buy menu'
        )
        
        if self.parent_view.current_embed:  # If the parent view has a current embed, mainly for saving positions if iterating through a menu
            previous_embed = self.parent_view.current_embed
        else:
            previous_embed = embed

        view = ResourceSelectView(
            interaction = discord.Interaction,
            user_info = self.parent_view.user_info,
            vendor_obj = self.parent_view.vendor_obj,
            trade_type = 'buy',
            previous_embed = previous_embed,
            previous_view = self.parent_view,
        )

        await interaction.response.edit_message(view=view)
        return

class BuyCargoButton(discord.ui.Button):
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        # if not self.parent_view.vendor_obj['cargo_inventory']:
        #     await interaction.response.send_message(f'{self.vendor_obj['name']} does not sell cargo', ephemeral=True, delete_after=10)
        #     return
        if self.parent_view.current_embed is None:
            await interaction.response.send_message('Select a cargo to buy from the vendor', ephemeral=True, delete_after=10)
            return
        
        convoy_balance = f'{self.parent_view.user_info['convoys'][0]['money']:,}'
        index = self.parent_view.position
        current_item = self.parent_view.menu[index]
        user_info = self.parent_view.user_info
        cargo_description = textwrap.dedent(f'''\
            *{current_item['base_desc']}*

            - Base Price: **${current_item['base_price']}**
        ''')

        if current_item['recipient']:  # If the cargo has a recipient, get the recipient's info to display to user
            recipient_vendor = await api_calls.get_vendor(vendor_id=current_item['recipient'])

            cargo_description += textwrap.dedent(f'''\
                - Recipient: **{recipient_vendor['name']}**
                - Delivery Reward: **{current_item['delivery_reward']}**
            ''')

        item_embed = discord.Embed(
            title=current_item['name'],
            description=cargo_description
        )
    
        item_embed.add_field(name='Quantity', value=current_item['quantity'])
        item_embed.add_field(name='Volume', value=f'{current_item['volume']} liter(s)')
        item_embed.add_field(name='Weight', value=f'{current_item['weight']} kilogram(s)')

        item_embed.set_author(
            name=f'{self.parent_view.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(embed=item_embed, view=CargoQuantityView(
            interaction=interaction,
            user_info=user_info,
            vendor_obj=self.parent_view.vendor_obj,
            cargo_obj=current_item,
            trade_type='buy',
            previous_embed=item_embed,
            previous_view=self.parent_view
            )
        )

class BuyVehicleButton(discord.ui.Button):
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # if not self.vendor_obj['vehicle_inventory']:
            # await interaction.response.send_message(f'No vehicles are available at {self.vendor_obj['name']}.', ephemeral=True, delete_after=10)
        if self.parent_view.current_embed is None:
            await interaction.response.send_message('Select a vehicle to buy from the vendor', ephemeral=True, delete_after=10)
            return
        
        convoy_balance = f'{self.parent_view.user_info['convoys'][0]['money']:,}'
        index = self.parent_view.position
        current_vehicle = self.parent_view.menu[index]

        vehicle_description = textwrap.dedent(f'''\
            ### ${current_vehicle['base_value']:,}
            - Fuel Efficiency: **{current_vehicle['base_fuel_efficiency']}**/100
            - Offroad Capability: **{current_vehicle['offroad_capability']}**/100
            - Top Speed: **{current_vehicle['top_speed']}**/100
            - Cargo Capacity: **{current_vehicle['cargo_capacity']}** liters
            - Weight Capacity: **{current_vehicle['weight_capacity']}** kilograms
        ''')

        if current_vehicle['towing_capacity']:
            vehicle_description += textwrap.dedent(f'''\
                - Towing Capacity: **{current_vehicle['towing_capacity']}** kilograms
            ''')

        vehicle_description += textwrap.dedent(f'''\
                                               
            *{current_vehicle['base_desc']}*
        ''')

        item_embed = discord.Embed(
            title=f'{current_vehicle['name']}',
            description=vehicle_description
        )
        item_embed.set_author(
            name=f'{self.parent_view.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        view = VehicleConfirmView(
            interaction=interaction,
            user_info=self.parent_view.user_info,
            vendor_obj=self.parent_view.vendor_obj,
            vehicle_obj=current_vehicle,
            trade_type='buy',
            previous_embed=item_embed,
            previous_view=self
        )
        await interaction.response.edit_message(embed=item_embed, view=view)

class ResourceButton(discord.ui.Button):
    '''
    Simple button for passing on resource type to further view menus
    
    Applied to `ResourceView` and `ResourceSelectView`
    '''
    def __init__(self, parent_view, trade_type: str, embed: discord.Embed, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view
        self.trade_type = trade_type
        self.embed = embed
    async def callback(self, interaction: discord.Interaction):
        if self.trade_type == 'buy':
            self.embed.set_footer(text=f'{self.label} in cart: 0')
        else:
            self.embed.set_footer(text=f'{self.label} to sell: 0')

        await interaction.response.edit_message(
            embed=self.embed,
            view=ResourceQuantityView(
                interaction=self.parent_view.interaction,
                user_info=self.parent_view.user_info,
                vendor_obj=self.parent_view.vendor_obj,
                resource_type=self.custom_id,
                trade_type=self.trade_type,
                previous_embed=self.parent_view.previous_embed,
                previous_view=self.parent_view
            )
        )

# Most likely avaialble to reuse this for different quantity view types
# XXX: wait couldn't i high key just put some decorator buttons on QuantityView instead??
# lol i think it makes more sense to have the quantity buttons as a decorator button and the sell/buy buttons as button classes
class QuantityButton(discord.ui.Button):
    def __init__(self, parent_view, item: str, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view
        self.item = item
    async def callback(self, interaction: discord.Interaction):
        embed = self.parent_view.previous_embed
        if self.parent_view.quantity + int(self.custom_id) <= 0:
            self.parent_view.quantity = 0
        else:
            self.parent_view.quantity += int(self.custom_id)
        if self.parent_view.trade_type == 'buy':
            embed.set_footer(text=f'{self.item} in cart: {self.parent_view.quantity}')
        else:
            embed.set_footer(text=f'{self.item} to sell: {self.parent_view.quantity}')

        await interaction.response.edit_message(embed=embed)

class CargoSellButton(discord.ui.Button):
    def __init__(self, parent_view, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        cargo_obj = self.parent_view.cargo_obj
        user_info = self.parent_view.user_info

        # async with httpx.AsyncClient(verify=False) as client:
        #     pass

class ResourceBuyButton(discord.ui.Button):
    def __init__(self, parent_view, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        user_info = self.parent_view.user_info

        try:
            convoy_after = await api_calls.buy_resource(
                vendor_id=self.parent_view.vendor_obj['vendor_id'],
                convoy_id=user_info['convoys'][0]['convoy_id'],
                resource_type=self.parent_view.resource_type,
                quantity=self.parent_view.quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        embed = discord.Embed(
            title=f'You refilled {self.parent_view.quantity} {self.parent_view.resource_type} for your convoy',
            # description=f'The transaction cost your convoy ${(self.parent_view.quantity * 30)}'
        )
        if self.parent_view.resource_type == 'water':
            embed.color = discord.Color.blue()
        elif self.parent_view.resource_type == 'food':
            embed.color = discord.Color.green()
        elif self.parent_view.resource_type == 'fuel':
            embed.color = discord.Color.gold()

        embed.set_author(
            name=f'{convoy_after['name']} | ${convoy_after['money']:,}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=BackButtonView(interaction, previous_embed=self.parent_view.previous_embed, previous_view=self.parent_view))

class ResourceSellButton(discord.ui.Button):
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        user_info = self.parent_view.user_info
        resource_type = self.parent_view.resource_type

        try:
            convoy_after = await api_calls.sell_resource(
                vendor_id=self.parent_view.vendor_obj['vendor_id'],
                convoy_id=user_info['convoys'][0]['convoy_id'],
                resource_type=self.parent_view.resource_type,
                quantity=self.parent_view.quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        embed = discord.Embed(
            title=f'You sold {self.parent_view.quantity} {resource_type} to {self.parent_view.vendor_obj['name']}',
        )

        embed.set_author(
            name=f'{convoy_after['name']} | ${convoy_after['money']:,}',
            icon_url=interaction.user.avatar.url
        )

        self.parent_view.previous_embed.remove_footer()  # Remove the footer 

        await interaction.response.edit_message(embed=embed, view=BackButtonView(interaction, previous_embed=self.parent_view.previous_embed, previous_view=self.parent_view))

class MapButton(discord.ui.Button):
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        vendor_x = self.parent_view.vendor_obj['x']
        vendor_y = self.parent_view.vendor_obj['y']
        embed = discord.Embed(
            title=f'Map relative to {self.parent_view.vendor_obj['name']}',
            description=textwrap.dedent('''
                🟨 - Your convoy's location
                🟦 - Recipient vendor's location
            ''')
        )

        if self.parent_view.recipient:
            recipient_info = self.parent_view.recipient
            recipient_x = recipient_info['x']
            recipient_y = recipient_info['y']

            if vendor_x < recipient_x:
                min_x = vendor_x
                max_x = recipient_x
            else:
                min_x = recipient_x
                max_x = vendor_x
            
            # Declaring minimum and maximum y coordinates
            if vendor_y < recipient_y:
                min_y = vendor_y
                max_y = recipient_y
            else:
                min_y = recipient_y
                max_y = vendor_y
                
            x_padding = 3
            y_padding = 3

            map_embed, image_file = await add_map_to_embed(
                embed=embed,
                highlighted=[(vendor_x, vendor_y)],
                lowlighted=[(recipient_x, recipient_y)],
                top_left=(min_x - x_padding, min_y - y_padding),
                bottom_right=(max_x + x_padding, max_y + y_padding),
            )
        else:
            x_padding = 16
            y_padding = 9

            map_embed, image_file = await add_map_to_embed(
                embed=embed,
                highlighted=[(vendor_x, vendor_y)],
                top_left=(vendor_x - x_padding, vendor_y - y_padding),
                bottom_right=(vendor_x + x_padding, vendor_y + y_padding),
            )

        map_embed.set_footer(text='Your vendor interaction is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.followup.send(
            embed=map_embed,
            file=image_file,
            ephemeral=True
        )
