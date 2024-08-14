# SPDX-FileCopyrightText: 2023-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                          os
import                          httpx
import                          asyncio
import                          logging
import                          textwrap
import                          discord
from datetime            import datetime, timezone
from io                  import BytesIO

from discord             import app_commands
from discord.ext         import commands
from utiloori.ansi_color import ansi_color

from discord_app                import vendor_views
from discord_app                import discord_timestamp
from discord_app.map_rendering  import render_map

API_SUCCESS_CODE = 200
API_UNPROCESSABLE_ENTITY_CODE = 422
DF_API_HOST = os.environ.get('DF_API_HOST')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

SETTLEMENTS = None  # Declared as none before being set on Discord bot startup by on_ready()

class Desolate_Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_history_limit = 1
        self.ephemeral = True

        # self.all_settlements = {} # maybe

    async def get_map(self):
        async with httpx.AsyncClient(verify=False) as client:
            map = await client.get(f'{DF_API_HOST}/map/get')
            
            if map.status_code != API_SUCCESS_CODE:
                msg = map.json()['detail']
                logging.log(msg=f'Something went wrong generating map: {msg}', level='INFO')
                return

            return map.json()

    async def get_user_by_discord(self, discord_id: int):
        '''Returns user info JSON object by calling API'''
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                f'{DF_API_HOST}/user/get_by_discord_id',
                params={'discord_id': discord_id}
            )
            return response.json()
        
    @commands.Cog.listener()
    async def on_ready(self):
        '''Called when the bot is ready to start taking commands'''
        global SETTLEMENTS
        SETTLEMENTS = []
        df_map = await self.get_map()

        for row in df_map['tiles']:
            for sett in row:
                SETTLEMENTS.extend(sett['settlements'])

    @app_commands.command(name='df-map', description='Show the full game map')
    async def get_df_map(self, interaction: discord.Interaction):
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    url=f'{DF_API_HOST}/map/get',
                    params={
                        # 'x_min': 1,
                        # 'x_max': 9,
                        # 'y_min': 20,
                        # 'y_max': 35
                    }
                )
                if response.status_code == API_UNPROCESSABLE_ENTITY_CODE:
                    logging.log(level='INFO', msg='Error: 422 Unprocessable')
                elif response.status_code == API_SUCCESS_CODE:
                    tiles = response.json()['tiles']
                    rendered_map = render_map(tiles)

                    # Create a BytesIO object to save the image in memory
                    with BytesIO() as image_binary:
                        rendered_map.save(image_binary, 'PNG')  # Save the image to the BytesIO object
                        image_binary.seek(0)  # Move the cursor to the beginning of the BytesIO object

                        # Send the image as a Discord file
                        await interaction.response.send_message(
                            file=discord.File(fp=image_binary, filename='map.png')
                        )

        except Exception as e:
            msg = f'something went wrong: {e}'
            await interaction.response.send_message(msg)
    
    @app_commands.command(name='df-register', description='Register a new Desolate Frontiers user')
    async def new_user(self, interaction: discord.Interaction):
        try:
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.post(
                    url=f'{DF_API_HOST}/user/new',
                    params={
                        'username': interaction.user.name,
                        'discord_id': interaction.user.id
                    }
                )
                if response.status_code == API_UNPROCESSABLE_ENTITY_CODE:
                    logging.log(level='INFO', msg='Error: 422 Unprocessable')
                elif response.status_code == API_SUCCESS_CODE:
                    # user_id display will go away in Beta
                    await interaction.response.send_message(textwrap.dedent(f'''
                        User **{interaction.user.name}** successfully created
                        user id: `{response.json()}`
                    '''))
                else:
                    await interaction.response.send_message(f'Failed to register user: User **{interaction.user.name}** already exists.')
        except Exception as e:
            msg = f'something went wrong: {e}'
            await interaction.response.send_message(msg)

    # i can't imagine this command seeing a whole lot of use, but added it anyway
    @app_commands.command(name='get-user', description='Get a user object based on its ID (probably an admin command or smth)')
    async def get_user(self, interaction: discord.Interaction, discord_id: str=None):
        if not discord_id:
            discord_id = interaction.user.id

        if discord_id.startswith('<@'):
            discord_id = discord_id.strip('<@>')  # allows users to @ individuals to get their profile info

        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                f'{DF_API_HOST}/user/get_by_discord_id',
                params={'discord_id': discord_id,}
            )
            print(response.json())
            if response.status_code == API_UNPROCESSABLE_ENTITY_CODE:
                await interaction.response.send_message('User doesn\'t exist in database, or invalid user ID was passed.', ephemeral=True)
                return
            user_info = response.json()
            await interaction.response.send_message(textwrap.dedent(f'''
                user id: `{user_info['user_id']}`
                username: `{user_info['username']}`
                discord id: `{user_info['discord_id']}`
                join date: `{user_info['join_date']}`
                convoys: `{', '.join([f'{convoy["name"]}' for convoy in user_info['convoys']])}`
            '''))

    @app_commands.command(name='vendors', description='Open the Desolate Frontiers buy menu')
    async def df_buy(self, interaction: discord.Interaction):
        async with httpx.AsyncClient(verify=False) as client:
            user_info = await client.get(
                f'{DF_API_HOST}/user/get_by_discord_id',
                params={'discord_id': interaction.user.id}
            )
            user_info = user_info.json()

            user_convoy = user_info['convoys'][0]

            tile_info = await client.get(
                f'{DF_API_HOST}/map/tile/get',
                params={'x': user_convoy['x'], 'y': user_convoy['y']}
            )
            tile_info = tile_info.json()

        # TODO: handle multiple settlements eventually
        node_embed = discord.Embed(
            title=f'{tile_info['settlements'][0]['name']} vendors and services',
        )
        for vendor in tile_info['settlements'][0]['vendors']:
            node_embed.add_field(
                name=vendor['name'],
                value=f'${vendor["money"]}'
            )
        node_embed.set_author(name=f'{user_info['convoys'][0]['name']} | ${user_info['convoys'][0]['money']}', icon_url=interaction.user.avatar.url)

        view=vendor_views.VendorMenuView(
            interaction=interaction,
            user_info=user_info,
            menu=tile_info['settlements'][0]['vendors'],
            menu_type='vendor'
        )
        await interaction.response.send_message(embed=node_embed, view=view)

    @app_commands.command(name='new-convoy', description='Create a new convoy')
    async def new_convoy(self, interaction: discord.Interaction, convoy_name: str=None):  # starting_location will be changed to a multi choice entry
        if not convoy_name:
            convoy_name = f'{interaction.user.name}\'s Convoy'

        async with httpx.AsyncClient(verify=False) as client:
            # grab user's DF id by their Discord ID
            user_info = await client.get(
                f'{DF_API_HOST}/user/get_by_discord_id',
                params={'discord_id': interaction.user.id}
            )

            # XXX: this should become a function
            if user_info.status_code != API_SUCCESS_CODE:
                await interaction.response.send_message(content=user_info.json()['detail'], ephemeral=True, delete_after=10)
                return
            
            user_info = user_info.json()
            user_id = user_info['user_id']

            # hit api post to create new convoy
            create_convoy_response = await client.post(
                f'{DF_API_HOST}/convoy/new',
                params={'user_id': user_id, 'convoy_name': convoy_name}
            )
            convoy_id = create_convoy_response.json()

            #hit api again to retrieve new convoy's information so that it can be displayed to user
            convoy_info = await client.get(
                f'{DF_API_HOST}/convoy/get',
                params={'convoy_id': convoy_id}
            )
            convoy_info = convoy_info.json()

        # give user pretty embed to look at
        # XXX: unfinished also turn me into a function
        convoy_embed = discord.Embed(
            color=discord.Color.green(),
            title=f'Welcome to the Desolate Frontiers, {interaction.user.name}.',
            description=textwrap.dedent('''
            **Convoy Information**
            ''')
        )

        # convoy_embed.add_field()
        convoy_embed.set_footer(text=f'Created on {convoy_info['creation_date']}')
        convoy_embed.set_author(
            name=f'{convoy_info['name']} | ${convoy_info['money']}',
            icon_url=interaction.user.avatar.url
        )
        await interaction.response.send_message(embed=convoy_embed)

    
    @app_commands.command(name='get-convoy', description='Bring up a menu with information pertaining to your convoys')
    async def my_convoys(self, interaction: discord.Interaction):
        async with httpx.AsyncClient(verify=False) as client:
            # First, get user ID from discord_id
            convoy_info = await self.get_user_by_discord(discord_id=interaction.user.id)

            # TODO: Remove the parameter from this command and make it easy for the user
            # Maybe just make a separate /convoys command that brings up a nice menu
            response = await client.get(
                f'{DF_API_HOST}/convoy/get',
                params={'convoy_id': convoy_info['convoys'][0]['convoy_id']}
            )

            if response.status_code != API_SUCCESS_CODE:
                msg = response.json()['detail']
                await interaction.response.send_message(content=msg, ephemeral=True, delete_after=10)
                return

            convoy_json = response.json()

            convoy_embed = discord.Embed(
                color=discord.Color.green(),
                title=f'{convoy_json['name']} Information'
            )
            if convoy_json['vehicles']:
                for item in convoy_json['vehicles']:
                    convoy_embed.add_field(name=item['name'], value=f'${item["value"]}')
            else:
                convoy_embed.description = 'No vehicles in convoy. Buy one by using /vendors and navigating one of your city\'s dealerships.'

            await interaction.response.send_message(embed=convoy_embed)

    # # XXX: im useful don't delete me
    # async def cities_autocomplete(  # TODO: move these all to a seperate file, or just to the top of this one
    #         self,
    #         interaction: discord.Interaction,
    #         current: str,
    # ) -> list[app_commands.Choice[str]]:
    #     setts_dict = {sett['name']: f'{sett['name']} is at coords ({sett['x']}, {sett['y']})' for sett in SETTLEMENTS}  # NA_NODES is in a list; convert it into a dict
    #     sett_names = [sett['name'] for sett in SETTLEMENTS]  # cities the users can select from
    #     choices = [
    #         app_commands.Choice(name=sett_name, value=setts_dict[sett_name])
    #         # for city in city_names if current.lower() in city.lower()
    #         for sett_name in sett_names if current.lower() in sett_name.lower()
    #     ]
    #     return choices[:25]

    @app_commands.command(name='send-convoy', description='Send your convoy on a journey to a given city.')
    async def send_convoy(self, interaction: discord.Interaction, x: int, y: int):
        async with httpx.AsyncClient(verify=False) as client:
            # Set up user info
            user_obj = await client.get(
                f'{DF_API_HOST}/user/get_by_discord_id',
                params={'discord_id': interaction.user.id}
            )

            user_obj = user_obj.json()

            convoy_obj = user_obj['convoys'][0]

            # Now, find routes that user can take to destination
            route = await client.post(
                f'{DF_API_HOST}/convoy/find_route',
                params={
                    'convoy_id': convoy_obj['convoy_id'],
                    'dest_x': x,
                    'dest_y': y
                }
            )
            if route.status_code != API_SUCCESS_CODE:
                msg = route.json()['detail']
                await interaction.response.send_message(content=msg, ephemeral=True, delete_after=10)
                return
            
            # alpha lol
            # print('json:')
            # print(route.json())
            route = route.json()[0]

            journey = await client.patch(
                f'{DF_API_HOST}/convoy/send',
                params={
                    'convoy_id': convoy_obj['convoy_id'],
                    'journey_id': route['journey']['journey_id']
                }
            )

            if journey.status_code != API_SUCCESS_CODE:
                msg = route.json()['detail']
                await interaction.response.send_message(content=msg, ephemeral=True, delete_after=10)
                return

            await interaction.response.send_message('Look at them gooooooo :D')

    # XXX: this command likes to throw errors (53005) ~~because discord.py is stupid~~, they're ignorable
    # @app_commands.command(name='get-node', description='Get a node object based on its ID')
    # @app_commands.autocomplete(city=cities_autocomplete)
    # async def get_node(self, interaction: discord.Interaction, city: str):
        # city_int = int(city)  # convert node id back into integer so api can handle it
        # async with httpx.AsyncClient(verify=False) as client:
        #     response = await client.get(
        #         f'{DF_API_HOST}/map/node/get',
        #         params={'node_id': city_int}
        #     )
        #     node_info = response.json()
        #     node_embed = discord.Embed(
        #         title=f'Info for {node_info['name']}',
        #         # XXX: pretty bad embed overall right now, but i wanna get to other stuff
        #         description=textwrap.dedent(f'''
        #             **Services**: {[vendor['name'] for vendor in node_info['vendors']]}
        #         ''')
        #     )  
        # await interaction.response.send_message(embed=node_embed)

        # await interaction.response.send_message(content=city)

def main():
    # Set up bot https://discord.com/developers/docs/topics/gateway#list-of-intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.invites = True

    bot = commands.Bot(
        command_prefix=['/'],
        intents=intents,
        description="Oori Bootlegged Chat Bot Framework"
    )

    @bot.event
    async def on_ready():
        '''
        Called when the bot is ready to start taking commands
        '''
        await bot.tree.sync()
        # logging stuff would go here if we had logging and config setup

    bot.DISCORD_TOKEN = DISCORD_TOKEN
    assert bot.DISCORD_TOKEN

    async def startup():
        await bot.add_cog(Desolate_Cog(bot))

    asyncio.run(startup())

    bot.run(bot.DISCORD_TOKEN)

if __name__ == '__main__':
    main()