# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                 os
import                                 asyncio
import                                 logging
import                                 textwrap
from typing                     import Optional
from datetime                   import datetime, timezone, timedelta
from io                         import BytesIO

import                                 discord
import                                 httpx
from discord                    import app_commands
from discord.ext                import commands, tasks

from utiloori.ansi_color        import ansi_color

from discord_app                import DF_DISCORD_LOGO as API_BANNER
from discord_app                import api_calls, convoy_views, DF_HELP, df_embed_author
from discord_app.map_rendering  import add_map_to_embed
from discord_app.vendor_views   import vendor_views
from discord_app.main_menu_views import main_menu
from discord_app.df_state       import DFState

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

    @commands.Cog.listener()
    async def on_ready(self):
        'Called when the bot is ready to start taking commands'
        global SETTLEMENTS_CACHE

        await self.bot.tree.sync()

        logger.info(ansi_color(f'DF API: {DF_API_HOST}', 'purple'))

        logger.debug(ansi_color('Initializing settlements cache...', 'yellow'))
        SETTLEMENTS_CACHE = []

        df_map = await api_calls.get_map()
        for row in df_map['tiles']:
            for sett in row:
                SETTLEMENTS_CACHE.extend(sett['settlements'])

        logger.debug(ansi_color('Initializing users cache...', 'yellow'))
        self.update_user_cache.start()

        df_guild = self.bot.get_guild(DF_GUILD_ID)
        logger.info(ansi_color(f'Discord guild: {df_guild.name}', 'purple'))
        df_notification_channel = self.bot.get_channel(DF_CHANNEL_ID)
        logger.info(ansi_color(f'Notifications channel: #{df_notification_channel.name}', 'purple'))
        
        logger.debug(ansi_color('Initializing notification loop...', 'yellow'))
        self.notifier.start()

        logger.log(1337, ansi_color('\n\n' + API_BANNER + '\n', 'green', 'black'))  # Display the cool DF banner

    @app_commands.command(name='desolate-frontiers', description='Desolate Frontiers main menu')
    async def df_main_menu(self, interaction: discord.Interaction):
        await main_menu(interaction=interaction, edit=False)
        
    @app_commands.command(name='df-map', description='Show the full game map')
    async def df_map(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            map_embed = discord.Embed()
            map_embed, image_file = await add_map_to_embed(map_embed)

            map_embed.set_author(
                name=interaction.user.name,
                icon_url=interaction.user.avatar.url
            )

            await interaction.followup.send(embed=map_embed, file=image_file)

        except Exception as e:
            msg = f'something went wrong: {e}'
            await interaction.followup.send(msg)

    # @app_commands.command(name='df-register', description='Register a new Desolate Frontiers user')
    # async def df_register(self, interaction: discord.Interaction):
    #     global DF_USERS_CACHE
    #     try:
    #         new_user_id = await api_calls.new_user(interaction.user.name, interaction.user.id)
    #         await interaction.response.send_message(textwrap.dedent(f'''
    #             User **{interaction.user.name}** successfully created
    #             user id: `{new_user_id}`
    #         '''))
    #         DF_USERS_CACHE.append((new_user_id, interaction.user))
    #     except Exception as e:
    #         await interaction.response.send_message(e)

    @app_commands.command(name='df-vendors', description='Open the Desolate Frontiers buy menu')
    async def df_vendors(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_dict = await api_calls.get_user_by_discord(interaction.user.id)
        user_convoy = user_dict['convoys'][0]  # XXX: just assuming one convoy for now

        tile_dict = await api_calls.get_tile(user_convoy['x'], user_convoy['y'])

        # TODO: handle multiple settlements eventually

        if not tile_dict['settlements']:
            await interaction.response.send_message(content='There aint no settle ments here dawg!!!!!', ephemeral=True, delete_after=10)
            return

        settlement_embed = discord.Embed(title=f'{tile_dict['settlements'][0]['name']} vendors',)
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

        await interaction.followup.send(
            embed=convoy_embed,
            file=image_file,
            view=convoy_views.ConvoyView(
                interaction=interaction,
                convoy_dict=convoy_dict,
                previous_embed=convoy_embed,
                previous_attachments=[image_file]
            )
        )

    async def settlements_autocomplete(  # TODO: move these all to a seperate file, or just to the top of this one
            self,
            interaction: discord.Interaction,
            current: str,
    ) -> list[app_commands.Choice[str]]:
        # setts_dict = {sett['name']: f'{sett['name']} is at coords ({sett['x']}, {sett['y']})' for sett in SETTLEMENTS_CACHE}
        # sett_names = [sett['name'] for sett in SETTLEMENTS_CACHE]  # cities the users can select from

        # discord.py does not like when Choice.value is not a string, even though `value` has a type hint of `any`
        # instead, save the coordinates as a string, (example: '50,9'), and when it gets handled the program will revert the numbers in the string back to int
        coords_dict = {sett['name']: f'{sett['x']},{sett['y']}' for sett in SETTLEMENTS_CACHE}
        sett_names = [sett['name'] for sett in SETTLEMENTS_CACHE]  # cities the users can select from

        logger.debug(ansi_color(coords_dict, 'green'))

        choices = [
            app_commands.Choice(name=sett_name, value=coords_dict[sett_name])
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
            view = convoy_views.SendConvoyConfirmView(
                interaction=interaction,
                convoy_dict=convoy_dict,
                prospective_journey_dict=prospective_journey_plus_misc['journey']
            )
        )

    @app_commands.command(name='df-help', description='Show the help message')
    async def df_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(DF_HELP, ephemeral=True)

    @tasks.loop(minutes=5)
    async def update_user_cache(self):
        asyncio.sleep(55)
        
        global DF_USERS_CACHE
        if not isinstance(DF_USERS_CACHE, dict):  # Initialize cache if not already a dictionary
            DF_USERS_CACHE = {}

        guild: discord.Guild = self.bot.get_guild(DF_GUILD_ID)
        current_member_ids = set(member.id for member in guild.members)  # Create a set of current members' IDs

        for cached_member_id in list(DF_USERS_CACHE.keys()):  # Remove users from cache who are no longer in the guild
            if cached_member_id not in current_member_ids:
                del DF_USERS_CACHE[cached_member_id]

        for member in guild.members:  # Update cache with current members
            if member.id in DF_USERS_CACHE:  # If the member is already in the cache, skip the API call
                continue
            
            try:  # Fetch user data via API only if they aren't in the cache
                user_dict = await api_calls.get_user_by_discord(member.id)
                DF_USERS_CACHE[member.id] = user_dict['user_id']  # Use Discord ID as key, DF user ID as value
                logger.info(ansi_color(f'discord user {member.name} ({user_dict['user_id']}) has been added to DF_USERS_CACHE', 'green'))
            except RuntimeError as e:  # Just skip unregistered users
                logger.info(ansi_color(f'discord user {member.name} is not registered: {e}', 'cyan'))
                continue

    @tasks.loop(minutes=1)
    async def notifier(self):
        global DF_USERS_CACHE

        notification_channel: discord.guild.GuildChannel = self.bot.get_channel(DF_CHANNEL_ID)
        guild: discord.Guild = self.bot.get_guild(DF_GUILD_ID)

        for discord_user_id, df_id in DF_USERS_CACHE.items():
            discord_user = guild.get_member(discord_user_id)  # Fetch the Discord member using the ID

            if discord_user:
                logger.info(ansi_color(f'Fetching notifications for user {discord_user.name} (discord id: {discord_user.id}) (DF id: {df_id})', 'blue'))
                try:
                    # Fetch unseen dialogue for the DF user
                    unseen_dialogue_dicts = await api_calls.get_unseen_dialogue_for_user(df_id)
                    logger.info(ansi_color(f'Got {len(unseen_dialogue_dicts)} unseen dialogues', 'cyan'))

                    if unseen_dialogue_dicts:
                        ping = f'<@{discord_user.id}>'
                        await notification_channel.send(ping)

                        # Compile message content from unseen dialogues
                        notifications = [
                            message['content']
                            for dialogue in unseen_dialogue_dicts
                            for message in dialogue['messages']
                        ]

                        for notification in notifications:
                            embed = discord.Embed(description=notification[:4096])  # Embed descriptions can be a maximum of 4096 chars
                            await notification_channel.send(embed=embed)

                        logger.info(ansi_color(f'Sent {len(notifications)} notification(s) to user {discord_user.nick} ({discord_user.id})', 'green'))

                        # Mark dialogue as seen after sending notification
                        await api_calls.mark_dialogue_as_seen(df_id)

                except RuntimeError as e:
                    logger.error(ansi_color(f'Error fetching notifications: {e}', 'red'))
                    continue
            else:
                logger.error(ansi_color(f'Discord user with ID {discord_user_id} not found in guild', 'red'))


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
