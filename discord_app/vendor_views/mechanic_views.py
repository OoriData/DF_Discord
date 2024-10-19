# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
import                                textwrap

import                                discord

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, df_embed_author
from discord_app.map_rendering import add_map_to_embed

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.getenv('DF_API_HOST')


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
    
    @discord.ui.button(label='Repair wear and AP for all vehicles', style=discord.ButtonStyle.green, custom_id='repair_all', disabled=True)
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

        mech_embed = discord.Embed()
        mech_embed = df_embed_author(mech_embed, self.user_obj['convoys'][0], interaction.user)
        mech_embed.description = '\n'.join([
            f'# {self.vendor_obj['name']}',
            f'## {selected_vehicle['name']}',
            f'*{selected_vehicle['base_desc']}*',
            '## Stats'
        ])
        mech_embed = df_embed_vehicle_stats(mech_embed, selected_vehicle)

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

    @discord.ui.button(label='Repair', style=discord.ButtonStyle.green, custom_id='repair', row=1, disabled=True)
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

        mech_vehicle_embed = discord.Embed()
        mech_vehicle_embed = df_embed_author(mech_vehicle_embed, self.user_obj['convoys'][0], interaction.user)
        mech_vehicle_embed.description = '\n'.join([
            f'## {self.selected_vehicle['name']}',
            f'*{self.selected_vehicle['base_desc']}*',
            '## Parts',
            displayable_vehicle_parts,
            '## Stats'
        ])
        mech_vehicle_embed = df_embed_vehicle_stats(mech_vehicle_embed, self.selected_vehicle)

        mech_vehicle_view = MechVehicleView(
            user_obj=self.user_obj,
            vendor_obj=self.vendor_obj,
            selected_vehicle=self.selected_vehicle,
            previous_embed=self.previous_embed,
            previous_view=self
        )

        await interaction.response.edit_message(embed=mech_vehicle_embed, view=mech_vehicle_view)

    @discord.ui.button(label='Strip', style=discord.ButtonStyle.red, custom_id='strip', row=1, disabled=True)
    async def strip_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.send_message('this don\'t do nothin yet!')

    @discord.ui.button(label='Recycle', style=discord.ButtonStyle.red, custom_id='recycle', row=1, disabled=True)
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

        # Disable the Convoy button if there's no cargo with a 'part' value
        if not any(cargo.get('part') for cargo in self.user_obj['convoys'][0]['all_cargo']):
            self.install_part_from_convoy_button.disabled = True

        # Disable the Vendor button if there's no cargo with a 'part' value
        if not any(cargo.get('part') for cargo in self.vendor_obj['cargo_inventory']):
            self.install_part_from_vendor_button.disabled = True
    
    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.blurple, custom_id='previous_menu', row=0)
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)

    async def handle_part_lists(self, interaction: discord.Interaction, cargo_source, is_vendor):
        part_cargos_to_display = []
        for cargo in cargo_source:
            if cargo.get('part'):
                try:
                    check_dict = await api_calls.check_part_compatibility(self.selected_vehicle['vehicle_id'], cargo['cargo_id'])
                    cargo['part'] = check_dict['part']
                    cargo['part']['installation_price'] = check_dict['installation_price']
                    
                    # Only assign kit_price if the cargo is from a vendor
                    if is_vendor:
                        cargo['part']['kit_price'] = cargo['base_price']
                    
                    part_cargos_to_display.append(cargo)
                except RuntimeError as e:
                    print(f'part does not fit: {e}')
                    continue
        
        part_list = []
        for cargo in part_cargos_to_display:
            part_list.append(format_part(cargo['part']))
        displayable_vehicle_parts = '\n'.join(part_list)

        cargo_selection_embed = discord.Embed()
        cargo_selection_embed = df_embed_author(cargo_selection_embed, self.user_obj['convoys'][0], interaction.user)
        cargo_selection_embed.description = '\n'.join([
            f'# {self.vendor_obj['name']}',
            f'## {self.selected_vehicle["name"]}',
            f'*{self.selected_vehicle["base_desc"]}*',
            '### Compatible parts available for purchase and installation' if is_vendor else '### Compatible parts available for installation',
            f'{displayable_vehicle_parts}',
            '### Stats'
        ])
        cargo_selection_embed = df_embed_vehicle_stats(cargo_selection_embed, self.selected_vehicle)

        cargo_selection_view = CargoSelectView(
            cargo_list=part_cargos_to_display,
            user_obj=self.user_obj,
            vendor_obj=self.vendor_obj,
            selected_vehicle=self.selected_vehicle,
            previous_embed=self.previous_embed,
            previous_view=self
        )

        await interaction.response.edit_message(embed=cargo_selection_embed, view=cargo_selection_view)

    @discord.ui.button(label='Install part from Convoy inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_convoy', row=1)
    async def install_part_from_convoy_button(self, interaction: discord.Interaction, button: discord.Button):
        convoy_cargo = self.user_obj['convoys'][0]['all_cargo']
        await self.handle_part_lists(interaction, convoy_cargo, is_vendor=False)

    @discord.ui.button(label='Install part from Vendor inventory', style=discord.ButtonStyle.blurple, custom_id='part_from_vendor', row=1)
    async def install_part_from_vendor_button(self, interaction: discord.Interaction, button: discord.Button):
        vendor_cargo = self.vendor_obj['cargo_inventory']
        await self.handle_part_lists(interaction, vendor_cargo, is_vendor=True)


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

        confirm_embed = discord.Embed()
        confirm_embed = df_embed_author(confirm_embed, self.user_obj['convoys'][0], interaction.user)
        confirm_embed.description = '\n'.join([
            f'# {self.vendor_obj['name']}',
            f'## {self.selected_vehicle['name']}\n'
            f'*{self.selected_vehicle['base_desc']}*\n'
            f'### Current Part\n'
            f'{format_part(current_part) if current_part else '- None'}\n'
            f'### New Part\n'
            f'{format_part(selected_part)}\n'
            '## Stats'
        ])
        confirm_embed = df_embed_vehicle_stats(confirm_embed, self.selected_vehicle, selected_part)

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
        convoy_after = await api_calls.add_part(
            vendor_id=self.vendor_obj['vendor_id'],
            convoy_id=self.user_obj['convoys'][0]['convoy_id'],
            vehicle_id=self.selected_vehicle['vehicle_id'],
            part_cargo_id=self.selected_part_cargo['cargo_id']
        )

        post_install_vehicle = next((
            v for v in convoy_after['vehicles']
            if v['vehicle_id'] == self.selected_vehicle['vehicle_id']
        ), None)

        post_install_embed = discord.Embed()
        post_install_embed = df_embed_author(post_install_embed, self.user_obj['convoys'][0], interaction.user)
        post_install_embed.description = '\n'.join([
            f'# {self.vendor_obj['name']}',
            f'## {post_install_vehicle['name']}',
            f'*{post_install_vehicle['base_desc']}*',
            '## Stats'
        ])
        post_install_embed = df_embed_vehicle_stats(post_install_embed, post_install_vehicle)

        post_install_view = PostInstallView(
            user_obj=self.user_obj,
            vendor_obj=self.vendor_obj,
            previous_embed=self.previous_embed,
            previous_view=self.previous_view
        )

        await interaction.response.send_message(embed=post_install_embed, view=post_install_view)


class PostInstallView(discord.ui.View):
    def __init__(self, user_obj, vendor_obj, previous_embed, previous_view):
        super().__init__()

        self.user_obj = user_obj
        self.vendor_obj = vendor_obj
        self.previous_embed = previous_embed
        self.previous_view = previous_view
    
    @discord.ui.button(label='⬅ Back', style=discord.ButtonStyle.blurple, custom_id='previous_menu', row=0)
    async def previous_menu_button(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.edit_message(embed=self.previous_embed, view=self.previous_view)
