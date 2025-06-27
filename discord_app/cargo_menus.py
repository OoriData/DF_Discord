# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
from __future__                import annotations
import                                os
from datetime import                  datetime, timezone, timedelta
from typing                    import Optional

import                                discord

from discord_app               import api_calls, handle_timeout, discord_timestamp, df_embed_author, validate_interaction, get_vehicle_emoji
from discord_app.map_rendering import add_map_to_embed
import discord_app.nav_menus
import discord_app.convoy_menus

from discord_app.df_state      import DFState

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')


async def cargo_menu(df_state: DFState):
    df_state.append_menu_to_back_stack(func=cargo_menu)  # Add this menu to the back stack

    carrier_vehicle = next((
        v for v in df_state.convoy_obj['vehicles']
        if v['vehicle_id'] == df_state.cargo_obj['vehicle_id']
    ), None)

    if df_state.cargo_obj['recipient']:
        recipient_vendor_obj = await api_calls.get_vendor(vendor_id=df_state.cargo_obj['recipient'])
    else:
        recipient_vendor_obj = {}

    cargo_embed = discord.Embed()
    cargo_embed = df_embed_author(cargo_embed, df_state)
    cargo_embed.description = '\n'.join([
        f'## {df_state.cargo_obj['name']}',
        '- $$$',
        f'  - Unit Price: **${df_state.cargo_obj['unit_price']}**',
        f'  - Recipient: **{recipient_vendor_obj.get('name')}**',
        f'  - Delivery Reward: **${df_state.cargo_obj['delivery_reward']}**',
        '- misc',
        f'  - Carrier Vehicle: **{carrier_vehicle['name']}**',
        f'  - Intrinsic_part_id: **{df_state.cargo_obj['intrinsic_part_id']}**',
        f'  - Capacity: **{df_state.cargo_obj['capacity']} L**',
        f'  - Quantity: **{df_state.cargo_obj['quantity']}**',
        f'  - Total Volume: **{df_state.cargo_obj['volume']}** L',
        f'  - Total Weight: **{df_state.cargo_obj['weight']}** kg',
    ])

    cargo_view = ConvoyCargoView(
        df_state=df_state,
        recipient_vendor_obj=recipient_vendor_obj
    )

    await df_state.interaction.response.edit_message(embed=cargo_embed, view=cargo_view, attachments=[])

class ConvoyCargoView(discord.ui.View):
    """ Overarching convoy button menu """
    def __init__(self, df_state: DFState, recipient_vendor_obj: dict = None):
        self.df_state = df_state
        super().__init__(timeout=600)

        discord_app.nav_menus.add_nav_buttons(self, self.df_state)

        self.add_item(MoveCargoVehicleSelect(self.df_state))

        if recipient_vendor_obj:
            self.add_item(MapButton(self.df_state, recipient_vendor_obj))

    async def on_timeout(self):
        await handle_timeout(self.df_state)

class MoveCargoVehicleSelect(discord.ui.Select):
    def __init__(self, df_state: DFState, row: int=2):
        self.df_state = df_state

        if self.df_state.cargo_obj['intrinsic_part_id']:
            disabled = True
        else:
            disabled = False

        placeholder = 'Select vehicle to move cargo into'
        options = [
            discord.SelectOption(
                label=vehicle['name'],
                value=vehicle['vehicle_id'],
                emoji=get_vehicle_emoji(vehicle['shape'])
            )
            for vehicle in self.df_state.convoy_obj['vehicles']
            if vehicle['vehicle_id'] != self.df_state.cargo_obj['vehicle_id']
        ]

        if not options:
            placeholder = 'No valid vehicles to move cargo into'
            disabled = True
            options = [discord.SelectOption(label='none', value='none')]

        sorted_options = sorted(options, key=lambda opt: opt.label.lower())  # Sort options by first letter of label alphabetically
        super().__init__(
            placeholder=placeholder,
            options=sorted_options,
            custom_id='select_vehicle',
            disabled=disabled,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        dest_vehicle = next((
            v for v in self.df_state.convoy_obj['vehicles']
            if v['vehicle_id'] == self.values[0]
        ), None)
        try:
            self.df_state.convoy_obj = await api_calls.move_cargo(
                self.df_state.convoy_obj['convoy_id'],
                self.df_state.cargo_obj['cargo_id'],
                dest_vehicle['vehicle_id']
            )
        except RuntimeError as e:
            await interaction.response.send_message(content=e, ephemeral=True)
            return

        await discord_app.convoy_menus.convoy_menu(self.df_state)

class MapButton(discord.ui.Button):
    def __init__(self, df_state: DFState, recipient_obj: dict, row: int=1):
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label='Map to Recipient',
            custom_id='map_button',
            emoji='🗺️',
            row=row
        )
        self.df_state = df_state
        self.recipient_obj = recipient_obj

    async def callback(self, interaction: discord.Interaction):
        if not await validate_interaction(interaction=interaction, df_state=self.df_state):
            return
        self.df_state.interaction = interaction

        await interaction.response.defer()

        convoy_x = self.df_state.convoy_obj['x']
        convoy_y = self.df_state.convoy_obj['y']

        recipient_x = self.recipient_obj['x']
        recipient_y = self.recipient_obj['y']

        embed = discord.Embed(
            description='\n'.join([
                f'## {self.df_state.cargo_obj['name']}',
                '🟨 - Your convoy\'s location',
                '🟦 - Recipient vendor\'s location',
            ])
        )

        map_embed, image_file = await add_map_to_embed(
            embed=embed,
            highlights=[(convoy_x, convoy_y)],
            lowlights=[(recipient_x, recipient_y)],
            map_obj=self.df_state.map_obj
        )

        map_embed.set_footer(text='Your interaction is still up above, just scroll up or dismiss this message to return to it.')

        await interaction.followup.send(
            embed=map_embed,
            file=image_file,
            ephemeral=True
        )


def format_part(part_cargo: dict, verbose: bool=True):
    """ Format vehicle part data into markdown string with proper list formatting. """
    if isinstance(part_cargo, list):
        parts = part_cargo
    elif part_cargo.get('cargo_id'):
        parts = part_cargo['parts']
    else:
        parts = [part_cargo]

    part_strs = []
    for part in parts:
        ac_add = part.get('ac_add')
        efficiency_add = part.get('efficiency_add')
        top_speed_add = part.get('top_speed_add')
        offroad_capability_add = part.get('offroad_capability_add')
        cargo_capacity_add = part.get('cargo_capacity_add')
        weight_capacity_add = part.get('weight_capacity_add')
        weight_capacity_multi = part.get('weight_capacity_multi')

        cargo_cubic_feet = round(cargo_capacity_add * 0.0353147) if cargo_capacity_add else None
        weight_lbs = round(weight_capacity_add * 2.20462) if weight_capacity_add else None

        horsepower = round(part['kw'] * 1.34102) if part.get('kw') else None
        lbft = round(part['nm'] * 0.7376) if part.get('nm') else None
        fuel_gal = round(part['fuel_capacity'] * 0.264172) if part.get('fuel_capacity') else None
        water_gal = round(part['water_capacity'] * 0.264172) if part.get('water_capacity') else None
        diameter_in = round(part['diameter'] * 39.3701) if part.get('diameter') else None

        slot = part['slot'].replace('_', ' ').capitalize() if part['slot'] != 'ice' else 'ICE'
        
        # Build requirements list separately
        requirements_text = ''
        if verbose and part.get('requirements'):
            requirements = [
                f'- {req.replace('_', ' ').capitalize()}' if req != 'ice' else '- ICE'
                for req in part.get('requirements')
            ]
            requirements_text = '  - Requirements:\n    ' + '\n    '.join(requirements)
            
        coupling = part['coupling'].replace('_', ' ').capitalize() if part['coupling'] else None

        lines = []
        
        # Start with part name and handle OE marking
        if part.get('oe'):
            lines.append(f'- **{part['name']}** (Original Equipment)')
        else:
            lines.append(f'- **{part['name']}**')
            
        # Add slot and wear points
        lines.append(f'  - Slot: **{slot}**')
        if part.get('wp'):
            lines.append(f'  - {part['wp']} / 10 wear points')

        # Add stats
        if ac_add:
            lines.append(f'  - AC 🛡️: **{ac_add:+.0f}**')
        if efficiency_add:
            lines.append(f'  - Efficiency 🌿: **{efficiency_add:+.0f}**')
        if top_speed_add:
            lines.append(f'  - Top speed 🚀: **{top_speed_add:+.0f}**')
        if offroad_capability_add:
            lines.append(f'  - Offroad capability 🥾: **{offroad_capability_add:+.0f}**')
        if cargo_capacity_add:
            if verbose:
                lines.append(f'  - Cargo capacity add 📦: **{cargo_capacity_add:+.0f}** L ({cargo_cubic_feet:+} ft³)')
            else:
                lines.append(f'  - Cargo capacity add 📦: **{cargo_capacity_add:+.0f}** L')
        if weight_capacity_add:
            if verbose:
                lines.append(f'  - Weight capacity add 🏋️: **{weight_capacity_add:+.0f}** kg ({weight_lbs:+} lbs)')
            else:
                lines.append(f'  - Weight capacity add 🏋️: **{weight_capacity_add:+.0f}** kg')
        if weight_capacity_multi:
            lines.append(f'  - Weight capacity multi {'💪' if verbose else '🏋️'}: **{weight_capacity_multi:+.0f}**')

        # Add verbose-only information
        if verbose:
            if part.get('weight_class'):
                lines.append(f'  - Minimum weight class: **{part['weight_class']}**')
            
            # Add requirements as a properly formatted sublist
            if requirements_text:
                lines.append(requirements_text)
                
            # Add technical specs
            if part.get('kw'):
                lines.append(f'  - **{part['kw']}** kW (**{horsepower}** hp)')
            if part.get('nm'):
                lines.append(f'  - **{part['nm']}** N·m (**{lbft}** lb·ft)')
            if part.get('fuel_capacity'):
                lines.append(f'  - **{part['fuel_capacity']}** L ⛽️ (**{fuel_gal}** gal)')
            if part.get('kwh_capacity'):
                lines.append(f'  - **{part['kwh_capacity']}** kWh 🔋')
            if part.get('energy_density'):
                lines.append(f'  - **{part['energy_density']}** Wh/kg')
            if part.get('water_capacity'):
                lines.append(f'  - **{part['water_capacity']}** L 💧 (**{water_gal}** gal)')
            if coupling:
                lines.append(f'  - **{coupling}**')
            if part.get('driven_axles'):
                lines.append(f'  - **{part['driven_axles']}** axles driven')
            if part.get('diameter'):
                lines.append(f'  - **{part['diameter']}**m ({diameter_in} in) diameter')
                
            # Add flags
            if part.get('critical'):
                lines.append('  - **Critical**')
            if part.get('removable'):
                lines.append('  - **Removable** ↩️')
            if part.get('salvagable'):
                lines.append('  - **Salvagable** ♻️')
            if part.get('bolt_on'):
                lines.append('  - **Bolt-on**')
                
            # Add description and pricing as separate paragraphs with proper indentation
            if part.get('description'):
                lines.append(f'  - *{part['description']}*')
            
            # Pricing info
            if part.get('value'):
                lines.append(f'  - Part value: **${part['value']:,.0f}**')
            if part.get('installation_price') is not None:
                lines.append(f'    - **Installation price: ${part['installation_price']:,.0f}**')
        else:
            # Only add these items in non-verbose mode
            if part.get('fuel_capacity'):
                lines.append(f'  - **{part['fuel_capacity']}** L ⛽️')
            if part.get('kwh_capacity'):
                lines.append(f'  - **{part['kwh_capacity']}** kWh 🔋')
            if part.get('water_capacity'):
                lines.append(f'  - **{part['water_capacity']}** L 💧')
            if part.get('removable'):
                lines.append('  - **Removable** ↩️')
            if part.get('salvagable'):
                lines.append('  - **Salvagable** ♻️')

        # Join this part's lines with proper newlines
        part_strs.append('\n'.join(lines))

    # Add an extra newline between parts for better separation
    return '\n'.join(part_strs)
