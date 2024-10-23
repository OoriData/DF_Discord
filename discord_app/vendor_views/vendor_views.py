# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, df_embed_author
from discord_app.map_rendering import add_map_to_embed
from discord_app.vendor_views.mechanic_views import MechVehicleDropdownView
import discord_app.vendor_views.mechanic_views
import discord_app.vendor_views.buy_menus
import discord_app.vendor_views.sell_menus
import discord_app.nav_menus

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')

# TODO: send message if user tries to iterate through menu with a length of zero
# TODO: Add universal BackButtonView that just allows users to go back to the main vendor menu after they complete a transaction


async def vendor_menu(df_state: DFState, edit: bool=True):
    vendor_embed = discord.Embed()
    vendor_embed = df_embed_author(vendor_embed, df_state)

    if df_state.vendor_obj:  # If a vendor has been selected
        vendor_embed.description = '\n'.join([
            f'## {df_state.vendor_obj['name']}',
            'Available Services:'
        ])
        
        for service, availability in vendor_services(df_state.vendor_obj):
            vendor_embed.add_field(
                name=service,
                value=availability,
            )

        vendor_view = VendorView(df_state)

    else:  # If no vendor selected, go select one
        tile_obj = await api_calls.get_tile(df_state.convoy_obj['x'], df_state.convoy_obj['y'])
        if not tile_obj['settlements']:
            await df_state.interaction.response.send_message(content='There aint no settle ments here dawg!!!!!', ephemeral=True, delete_after=10)
            return
        
        vendor_embed.description = '\n'.join([
            f'## {tile_obj['settlements'][0]['name']}',
            '\n'.join([f'- {vendor['name']}' for vendor in tile_obj['settlements'][0]['vendors']]),
            'Select a vendor:'
        ])

        vendor_view = ChooseVendorView(df_state, tile_obj['settlements'][0]['vendors'])

    if edit:
        await df_state.interaction.response.edit_message(embed=vendor_embed, view=vendor_view, attachments=[])
    else:
        await df_state.interaction.followup.send(embed=vendor_embed, view=vendor_view)


class ChooseVendorView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState, vendors):
        self.df_state = df_state
        super().__init__(timeout=120)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(VendorSelect(self.df_state, vendors))


class VendorSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, vendors, row: int=1):
        self.df_state = df_state
        self.vendors = vendors

        options=[
            discord.SelectOption(label=vendor['name'], value=vendor['vendor_id'])
            for vendor in self.vendors
        ]
        
        super().__init__(
            placeholder='Select vendor to visit',
            options=options,
            custom_id='select_vendor',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction

        self.df_state.vendor_obj = next((
            v for v in self.vendors
            if v['vendor_id'] == self.values[0]
        ), None)

        await vendor_menu(self.df_state)


class VendorView(discord.ui.View):
    ''' Overarching convoy button menu '''
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=120)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(BuyButton(df_state))
        self.add_item(MechanicButton(df_state))
        self.add_item(SellButton(df_state))


class BuyButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.vendor_obj['cargo_inventory']:
            disabled = False
        else:
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Buy',
            disabled=disabled,
            custom_id='buy_button',
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.vendor_views.buy_menus.buy_menu(self.df_state)


class MechanicButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        if self.df_state.vendor_obj['repair_price']:
            disabled = False
        else:
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Mechanic Services',
            disabled=disabled,
            custom_id='mech_button',
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.vendor_views.mechanic_views.mechanic_menu(self.df_state)


class SellButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        # if self.df_state.vendor_obj['repair_price']:
        #     disabled = False
        # else:
        #     disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Sell',
            # disabled=disabled,
            custom_id='sell_button',
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.df_state.interaction = interaction
        await discord_app.vendor_views.sell_menus.sell_menu(self.df_state)


def vendor_services(vendor: dict):
    service_keys = {
        'fuel': 'Fuel Refilling',
        'water': 'Drinking Water',
        'food': 'Food',
        'cargo_inventory': 'Commerce Items',
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


# ------ KILL? ---------------------------------------------------------------------------------------------------------
class BackToVendorsView(discord.ui.View):
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

        self.remove_item(self.buy_button)
        self.remove_item(self.mechanic_services_button)
        self.remove_item(self.sell_button)
    
    # menu_types = ['vendor', 'vehicle', 'cargo', 'food', 'resource']

    @discord.ui.button(label='◀', style=discord.ButtonStyle.blurple, custom_id='back', row=0)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        '''Simple button to bring user back and forth between the menu list'''
        self.position = (self.position - 1) % len(self.menu)
        await self.update_menu(interaction)

    @discord.ui.button(label='▶', style=discord.ButtonStyle.blurple, custom_id='next', row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        '''Simple button to bring user back and forth between the menu list'''
        self.position = (self.position + 1) % len(self.menu)
        await self.update_menu(interaction)

    # Renaming this to 'buy' instead
    @discord.ui.button(label='Buy', style=discord.ButtonStyle.green, custom_id='buy', row=1)  # TODO: Create an actual 'trade' button which diverges into a sell and buy button
    async def buy_button(self, interaction: discord.Interaction, button: discord.Button):
        if self.current_embed is None:
            await interaction.response.send_message('Select a vendor to buy from', ephemeral=True, delete_after=10)
            return
        
        convoy_balance = f'{self.user_info['convoys'][0]['money']:,}'
        index = self.position
        current_vendor = self.menu[index]  # set variable for menu user is currently interacting with
        
        for cargo in current_vendor['cargo_inventory']:
            cargo['inv_type'] = 'cargo'
        for cargo in current_vendor['vehicle_inventory']:
            cargo['inv_type'] = 'vehicle'

        if current_vendor['cargo_inventory'] or current_vendor['vehicle_inventory']:  # if the vendor has a cargo or vehicle inventory
            # display cargo available for purchase in current vendor's inventory
            cargo_list = []
            for cargo in current_vendor['cargo_inventory']:  # could maaaaaaybe list comprehension this, not super important
                cargo_str = f'- {cargo['name']} - ${cargo['base_price']}'
                cargo_list.append(cargo_str)
            displayable_cargo = '\n'.join(cargo_list)

            vehicle_list = []
            for vehicle in current_vendor['vehicle_inventory']:
                vehicle_str = f'- {vehicle['name']} - ${vehicle['value']}'
                vehicle_list.append(vehicle_str)
            displayable_vehicles = '\n'.join(vehicle_list)

            menu_embed = discord.Embed(
                title=current_vendor['name'],
                description=textwrap.dedent(f'''\
                    **Available for Purchase:**
                    Vehicles:
                    {displayable_vehicles}

                    Cargo:
                    {displayable_cargo}
                    
                    **Use the arrows to select the item you want to buy**
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
                menu=current_vendor['cargo_inventory'] + current_vendor['vehicle_inventory'],
                menu_type='n/A',
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

    @discord.ui.button(label='Mechanic Services', style=discord.ButtonStyle.green, custom_id='mechanic_services', row=1)
    async def mechanic_services_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_vendor = self.menu[self.position]  # set variable for menu user is currently interacting with

        vehicle_list = []
        for vehicle in self.user_info['convoys'][0]['vehicles']:
            vehicle_str = f'- {vehicle['name']} - ${vehicle['value']}'
            vehicle_list.append(vehicle_str)
        displayable_vehicles = '\n'.join(vehicle_list)

        mech_dropdown_embed = discord.Embed(
            title=current_vendor['name'],
            description=textwrap.dedent(f'''\
                **Select a vehicle for repairs/upgrades:**
                Vehicles:
                {displayable_vehicles}
            ''')
        )
        mech_dropdown_embed.set_author(
            name=f'{self.user_info['convoys'][0]['name']} | ${self.user_info['convoys'][0]['money']:,}',
            icon_url=interaction.user.avatar.url
        )

        vehicle_dropdown_view = MechVehicleDropdownView(
            user_obj=self.user_info,
            vendor_obj=current_vendor,
            previous_embed=self.current_embed,
            previous_view=self
        )
        
        await interaction.response.edit_message(embed=mech_dropdown_embed, view=vehicle_dropdown_view)

    @discord.ui.button(label='Sell', style=discord.ButtonStyle.green, custom_id='sell', row=1)
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
        
        # Reset buttons
        self.clear_items()
        self.add_item(self.previous_button)
        self.add_item(self.buy_button)
        if self.menu[self.position]['repair_price']:
            self.add_item(self.mechanic_services_button)
        self.add_item(self.sell_button)
        self.add_item(self.next_button)

        await interaction.response.edit_message(embed=item_embed, view=self)


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
        if self.trade_type == 'sell':
            self.add_item(CargoSellButton(self))
        elif self.trade_type == 'buy':
            self.add_item(CargoBuyButton(self))

        self.add_item(QuantityButton(self, item=self.cargo_obj['name'], label='-5', style=discord.ButtonStyle.gray, custom_id='-5'))
        self.add_item(QuantityButton(self, item=self.cargo_obj['name'], label='-1', style=discord.ButtonStyle.gray, custom_id='-1'))
        self.add_item(QuantityButton(self, item=self.cargo_obj['name'], label='+1', style=discord.ButtonStyle.gray, custom_id='1'))
        self.add_item(QuantityButton(self, item=self.cargo_obj['name'], label='+5', style=discord.ButtonStyle.gray, custom_id='5'))

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.green, custom_id='back_button')
    async def back_button(self, interaction: discord.Interaction, button: discord.Button):
        self.previous_embed.remove_footer()
        await interaction.response.edit_message(view=self.previous_view, embed=self.previous_embed)

# TODO: Also need to implement Sell vehicle view
# TODO: future also implement vehicle repair AP, vehicle repair wear

# class VehicleBuyView(discord.ui.View):
#     pass
