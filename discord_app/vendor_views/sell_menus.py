# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, handle_timeout, df_embed_author, get_user_metadata, validate_interaction, get_cargo_emoji
from discord_app.map_rendering import add_map_to_embed
import discord_app.nav_menus
import discord_app.vehicle_menus
import discord_app.cargo_menus

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


async def sell_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=sell_menu)  # Add this menu to the back stack

    resources_list = []
    if df_state.vendor_obj['fuel']:
        resources_list.append(f'- Fuel: {df_state.convoy_obj['fuel']} Liters\n  - *${df_state.vendor_obj['fuel_price']} per Liter*')
    if df_state.vendor_obj['water']:
        resources_list.append(f'- Water: {df_state.convoy_obj['water']} Liters\n  - *${df_state.vendor_obj['water_price']} per Liter*')
    if df_state.vendor_obj['food']:
        resources_list.append(f'- Food: {df_state.convoy_obj['food']} meals\n  - *${df_state.vendor_obj['food_price']} per Serving*')
    displayable_resources = '\n'.join(resources_list) if resources_list else '- None'

    vehicle_list = []
    for vehicle in df_state.convoy_obj['vehicles']:
        vehicle_str = f'- {vehicle['name']} | *${vehicle['value']:,}*'
        if not all(c['intrinsic_part_id'] for c in vehicle['cargo']):
            vehicle_str += '\n  - *contains cargo, cannot be sold*'
        vehicle_list.append(vehicle_str)
    displayable_vehicles = '\n'.join(vehicle_list) if vehicle_list else '- None'

    cargo_list = []
    for vehicle in df_state.convoy_obj['vehicles']:
        for cargo in vehicle['cargo']:
            if cargo['intrinsic_part_id']:
                continue

            cargo_str = f'- {cargo['quantity']} **{cargo['name']}**(s) | *{vehicle['name']}* | *${cargo['unit_price']:,} each*'

            if cargo['recipient']:
                cargo['recipient_vendor'] = await api_calls.get_vendor(vendor_id=cargo['recipient'])
                cargo_str += f'\n  - Deliver to *{cargo['recipient_vendor']['name']}* | ${cargo['delivery_reward']:,}'

            cargo_list.append(cargo_str)
    displayable_cargo = '\n'.join(cargo_list) if cargo_list else '- None'

    embed = discord.Embed()
    embed.description='\n'.join([
        f'## {df_state.vendor_obj['name']}',
        '### Available to sell from convoy:',
        '**Resources:**',
        f'{displayable_resources}',
        '',
        '**Vehicles:**',
        f'{displayable_vehicles}',
        '',
        '**Cargo:**',
        f'{displayable_cargo}'
    ])

    embed = df_embed_author(embed, df_state)

    view = SellView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class SellView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(SellResourceButton(self.df_state, 'fuel'))
        self.add_item(SellResourceButton(self.df_state, 'water'))
        self.add_item(SellResourceButton(self.df_state, 'food'))

        self.add_item(SellVehicleSelect(self.df_state))

        self.add_item(SellCargoSelect(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class SellResourceButton(discord.ui.Button):
    def __init__(self, df_state: DFState, resource_type: str, row: int=1):
        self.df_state = df_state
        self.resource_type = resource_type

        disabled = True
        if self.df_state.vendor_obj[resource_type]:
            disabled = False

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=f'Sell {resource_type}',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        await sell_resource_menu(self.df_state, self.resource_type)

class SellVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state

        placeholder = 'Vehicles which can be sold'
        disabled = False
        options=[]
        for vehicle in self.df_state.convoy_obj['vehicles']:
            if all(c['intrinsic_part_id'] for c in vehicle['cargo']):  # Check if any of the cargo aren't intrinsic
                options.append(discord.SelectOption(label=f'{vehicle['name']} | ${vehicle['value']:,}', value=vehicle['vehicle_id']))
        if not options:
            placeholder = 'Convoy has no sellable vehicles'
            disabled = True
            options=[discord.SelectOption(label='None', value='None')]
        if not self.df_state.vendor_obj['vehicle_inventory']:
            placeholder = 'Vendor does not buy vehicles'
            disabled = True

        super().__init__(
            placeholder=placeholder,
            options=options,
            disabled=disabled,
            custom_id='select_vehicle',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        self.df_state.vehicle_obj = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        await sell_vehicle_menu(self.df_state)

class SellCargoSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=3):
        self.df_state = df_state

        placeholder = 'Cargo which can be sold'
        disabled = False

        options = []
        for vehicle in df_state.convoy_obj['vehicles']:
            for cargo in vehicle['cargo']:
                if not cargo['intrinsic_part_id']:
                    if cargo['fuel'] is not None and df_state.vendor_obj['fuel_price'] is not None:
                        cargo['price'] = round(cargo['price'] + cargo['fuel'] * df_state.vendor_obj['fuel_price'], 2)
                    elif cargo['water'] is not None and df_state.vendor_obj['water_price'] is not None:
                        cargo['price'] = round(cargo['price'] + cargo['water'] * df_state.vendor_obj['water_price'], 2)
                    elif cargo['food'] is not None and df_state.vendor_obj['food_price'] is not None:
                        cargo['price'] = round(cargo['price'] + cargo['food'] * df_state.vendor_obj['food_price'], 2)

                    if df_state.vendor_obj['fuel_price'] is None and cargo['fuel'] is not None:
                        continue
                    if df_state.vendor_obj['water_price'] is None and cargo['water'] is not None:
                        continue
                    if df_state.vendor_obj['food_price'] is None and cargo['food'] is not None:
                        continue

                    options.append(discord.SelectOption(  # Append the cargo option with the emoji
                        label=f'{cargo['name']} | {vehicle['name']} | ${cargo['unit_price']:,}',
                        value=cargo['cargo_id'],
                        emoji=get_cargo_emoji(cargo)
                    ))

        if not options:
            placeholder = 'Convoy has no sellable cargo'
            disabled = True
            options = [discord.SelectOption(label='None', value='None')]

        super().__init__(
            placeholder=placeholder,
            options=options[:25],
            disabled=disabled,
            custom_id='select_cargo',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        self.df_state.cargo_obj = next((
            c for c in self.df_state.convoy_obj['all_cargo']
            if c['cargo_id'] == self.values[0]
        ), None)

        await sell_cargo_menu(self.df_state)


async def sell_resource_menu(df_state: DFState, resource_type: str):
    df_state.append_menu_to_back_stack(func=sell_resource_menu, args={'resource_type': resource_type})  # Add this menu to the back stack

    embed = ResourceSellQuantityEmbed(df_state, resource_type)
    view = ResourceSellQuantityView(df_state, resource_type)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class ResourceSellQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, resource_type: str, sale_quantity: int=1):
        self.df_state = df_state
        self.resource_type = resource_type
        self.sale_quantity = sale_quantity
        super().__init__()

        self = df_embed_author(self, self.df_state)

        sale_price = self.sale_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']

        self.description = '\n'.join([
            f'## {df_state.vendor_obj['name']}',
            f'### Selling {self.resource_type} for ${self.df_state.vendor_obj[f'{self.resource_type}_price']:,} per Liter/meals',
            f'{self.df_state.convoy_obj['name']}\'s {self.resource_type}: {self.df_state.convoy_obj[self.resource_type]} Liters/meals',
            f'### Sale: {self.sale_quantity:,.2f} Liters/meals | ${sale_price:,.0f}'
        ])

class ResourceSellQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, resource_type: str, sale_quantity: int=1):
        self.df_state = df_state
        self.resource_type = resource_type
        self.sale_quantity = sale_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, -10, self.resource_type))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, -1, self.resource_type))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 1, self.resource_type))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 10, self.resource_type))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 'max', self.resource_type))

        self.add_item(ResourceConfirmSellButton(self.df_state, self.sale_quantity, self.resource_type, row=2))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class ResourceConfirmSellButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            sale_quantity: int,
            resource_type: str=None,
            row: int=1
    ):
        self.df_state = df_state
        self.sale_quantity = sale_quantity
        self.resource_type = resource_type

        sale_price = self.sale_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Sell {self.sale_quantity:,.2f}L of {self.resource_type} | ${sale_price:,.0f}',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.sell_resource(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                resource_type=self.resource_type,
                quantity=self.sale_quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        sale_price = self.sale_quantity * self.df_state.vendor_obj[f'{self.resource_type}_price']

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'## {self.df_state.vendor_obj['name']}',
            f'Sold {self.sale_quantity:,.2f} Liters/meals of {self.resource_type} for ${sale_price:,.0f}'
        ])

        view = PostSellView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


async def sell_cargo_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=sell_cargo_menu)  # Add this menu to the back stack

    embed = CargoSellQuantityEmbed(df_state)
    view = CargoSellQuantityView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class CargoSellQuantityEmbed(discord.Embed):
    def __init__(self, df_state: DFState, sale_quantity: int=1):
        self.df_state = df_state
        self.sale_quantity = sale_quantity
        super().__init__()

        self = df_embed_author(self, self.df_state)

        sale_volume = self.sale_quantity * self.df_state.cargo_obj['unit_volume']
        sale_weight = self.sale_quantity * self.df_state.cargo_obj['unit_weight']

        desc = [f'## {self.df_state.vendor_obj['name']}']
        if self.df_state.cargo_obj['recipient'] == self.df_state.vendor_obj['vendor_id']:
            desc.append(f'### Delivering {self.df_state.cargo_obj['name']} for a reward of ${self.df_state.cargo_obj['unit_delivery_reward']:,} per item')
            sale_price = self.sale_quantity * self.df_state.cargo_obj['unit_delivery_reward']
        else:
            desc.append(f'### Selling {self.df_state.cargo_obj['name']} for ${self.df_state.cargo_obj['unit_price']:,} per item')
            sale_price = self.sale_quantity * self.df_state.cargo_obj['unit_price']
        desc.extend([
            f'*{self.df_state.cargo_obj['base_desc']}*',
            f'- Sale volume: {sale_volume:,}L',
            f'- Sale weight: {sale_weight:,}kg',
            f'### Sale: {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) | ${sale_price:,}'
        ])

        self.description = '\n'.join(desc)

        if get_user_metadata(df_state, 'mobile'):
            self.description += '\n' + '\n'.join([
                f'- Inventory: {self.df_state.cargo_obj['quantity']}',
                f'- Volume (per unit): {self.df_state.cargo_obj['volume']}L',
                f'- Weight (per unit): {self.df_state.cargo_obj['weight']}kg'
            ])
        else:
            self.add_field(name='Inventory', value=self.df_state.cargo_obj['quantity'])
            self.add_field(name='Volume (per unit)', value=f'{self.df_state.cargo_obj['volume']} liter(s)')
            self.add_field(name='Weight (per unit)', value=f'{self.df_state.cargo_obj['weight']} kilogram(s)')

class CargoSellQuantityView(discord.ui.View):
    def __init__(self, df_state: DFState, sale_quantity: int=1):
        self.df_state = df_state
        self.sale_quantity = sale_quantity
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, -10, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, -1, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 1, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 10, cargo_for_sale=self.df_state.cargo_obj))
        self.add_item(QuantitySellButton(self.df_state, self.sale_quantity, 'max', cargo_for_sale=self.df_state.cargo_obj))

        self.add_item(CargoConfirmSellButton(self.df_state, self.sale_quantity, row=2))
        self.add_item(SellAllCargoButton(self.df_state, row=2))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class CargoConfirmSellButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            sale_quantity: int,
            row: int=1
    ):
        self.df_state = df_state
        self.sale_quantity = sale_quantity

        if self.df_state.cargo_obj['recipient'] == self.df_state.vendor_obj['vendor_id']:
            sale_price = self.sale_quantity * self.df_state.cargo_obj['delivery_reward']
        else:
            sale_price = self.sale_quantity * self.df_state.cargo_obj['unit_price']

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Sell {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) | ${sale_price}',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.sell_cargo(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                cargo_id=self.df_state.cargo_obj['cargo_id'],
                quantity=self.sale_quantity
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        sale_price = self.sale_quantity * self.df_state.cargo_obj['unit_price']

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        desc = [f'## {self.df_state.vendor_obj['name']}']
        if self.df_state.cargo_obj['recipient'] == self.df_state.vendor_obj['vendor_id']:
            delivery_reward = self.sale_quantity * self.df_state.cargo_obj['delivery_reward']
            desc.append(f'Delivered {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) for ${delivery_reward}')
        else:
            desc.append(f'Sold {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) for ${sale_price}')
        embed.description = '\n'.join(desc)

        view = PostSellView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)

class SellAllCargoButton(discord.ui.Button):
    def __init__(
            self,
            df_state: DFState,
            row: int=1
    ):
        self.df_state = df_state

        if self.df_state.cargo_obj['recipient'] == self.df_state.vendor_obj['vendor_id']:
            sell_list = [
                cargo
                for cargo in self.df_state.convoy_obj['all_cargo']
                if cargo['class_id'] == self.df_state.cargo_obj['class_id']
                and cargo['recipient'] == self.df_state.vendor_obj['vendor_id']
            ]
            sale_quantity = sum(cargo['quantity'] for cargo in sell_list)
            sale_price =  sale_quantity * self.df_state.cargo_obj['delivery_reward']
        else:
            sell_list = [
                cargo
                for cargo in self.df_state.convoy_obj['all_cargo']
                if cargo['class_id'] == self.df_state.cargo_obj['class_id']
            ]

            # sell_list = [cargo for vehicle in self.df_state.convoy_obj['vehicles'] for cargo in vehicle if cargo['class_id'] == self.df_state.cargo_obj['class_id']]
            sale_quantity = sum(cargo['quantity'] for cargo in sell_list)
            sale_price = sale_quantity * self.df_state.cargo_obj['price']

        self.sale_quantity = sale_quantity
        self.sell_list = sell_list
        self.sale_price = sale_price

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Sell all {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) across convoy | ${sale_price}',
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        
        self.df_state.interaction = interaction

        try:
            for cargo in self.sell_list:
                self.df_state.convoy_obj = await api_calls.sell_cargo(
                    vendor_id=self.df_state.vendor_obj['vendor_id'],
                    convoy_id=self.df_state.convoy_obj['convoy_id'],
                    # cargo_id=self.df_state.cargo_obj['cargo_id'],
                    cargo_id=cargo['cargo_id'],
                    quantity=cargo['quantity']
                )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return
        
        
        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        desc = [f'## {self.df_state.vendor_obj['name']}']
        if self.df_state.cargo_obj['recipient'] == self.df_state.vendor_obj['vendor_id']:
            # delivery_reward = self. * self.df_state.cargo_obj['delivery_reward']
            desc.append(f'Delivered {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) for ${self.sale_price}')
        else:
            desc.append(f'Sold {self.sale_quantity} {self.df_state.cargo_obj['name']}(s) for ${self.sale_price}')
        embed.description = '\n'.join(desc)

        view = PostSellView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


async def sell_vehicle_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=sell_vehicle_menu)  # Add this menu to the back stack

    part_list = []
    for part in df_state.vehicle_obj['parts']:
        if not part:  # If the part slot is empty
            part_list.append(f'- {part['slot'].replace('_', ' ').capitalize()}\n  - None')
            continue

        part_list.append(discord_app.cargo_menus.format_part(part))
    displayable_vehicle_parts = '\n'.join(part_list)

    embed = discord.Embed()
    embed = df_embed_author(embed, df_state)
    embed.description = '\n'.join([
        f'## {df_state.vendor_obj['name']}',
        f'### {df_state.vehicle_obj['name']} | ${df_state.vehicle_obj['value']:,}',
        f'*{df_state.vehicle_obj['description']}*',
        '### Parts',
        displayable_vehicle_parts,
        '### Stats'
    ])
    embed = discord_app.vehicle_menus.df_embed_vehicle_stats(df_state, embed, df_state.vehicle_obj)

    view = VehicleSellConfirmView(df_state)

    await df_state.interaction.response.edit_message(embed=embed, view=view)

class VehicleSellConfirmView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(SellVehicleButton(self.df_state))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class SellVehicleButton(discord.ui.Button):
    def __init__(self, df_state: DFState):
        self.df_state = df_state

        super().__init__(
            style=discord.ButtonStyle.green,
            label=f'Sell {self.df_state.vehicle_obj['name']} | ${self.df_state.vehicle_obj['value']:,}',
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        try:
            self.df_state.convoy_obj = await api_calls.sell_vehicle(
                vendor_id=self.df_state.vendor_obj['vendor_id'],
                convoy_id=self.df_state.convoy_obj['convoy_id'],
                vehicle_id=self.df_state.vehicle_obj['vehicle_id']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        embed = discord.Embed()
        embed = df_embed_author(embed, self.df_state)
        embed.description = '\n'.join([
            f'Your convoy sold {self.df_state.vehicle_obj['name']} for ${self.df_state.vehicle_obj['value']:,}',
            f'*{self.df_state.vehicle_obj['description']}*'
        ])

        view = PostSellView(self.df_state)

        await interaction.response.edit_message(embed=embed, view=view)


class QuantitySellButton(discord.ui.Button):  # XXX: Explode this button into like 4 different buttons, instead of just nesting a million if/elses
    def __init__(
            self,
            df_state: DFState,
            sale_quantity: int,
            button_quantity: int | str,
            resource_type: str = None,
            cargo_for_sale: dict = None,
            row: int = 1
    ):
        self.df_state = df_state
        self.sale_quantity = sale_quantity
        self.resource_type = resource_type
        self.cargo_for_sale = cargo_for_sale

        if self.cargo_for_sale:  # Determine max quantities
            inventory_quantity = self.df_state.cargo_obj['quantity']
        else:
            inventory_quantity = self.df_state.convoy_obj[self.resource_type]

        if button_quantity == 'max':  # Handle "max" button logic
            self.button_quantity = inventory_quantity - self.sale_quantity
            self.button_quantity = max(0, self.button_quantity)  # Ensure the quantity is 0
            label = f'max ({self.button_quantity:+,})' if self.cargo_for_sale else f'max ({self.button_quantity:+,.2f})'
        else:
            self.button_quantity = int(button_quantity)
            label = f'{self.button_quantity:+,}'

        resultant_quantity = self.sale_quantity + self.button_quantity

        disabled = self.should_disable_button(  # Determine if button should be disabled
            resultant_quantity, inventory_quantity
        )

        if self.button_quantity == 0:  # Disable the button if the "max" button would add 0 quantity
            disabled = True

        super().__init__(
            style=discord.ButtonStyle.blurple,
            label=label,
            disabled=disabled,
            row=row
        )

    def should_disable_button(self, resultant_quantity, inventory_quantity):
        # Disable if the resulting quantity is out of valid bounds
        if resultant_quantity <= 0:
            return True

        if resultant_quantity > inventory_quantity:
            return True

        return False

    async def callback(self, interaction: discord.Interaction):
        await validate_interaction(interaction=interaction, df_state=self.df_state)
        self.df_state.interaction = interaction

        self.sale_quantity += self.button_quantity  # Update sale quantity

        if self.resource_type:  # Update embed and view depending on resource type
            embed = ResourceSellQuantityEmbed(self.df_state, self.resource_type, self.sale_quantity)
            view = ResourceSellQuantityView(self.df_state, self.resource_type, self.sale_quantity)
        else:
            embed = CargoSellQuantityEmbed(self.df_state, self.sale_quantity)
            view = CargoSellQuantityView(self.df_state, self.sale_quantity)

        await interaction.response.edit_message(embed=embed, view=view)


class PostSellView(discord.ui.View):
    def __init__(self, df_state: DFState):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

    async def on_timeout(self):
        await handle_timeout(self.df_state)
