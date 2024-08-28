# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                os
import                                asyncio
import                                logging
import                                textwrap
from typing                    import Optional
from datetime                  import datetime, timezone, timedelta
from io                        import BytesIO

import                                discord
from discord                   import app_commands
from discord.ext               import commands, tasks

from utiloori.ansi_color       import ansi_color

from discord_app               import api_calls, vendor_views, convoy_views, DF_HELP
from discord_app               import DF_DISCORD_LOGO as API_BANNER
from discord_app.map_rendering import add_map_to_embed

DF_API_HOST = os.environ.get('DF_API_HOST')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
DF_GUILD_ID = int(os.environ.get('DF_GUILD_ID'))
DF_CHANNEL_ID = int(os.environ.get('DF_CHANNEL_ID'))

logger = logging.getLogger('DF_Discord')
logging.basicConfig(format='%(levelname)s:%(name)s: %(message)s', level=LOG_LEVEL)

SETTLEMENTS_CACHE = None  # None until initialized 
DF_USERS_CACHE = None     # None until initialized 

class Desolate_Cog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.message_history_limit = 1
        self.ephemeral = True

        # self.all_settlements = {} # maybe
        
    @commands.Cog.listener()
    async def on_ready(self):
        'Called when the bot is ready to start taking commands'
        global SETTLEMENTS_CACHE
        global DF_USERS_CACHE


        # Startup:
        await self.bot.tree.sync()

        logger.info(ansi_color(f'DF API: {DF_API_HOST}', 'purple'))

        logger.debug(ansi_color('Initializing settlements cache...', 'yellow'))
        SETTLEMENTS_CACHE = []
        df_map = await api_calls.get_map()

        for row in df_map['tiles']:
            for sett in row:
                SETTLEMENTS_CACHE.extend(sett['settlements'])

        logger.debug(ansi_color('Initializing users cache...', 'yellow'))
        DF_USERS_CACHE = []
        guild: discord.Guild = self.bot.get_guild(DF_GUILD_ID)
        df_users = guild.members
        for df_user in df_users:
            try:
                user_dict = await api_calls.get_user_by_discord(df_user.id)
                DF_USERS_CACHE.append((user_dict['user_id'], df_user))
            except RuntimeError as e:
                logger.debug(f'user is not registered: {e}')
                continue

        df_guild = self.bot.get_guild(DF_GUILD_ID)
        logger.info(ansi_color(f'Discord guild: {df_guild.name}', 'purple'))
        df_notification_channel = self.bot.get_channel(DF_CHANNEL_ID)
        logger.info(ansi_color(f'Notifications channel: #{df_notification_channel.name}', 'purple'))
        
        logger.debug(ansi_color('Initializing notification loop...', 'yellow'))
        self.notifier.start()  

        logger.log(1337, ansi_color('\n\n' + API_BANNER + '\n', 'green', 'black'))  # Display the cool DF banner

        yield  # Shutdown:

    @app_commands.command(name='df-map', description='Show the full game map')
    async def df_map(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            embed = discord.Embed()
            embed, image_file = await add_map_to_embed(embed)

            embed.set_author(
                name=interaction.user.name,
                icon_url=interaction.user.avatar.url
            )
            await interaction.followup.send(embed=embed, file=image_file)

        except Exception as e:
            msg = f'something went wrong: {e}'
            await interaction.followup.send(msg)
    
    @app_commands.command(name='df-register', description='Register a new Desolate Frontiers user')
    async def df_register(self, interaction: discord.Interaction):
        global DF_USERS_CACHE
        try:
            new_user_id = await api_calls.new_user(interaction.user.name, interaction.user.id)
            await interaction.response.send_message(textwrap.dedent(f'''
                User **{interaction.user.name}** successfully created
                user id: `{new_user_id}`
            '''))
            DF_USERS_CACHE.append((new_user_id, interaction.user))
        except Exception as e:
            await interaction.response.send_message(e)

    # i can't imagine this command seeing a whole lot of use, but added it anyway
    # @app_commands.command(name='get-user', description='Get a user object based on its ID (probably an admin command or smth)')
    # async def get_user(self, interaction: discord.Interaction, discord_id: str=None):
    #     if not discord_id:
    #         discord_id = interaction.user.id

    #     if discord_id.startswith('<@'):
    #         discord_id = discord_id.strip('<@>')  # allows users to @ individuals to get their profile info

    #     user_info = await api_calls.get_user_by_discord(interaction.user.id)
        
    #     await interaction.response.send_message(textwrap.dedent(f'''
    #         user id: `{user_info['user_id']}`
    #         username: `{user_info['username']}`
    #         discord id: `{user_info['discord_id']}`
    #         join date: `{user_info['join_date']}`
    #         convoys: `{', '.join([f'{convoy['name']}' for convoy in user_info['convoys']])}`
    #     '''))

    @app_commands.command(name='df-vendors', description='Open the Desolate Frontiers buy menu')
    async def df_vendors(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_dict = await api_calls.get_user_by_discord(interaction.user.id)
        user_convoy = user_dict['convoys'][0]  # XXX: just assuming one convoy for now

        tile_dict = await api_calls.get_tile(user_convoy['x'], user_convoy['y'])

        # TODO: handle multiple settlements eventually
        # wtf does this mean
        if not tile_dict['settlements']:
            await interaction.response.send_message(content='There aint no settle ments here dawg!!!!!', ephemeral=True, delete_after=10)
            return

        settlement_embed = discord.Embed(
            title=f'{tile_dict['settlements'][0]['name']} vendors',
        )
        settlement_embed.description = '\n'.join([f'- {vendor['name']}' for vendor in tile_dict['settlements'][0]['vendors']])
        settlement_embed.description += '\n**Use the arrows to select the vendor you want to interact with**'
        convoy_balance = f'{user_dict['money']:,}'
        settlement_embed.set_author(name=f'{user_convoy['name']} | ${convoy_balance}', icon_url=interaction.user.avatar.url)

        view=vendor_views.VendorMenuView(
            interaction=interaction,
            user_info=user_dict,
            menu=tile_dict['settlements'][0]['vendors'],
            menu_type='vendor'
        )
        await interaction.followup.send(embed=settlement_embed, view=view)

    @app_commands.command(name='df-new-convoy', description='Create a new convoy')
    async def new_convoy(self, interaction: discord.Interaction, new_convoy_name: str=None):
        await interaction.response.defer()

        if not new_convoy_name:
            new_convoy_name = f'{interaction.user.name}\'s Convoy'

        user_dict = await api_calls.get_user_by_discord(interaction.user.id)

        # hit api post to create new convoy
        convoy_id = await api_calls.new_convoy(user_dict['user_id'], new_convoy_name)

        #hit api again to retrieve new convoy's information so that it can be displayed to user
        convoy_dict = await api_calls.get_convoy(convoy_id)

        convoy_embed, image_file = await convoy_views.make_convoy_embed(interaction, convoy_dict)

        await interaction.followup.send(embed=convoy_embed, file=image_file)

    
    @app_commands.command(name='df-convoy', description='Bring up a menu with information pertaining to your convoys')
    async def df_convoys(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # First, get user ID from discord_id
        user_dict = await api_calls.get_user_by_discord(interaction.user.id)

        convoy_dict = user_dict['convoys'][0]  # XXX: handle more convoys

        convoy_embed, image_file = await convoy_views.make_convoy_embed(interaction, convoy_dict)

        await interaction.followup.send(embed=convoy_embed, file=image_file)

    # XXX: im useful don't delete me
    async def settlements_autocomplete(  # TODO: move these all to a seperate file, or just to the top of this one
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> list[app_commands.Choice[str]]:
        # setts_dict = {sett['name']: f'{sett['name']} is at coords ({sett['x']}, {sett['y']})' for sett in SETTLEMENTS_CACHE}
        # sett_names = [sett['name'] for sett in SETTLEMENTS_CACHE]  # cities the users can select from

        # OK so what's going on here is that discord.py does not like when the Choice.value is not a string, even though `value` has a type hint of `any`
        # so what i'm gonna do instead is save the coordinates as a string, (example: '50,9'), and when it gets handled 
        setts_dict = {sett['name']: f'{sett['x']},{sett['y']}' for sett in SETTLEMENTS_CACHE}
        sett_names = [sett['name'] for sett in SETTLEMENTS_CACHE]  # cities the users can select from
        logger.debug(ansi_color(setts_dict, 'green'))
        choices = [
            app_commands.Choice(name=sett_name, value=setts_dict[sett_name])
            for sett_name in sett_names if current.lower() in sett_name.lower()
            # for city in city_names if current.lower() in city.lower()
        ][:25]
        return choices

    @app_commands.command(name='df-send-convoy', description='Send your convoy on a journey to a given city.')
    @app_commands.autocomplete(sett=settlements_autocomplete)
    async def send_convoy(self, interaction: discord.Interaction, sett: str):
        await interaction.response.defer()

        user_dict = await api_calls.get_user_by_discord(interaction.user.id)

        convoy_dict = user_dict['convoys'][0]  # XXX: handle more convoys

        dest_x, dest_y = map(int, sett.split(','))  # Get the destination coords out of the autocomplete

        # Now, find routes that user can take to destination
        try:
            route_choices = await api_calls.find_route(convoy_dict['convoy_id'], dest_x, dest_y)
        except RuntimeError as e:
            await interaction.followup.send(content=e, ephemeral=True)
            return
        prospective_journey_plus_misc = route_choices[0]

        convoy_embed, image_file = await convoy_views.make_convoy_embed(interaction, convoy_dict, prospective_journey_plus_misc)

        await interaction.followup.send(
            embed=convoy_embed,
            file=image_file,
            view=convoy_views.SendConvoyConfirmView(
                interaction=interaction,
                convoy_dict=convoy_dict,
                prospective_journey_dict=prospective_journey_plus_misc['journey']
            )
        )

    @app_commands.command(name='df-help', description='Show the help message')
    async def df_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(DF_HELP, ephemeral=True)

    @tasks.loop(minutes=1)
    async def notifier(self):
        global DF_USERS_CACHE

        notification_channel: discord.guild.GuildChannel = self.bot.get_channel(DF_CHANNEL_ID)

        for df_id, discord_user in DF_USERS_CACHE:
            try:
                unseen_dialogue_dicts = await api_calls.get_unseen_dialogue_for_user(df_id)

                if unseen_dialogue_dicts:
                    ping_deets = [
                        message['content']
                        for dialogue in unseen_dialogue_dicts
                        for message in dialogue['messages']
                    ]
                    ping = '\n- '
                    ping +='\n- '.join(ping_deets)
                    ping += f'\n<@{discord_user.id}>'

                    await notification_channel.send(ping)
                    logger.info(ansi_color(f'sent notification to user {discord_user.nick} ({discord_user.id})', 'green'))

                    await api_calls.mark_dialogue_as_seen(df_id)
            except RuntimeError as e:
                logger.error(f'Error fetching notifications: {e}')
                continue


def main():
    # Set up bot https://discord.com/developers/docs/topics/gateway#list-of-intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.invites = True

    bot = commands.Bot(
        command_prefix=['/'],
        intents=intents,
        description='Desolate Frontiers Discord Client'
    )

    bot.DISCORD_TOKEN = DISCORD_TOKEN
    assert bot.DISCORD_TOKEN

    async def startup():
        await bot.add_cog(Desolate_Cog(bot))

    asyncio.run(startup())

    bot.run(bot.DISCORD_TOKEN)


if __name__ == '__main__':
    main()
