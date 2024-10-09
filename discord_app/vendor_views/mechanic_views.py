# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls
from discord_app.map_rendering import add_map_to_embed

from discord_app.vehicle_views import VehicleView

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')    


def format_part(part):
    fuel_gal = round(part['capacity'] * 0.264172) if part.get('capacity') else None
    lbft = round(part['Nm'] * 0.7376) if part.get('Nm') else None
    horsepower = round(part['kW'] * 1.34102) if part.get('kW') else None
    displacement_cubic_inches = round(part['displacement'] * 61.0237) if part.get('displacement') else None
    cargo_cubic_feet = round(part['cargo_capacity_mod'] * 0.0353147) if part.get('cargo_capacity_mod') else None
    weight_lbs = round(part['weight_capacity_mod'] * 2.20462) if part.get('weight_capacity_mod') else None
    towing_lbs = round(part['towing_capacity_mod'] * 2.20462) if part.get('towing_capacity_mod') else None
    diameter_in = round(part['diameter'] * 39.3701) if part.get('diameter') else None

    part_bits = [
        f'- {part['category'].replace('_', ' ').capitalize()} (OE)' if part.get('OE') else f'- {part['category'].replace('_', ' ').capitalize()}',
        f'  - **{part['name']}**' if part.get('name') else None,

        f'  - {part['capacity']} L ({fuel_gal} gal)' if part.get('capacity') else None,

        f'  - {part['Nm']} N·m ({lbft} lb·ft)' if part.get('Nm') else None,
        f'  - {part['kW']} kW ({horsepower} hp)' if part.get('kW') else None,
        f'  - {part['displacement']} L ({displacement_cubic_inches} in³)' if part.get('displacement') else None,

        f'  - Max AP: {part['max_ap_mod']:+}' if part.get('max_ap_mod') else None,
        f'  - Fuel efficiency: {part['fuel_efficiency_mod']:+}' if part.get('fuel_efficiency_mod') else None,
        f'  - Top speed: {part['top_speed_mod']:+}' if part.get('top_speed_mod') else None,
        f'  - Offroad capability: {part['offroad_capability_mod']:+}' if part.get('offroad_capability_mod') else None,
        f'  - Cargo capacity: {part['cargo_capacity_mod']:+} L ({cargo_cubic_feet:+} ft³)' if part.get('cargo_capacity_mod') else None,
        f'  - Weight capacity: {part['weight_capacity_mod']:+} kg ({weight_lbs:+} lbs)' if part.get('weight_capacity_mod') else None,
        f'  - Towing capacity: {part['towing_capacity_mod']:+} kg ({towing_lbs:+} lbs)' if part.get('towing_capacity_mod') else None,

        f'  - {part['diameter']} m ({diameter_in} in) diameter' if part.get('diameter') else None,

        f'  - *{part['description']}*' if part.get('description') else None,
        # f'  - ${part['part_value']}' if part.get('part_value') else None,
        f'    - Part price: ${part['kit_price']}' if part.get('kit_price') else None,
        f'    - Installation price: ${part['installation_price']}' if part.get('installation_price') else None,
        f'    - **Total installation price: ${part['kit_price'] + part['installation_price']}**' if part.get('kit_price') and part.get('installation_price') else None,
    ]

    return '\n'.join(bit for bit in part_bits if bit)


def add_vehicle_stats_to_embed(embed, vehicle):
    embed.add_field(name='💵 Value', value=f'${vehicle['value']}')
    embed.add_field(name='🔧 Wear', value=f'{vehicle['wear']} / 100')
    embed.add_field(name='🛡️ AP', value=f'{vehicle['ap']} / {vehicle['max_ap']}')
    embed.add_field(name='⛽️ Fuel Efficiency', value=f'{vehicle['fuel_efficiency']} / 100')
    embed.add_field(name='🏎️ Top Speed', value=f'{vehicle['top_speed']} / 100')
    embed.add_field(name='🏔️ Off-road Capability', value=f'{vehicle['offroad_capability']} / 100')
    embed.add_field(name='📦 Cargo Capacity', value=f'{vehicle['cargo_capacity']} L')
    embed.add_field(name='🏋️ Weight Capacity', value=f'{vehicle['weight_capacity']} kg')
    embed.add_field(name='🚛 Towing Capacity', value=f'{vehicle['towing_capacity']} kg')
    return embed


class MechVehicleDropdownView(discord.ui.View):
    def __init__(
            self,
            user_obj,
            vendor_obj,
            previous_embed,
            previous_view
    ):
        super().__init__()

        self.add_item(VehicleSelect(
            user_obj=user_obj,
            vendor_obj=vendor_obj,
            previous_embed=previous_embed,
            previous_view=previous_view
        ))
    
    @discord.ui.button(label='Repair wear and AP for all vehicles', style=discord.ButtonStyle.green, custom_id='repair_all')
    async def repair_all_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.send_message('this don\'t do nothin yet!')


class VehicleSelect(discord.ui.Select):
    def __init__(self, user_obj, vendor_obj, previous_embed, previous_view):
        options=[
            discord.SelectOption(label=vehicle['name'], value=vehicle['vehicle_id'])
            for vehicle in user_obj['convoys'][0]['vehicles']
        ]
        
        super().__init__(
            placeholder='Which vehicle?',
            options=options,
            custom_id='select_vehicle',
        )

        self.user_obj = user_obj
        self.vendor_obj = vendor_obj
        self.previous_embed = previous_embed
        self.previous_view = previous_view


    async def callback(self, interaction: discord.Interaction):
        selected_vehicle = next((
            v for v in self.user_obj['convoys'][0]['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)

        cargo_list = []
        for cargo in self.vendor_obj['cargo_inventory']:  # could maaaaaaybe list comprehension this, not super important
            cargo_str = (
                f'- **{cargo['name']}**\n'
                f'  - ${cargo['base_price']}\n'
                f'  - *{cargo['base_desc']}*'
            )
            cargo_list.append(cargo_str)
        displayable_cargo = '\n'.join(cargo_list)

        mech_embed = discord.Embed(
            title=self.vendor_obj['name'],
            description=(
                f'## {selected_vehicle['name']}\n'
                f'*{selected_vehicle['base_desc']}*\n'
                # f'### Parts\n'
                # f'{displayable_vehicle_parts}\n'
                # f'{vehicle_stats}\n'
                # f'### Parts Available for Purchase\n'
                # f'{displayable_cargo}'
                f'### Stats'
            )
        )
        mech_embed.set_author(
            name=f'{self.user_obj['convoys'][0]['name']} | ${self.user_obj['convoys'][0]['money']:,}',
            icon_url=interaction.user.avatar.url
        )
        mech_embed = add_vehicle_stats_to_embed(mech_embed, selected_vehicle)

        mech_view = MechView(
            user_obj=self.user_obj,
            vendor_obj=self.vendor_obj,
            selected_vehicle=selected_vehicle,
            previous_embed=self.previous_embed,
            previous_view=self.previous_view
        )

        await interaction.response.edit_message(embed=mech_embed, view=mech_view)


class MechView(discord.ui.View):
    def __init__(self, user_obj, vendor_obj, selected_vehicle, previous_embed, previous_view):
        super().__init__()

        self.user_obj = user_obj
        self.vendor_obj = vendor_obj
        self.selected_vehicle = selected_vehicle
        self.previous_embed = previous_embed
        self.previous_view = previous_view

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.blurple, custom_id='previous_menu', row=0)
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)

    @discord.ui.button(label='Repair', style=discord.ButtonStyle.green, custom_id='repair', row=1)
    async def repair_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.send_message('this don\'t do nothin yet!')

    @discord.ui.button(label='Upgrade', style=discord.ButtonStyle.blurple, custom_id='upgrade', row=1)
    async def upgrade_button(self, interaction: discord.Interaction, button: discord.Button):
        part_list = []
        for category, part in self.selected_vehicle['parts'].items():
            if not part:  # If the part slot is empty
                part_list.append(f'- {category.replace('_', ' ').capitalize()}\n  - None')
                continue

            part_list.append(format_part(part))
        displayable_vehicle_parts = '\n'.join(part_list)

        mech_vehicle_embed = discord.Embed(
            title=self.vendor_obj['name'],
            description=(
                f'## {self.selected_vehicle['name']}\n'
                f'*{self.selected_vehicle['base_desc']}*\n'
                f'### Parts\n'
                f'{displayable_vehicle_parts}\n'
                # f'{vehicle_stats}\n'
                # f'### Parts Available for Purchase\n'
                # f'{displayable_cargo}'
                f'### Stats'
            )
        )
        mech_vehicle_embed.set_author(
            name=f'{self.user_obj['convoys'][0]['name']} | ${self.user_obj['convoys'][0]['money']:,}',
            icon_url=interaction.user.avatar.url
        )
        mech_vehicle_embed = add_vehicle_stats_to_embed(mech_vehicle_embed, self.selected_vehicle)

        mech_vehicle_view = MechVehicleView(
            user_obj=self.user_obj,
            vendor_obj=self.vendor_obj,
            selected_vehicle=self.selected_vehicle,
            previous_embed=self.previous_embed,
            previous_view=self
        )

        await interaction.response.edit_message(embed=mech_vehicle_embed, view=mech_vehicle_view)

    @discord.ui.button(label='Strip', style=discord.ButtonStyle.red, custom_id='strip', row=1)
    async def strip_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.send_message('this don\'t do nothin yet!')

    @discord.ui.button(label='Recycle', style=discord.ButtonStyle.red, custom_id='recycle', row=1)
    async def recycle_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.send_message('this don\'t do nothin yet!')


class MechVehicleView(discord.ui.View):
    def __init__(self, user_obj, vendor_obj, selected_vehicle, previous_embed, previous_view):
        super().__init__()

        self.user_obj = user_obj
        self.vendor_obj = vendor_obj
        self.selected_vehicle = selected_vehicle
        self.previous_embed = previous_embed
        self.previous_view = previous_view
    
    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.blurple, custom_id='previous_menu', row=0)
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)
    
    @discord.ui.button(label='Install part from Convoy inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_convoy', row=1)
    async def install_part_from_convoy_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)

    @discord.ui.button(label='Install part from Vendor inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_vendor', row=1)
    async def install_part_from_vendor_button(self, interaction: discord.Interaction, button: discord.Button):
        part_cargos_to_display = []
        for cargo in self.vendor_obj['cargo_inventory']:
            if cargo.get('part'):
                try:
                    check_dict = await api_calls.check_part_compatibility(self.selected_vehicle['vehicle_id'], cargo['cargo_id'])
                    cargo['part'] = check_dict['part']
                    cargo['part']['kit_price'] = cargo['base_price']
                    cargo['part']['installation_price'] = check_dict['installation_price']
                    
                    part_cargos_to_display.append(cargo)
                except RuntimeError as e:
                    print(f'part does not fit: {e}')

        part_list = []
        for cargo in part_cargos_to_display:
            part_list.append(format_part(cargo['part']))
        displayable_vehicle_parts = '\n'.join(part_list)

        cargo_selection_embed = discord.Embed(
            title=self.vendor_obj['name'],
            description=(
                f'## {self.selected_vehicle['name']}\n'
                f'*{self.selected_vehicle['base_desc']}*\n'
                f'### Compatible parts available for purchase and installation\n'
                f'{displayable_vehicle_parts}\n'
                # f'{vehicle_stats}\n'
                # f'### Parts Available for Purchase\n'
                # f'{displayable_cargo}\n'
                f'### Stats'
            )
        )
        cargo_selection_embed.set_author(
            name=f'{self.user_obj['convoys'][0]['name']} | ${self.user_obj['convoys'][0]['money']:,}',
            icon_url=interaction.user.avatar.url
        )
        cargo_selection_embed = add_vehicle_stats_to_embed(cargo_selection_embed, self.selected_vehicle)

        cargo_selection_view = CargoSelectView(
            cargo_list=part_cargos_to_display,
            user_obj=self.user_obj,
            vendor_obj=self.vendor_obj,
            selected_vehicle=self.selected_vehicle,
            previous_embed=self.previous_embed,
            previous_view=self
        )

        await interaction.response.edit_message(embed=cargo_selection_embed, view=cargo_selection_view)


class CargoSelectView(discord.ui.View):
    def __init__(
            self,
            cargo_list,
            user_obj,
            vendor_obj,
            selected_vehicle,
            previous_embed,
            previous_view
    ):
        super().__init__()

        self.add_item(CargoSelect(
            cargo_list=cargo_list,
            user_obj=user_obj,
            vendor_obj=vendor_obj,
            selected_vehicle=selected_vehicle,
            previous_embed=previous_embed,
            previous_view=previous_view
        ))
    
    # @discord.ui.button(label='Repair wear and AP for all vehicles', style=discord.ButtonStyle.green, custom_id='repair_all')
    # async def repair_all_button(self, interaction: discord.Interaction, button: discord.Button):
    #     await interaction.response.send_message('this don\'t do nothin yet!')


class CargoSelect(discord.ui.Select):
    def __init__(self, cargo_list, user_obj, vendor_obj, selected_vehicle, previous_embed, previous_view):
        options=[
            discord.SelectOption(label=cargo['name'], value=cargo['cargo_id'])
            for cargo in cargo_list
        ]
        
        super().__init__(
            placeholder='Which part?',
            options=options,
            custom_id='select_part',
        )

        self.user_obj = user_obj
        self.vendor_obj = vendor_obj
        self.selected_vehicle = selected_vehicle
        self.previous_embed = previous_embed
        self.previous_view = previous_view


    async def callback(self, interaction: discord.Interaction):
        all_inventories = self.vendor_obj['cargo_inventory'] + self.user_obj['convoys'][0]['all_cargo']
        selected_part_cargo = next((
            c for c in all_inventories
            if c['cargo_id'] == self.values[0]
        ), None)
        selected_part = selected_part_cargo['part']

        current_part = None
        for category, part in self.selected_vehicle['parts'].items():
            if category == selected_part['category']:
                current_part = part
        if not current_part:
            current_part = None

        confirm_embed = discord.Embed(
            title=self.vendor_obj['name'],
            description=(
                f'## {self.selected_vehicle['name']}\n'
                # f'*{self.selected_vehicle['base_desc']}*\n'
                f'### Current Part\n'
                f'{format_part(current_part) if current_part else '- None'}\n'
                f'### New Part\n'
                f'{format_part(selected_part)}\n'
                f''
                # f'{vehicle_stats}\n'
                # f'### Parts Available for Purchase\n'
                # f'{displayable_cargo}'
                f'### Stats'
            )
        )
        confirm_embed.set_author(
            name=f'{self.user_obj['convoys'][0]['name']} | ${self.user_obj['convoys'][0]['money']:,}',
            icon_url=interaction.user.avatar.url
        )
        confirm_embed = add_vehicle_stats_to_embed(confirm_embed, self.selected_vehicle)

        install_confirm_view = InstallConfirmView(
            selected_part_cargo=selected_part_cargo,
            user_obj=self.user_obj,
            vendor_obj=self.vendor_obj,
            selected_vehicle=self.selected_vehicle,
            previous_embed=self.previous_embed,
            previous_view=self.previous_view
        )

        await interaction.response.edit_message(embed=confirm_embed, view=install_confirm_view)

class InstallConfirmView(discord.ui.View):
    def __init__(
            self,
            selected_part_cargo,
            user_obj,
            vendor_obj,
            selected_vehicle,
            previous_embed,
            previous_view
    ):
        super().__init__()

        self.selected_part_cargo = selected_part_cargo
        self.user_obj = user_obj
        self.vendor_obj = vendor_obj
        self.selected_vehicle = selected_vehicle
        self.previous_embed = previous_embed
        self.previous_view = previous_view

    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.blurple, custom_id='previous_menu', row=0)
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)

    @discord.ui.button(label='Install part', style=discord.ButtonStyle.green, custom_id='confirm_install_part', row=1)
    async def confirm_install_button(self, interaction: discord.Interaction, button: discord.Button):
        await api_calls.add_part(
            vendor_id=self.vendor_obj['vendor_id'],
            convoy_id=self.user_obj['convoys'][0]['convoy_id'],
            vehicle_id=self.selected_vehicle['vehicle_id'],
            part_cargo_id=self.selected_part_cargo['cargo_id']
        )

        await interaction.response.send_message('yay, you did it!')
        # await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)
