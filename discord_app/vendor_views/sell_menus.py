# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, df_embed_author
from discord_app.map_rendering import add_map_to_embed
import discord_app.nav_menus
import discord_app.vehicle_views
import discord_app.cargo_views

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


async def sell_menu(df_state: DFState):
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


class CargoSellView(discord.ui.View):  # XXX: replaced by dropdown menu
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


class CargoSellButton(discord.ui.Button):  # XXX: To be sent to SellButtons or SellView, or replaced by text input
    def __init__(self, parent_view):
        super().__init__(label='Sell Cargo', custom_id='sell_cargo', style=discord.ButtonStyle.green)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        convoy_before_money = self.parent_view.user_info['convoys'][0]['money']
        try:
            convoy_after_dict = await api_calls.sell_cargo(
                vendor_id=self.parent_view.vendor_obj['vendor_id'],
                convoy_id=self.parent_view.user_info['convoys'][0]['convoy_id'],
                cargo_id=self.parent_view.cargo_obj['cargo_id'],
                quantity=self.parent_view.quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        delta_cash = convoy_after_dict['money'] - convoy_before_money

        embed = discord.Embed(
            title=f'You sold {self.parent_view.quantity} {self.parent_view.cargo_obj['name']} to {self.parent_view.vendor_obj['name']}',
            description=f'Your convoy made ${delta_cash} from the transaction.'
        )
        convoy_balance = f'{convoy_after_dict['money']:,}'
        embed.set_author(
            name=f'{convoy_after_dict['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=BackToVendorsView(interaction, previous_embed=self.parent_view.previous_embed, previous_view=self))



class ResourceSellButton(discord.ui.Button):  # XXX: To be sent to SellButtons or SellView, or replaced by text input
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

        await interaction.response.edit_message(embed=embed, view=BackToVendorsView(interaction, previous_embed=self.parent_view.previous_embed, previous_view=self.parent_view))



class VehicleSellView(discord.ui.View):  # XXX: to send to SellMenus
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

class SellSelectView(discord.ui.View):  # XXX: likely going to be replaced by a dropdown menu
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

class SellSelectResource(discord.ui.Button):  # XXX: most likely to be replaced by a dropdown menu
    def __init__(self, parent_view: discord.ui.View, label: str, style: discord.ButtonStyle, custom_id: str):
        super().__init__(label=label, custom_id=custom_id, style=style)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if not self.parent_view.vendor_obj['cargo_inventory']:
            await interaction.response.send_message(f'{self.parent_view.vendor_obj['name']} does not buy cargo', ephemeral=True, delete_after=10)
            return
        
        embed = discord.Embed(
            title=f'Selling resources to {self.parent_view.vendor_obj['name']}',
            description='Use buttons to navigate selling menu',
        )

        convoy_balance = f'{self.parent_view.user_info['convoys'][0]['money']:,}'
        embed.set_author(
            name=f'{self.parent_view.user_info['convoys'][0]['name']} | ${convoy_balance}',
            icon_url=interaction.user.avatar.url
        )

        await interaction.response.edit_message(
            embed=embed,
            view=ResourceSelectView(
                interaction=interaction,
                user_info=self.parent_view.user_info,
                vendor_obj=self.parent_view.vendor_obj,
                trade_type='sell',
                previous_embed=self.parent_view.previous_embed,
                previous_view=self.parent_view.previous_view
            )
        )

class SellSelectCargo(discord.ui.Button):  # XXX: also likely going to be replaced by a dropdown menu
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

class SellSelectVehicle(discord.ui.Button):  # XXX: going to be replaced by a dropdown menu
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
