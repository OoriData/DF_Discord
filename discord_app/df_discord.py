# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED
import                                  os
import                                  asyncio
import                                  logging

import                                  discord
from discord                     import app_commands, HTTPException
from discord.ext                 import commands, tasks

from httpx                       import ConnectError, ConnectTimeout

from utiloori.ansi_color         import ansi_color

from discord_app                 import DF_DISCORD_LOGO as API_BANNER
from discord_app                 import (
    DF_GUILD_ID,
    DF_CHANNEL_ID, DF_WELCOME_CHANNEL_ID,
    WASTELANDER_ROLE, ALPHA_ROLE, BETA_ROLE,
    DF_GAMEPLAY_CHANNEL_1_ID, DF_GAMEPLAY_CHANNEL_2_ID, DF_GAMEPLAY_CHANNEL_3_ID,
    DF_LOGO_EMOJI,
)
from discord_app                 import TimeoutView, api_calls, DF_HELP
from discord_app.map_rendering   import add_map_to_embed
from discord_app.main_menu_menus import main_menu
from discord_app.dialogue_menus  import RespondToConvoyView

DF_API_HOST = os.environ['DF_API_HOST']
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
DISCORD_TOKEN = os.environ['DISCORD_TOKEN']

logger = logging.getLogger('DF_Discord')
logging.basicConfig(format='%(levelname)s:%(name)s: %(message)s', level=LOG_LEVEL)


class DesolateCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.message_history_limit = 1
        self.ephemeral = True
        self.cache_ready = asyncio.Event()

    @commands.Cog.listener()
    async def on_ready(self):
        """ Called when the bot is ready to start taking commands """
        await self.bot.tree.sync()

        logger.info(ansi_color(f'Bot/App: {self.bot.user.name}', 'purple'))
        logger.info(ansi_color(f'Welcome channel: #{self.bot.get_channel(DF_WELCOME_CHANNEL_ID).name}', 'purple'))
        logger.info(ansi_color(f'Gameplay channel 1: #{self.bot.get_channel(DF_GAMEPLAY_CHANNEL_1_ID).name}', 'purple'))
        logger.info(ansi_color(f'Gameplay channel 2: #{self.bot.get_channel(DF_GAMEPLAY_CHANNEL_2_ID).name}', 'purple'))
        logger.info(ansi_color(f'Gameplay channel 3: #{self.bot.get_channel(DF_GAMEPLAY_CHANNEL_3_ID).name}', 'purple'))
        logger.info(ansi_color(f'DF API: {DF_API_HOST}', 'purple'))

        logger.debug(ansi_color('Initializing settlements cache...', 'yellow'))
        self.settlements_cache = []
        self.df_map_obj = None
        while not self.df_map_obj:  # Retry logic for bootup
            try:
                self.df_map_obj = await api_calls.get_map()
            except ConnectError as e:
                logger.error(ansi_color(f'Error connecting to DF API: {e}', 'red'))
                await asyncio.sleep(3)  # Wait 3 seconds before trying again
            except ConnectTimeout as e:
                logger.error(ansi_color(f'Timeout connecting to DF API: {e}', 'red'))
                await asyncio.sleep(3)  # Wait 3 seconds before trying again

        for row in self.df_map_obj['tiles']:
            for sett in row:
                self.settlements_cache.extend(sett['settlements'])

        self.find_roles()

        logger.debug(ansi_color('Initializing users cache...', 'yellow'))
        self.df_users_cache = None
        self.update_user_cache.start()
        await self.cache_ready.wait()  # Wait until cache is initialized
        self.bot.add_view(TimeoutView(self.df_users_cache))

        df_guild = self.bot.get_guild(DF_GUILD_ID)
        logger.info(ansi_color(f'Discord guild: {df_guild.name}', 'purple'))
        df_notification_channel = self.bot.get_channel(DF_CHANNEL_ID)
        logger.info(ansi_color(f'Notifications channel: #{df_notification_channel.name}', 'purple'))

        logger.debug(ansi_color('Initializing notification loop...', 'yellow'))
        self.notifier.start()

        logger.log(1337, ansi_color('\n\n' + API_BANNER + '\n', 'green', 'black'))  # Display the cool DF banner

    def find_roles(self):
        """ Cache player roles """
        guild: discord.Guild = self.bot.get_guild(DF_GUILD_ID)
        self.wastelander_role, self.beta_role, self.alpha_role = None, None, None
        for role in guild.roles:
            if role.id == WASTELANDER_ROLE:
                self.wastelander_role = role
                logger.info(ansi_color(f'Player Role: {self.wastelander_role.name}', 'yellow'))
            if role.id == ALPHA_ROLE:
                self.alpha_role = role
                logger.info(ansi_color(f'Alpha Role: {self.alpha_role.name}', 'yellow'))
            if role.id == BETA_ROLE:
                self.beta_role = role
                logger.info(ansi_color(f'Beta Role: {self.beta_role.name}', 'yellow'))
            if self.wastelander_role and self.alpha_role and self.beta_role:  # Break early if all roles are found
                break

    async def mm(self, interaction: discord.Interaction):
        if not self.cache_ready.is_set():
            await interaction.response.send_message('-# Still booting up! Please try again in a few seconds.', ephemeral=True)
            return

        # ENTITLEMENTS CHECKER MECHANISM
        # user_entitlements = [entitlement async for entitlement in self.bot.entitlements(user=interaction.user)]
        # import pprint;pprint.pprint(user_entitlements)

        await main_menu(
            interaction=interaction,
            df_map=self.df_map_obj,
            user_cache=self.df_users_cache,
            edit=False
        )

    @app_commands.command(name='desolate-frontiers', description='Show the Desolate Frontiers main menu')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def desolate_frontiers_main_menu(self, interaction: discord.Interaction):
        await self.mm(interaction)

    @app_commands.command(name='df', description='A short alias to show the Desolate Frontiers main menu')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def df_main_menu(self, interaction: discord.Interaction):
        await self.mm(interaction)

    @app_commands.command(name='df-map', description='Show the full game map')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def df_map(self, interaction: discord.Interaction):
        if not self.cache_ready.is_set():
            await interaction.response.send_message('-# Still booting up! Please try again in a few seconds.', ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            map_embed = discord.Embed()
            map_embed, image_file = await add_map_to_embed(map_embed, map_obj=self.df_map_obj)

            map_embed.set_author(
                name=interaction.user.name,
                icon_url=interaction.user.avatar.url
            )
            map_embed.set_footer(text='Open this map in a browser to zoom in')

            await interaction.followup.send(embed=map_embed, file=image_file)

        except Exception as e:
            msg = f'something went wrong: {e}'
            await interaction.followup.send(msg)

    @app_commands.command(name='df-help', description='Show the help message')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def df_help(self, interaction: discord.Interaction):
        help_embed = discord.Embed(description=DF_HELP)
        await interaction.response.send_message(embed=help_embed, ephemeral=True)

    @app_commands.command(name='redeem_free_days', description="Redeem available free days")
    async def redeem_free_days(self, interaction: discord.Interaction):
        return  # Ignore commands
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """ Sends a welcome message to new members. """
        if member.bot:  # Ignore bots
            return

        welcome_channel: discord.guild.GuildChannel = self.bot.get_channel(DF_WELCOME_CHANNEL_ID)
        gameplay_channel_1: discord.guild.GuildChannel = self.bot.get_channel(DF_GAMEPLAY_CHANNEL_1_ID)
        gameplay_channel_2: discord.guild.GuildChannel = self.bot.get_channel(DF_GAMEPLAY_CHANNEL_2_ID)
        gameplay_channel_3: discord.guild.GuildChannel = self.bot.get_channel(DF_GAMEPLAY_CHANNEL_3_ID)

        welcome_embed = discord.Embed(description='\n'.join([
            f"## Welcome to the {DF_LOGO_EMOJI} Desolate Frontiers server, {member.mention}!",
            f"We're glad to have you! Use the `/desolate_frontiers` command in one of the gameplay channels ({gameplay_channel_1.jump_url}, {gameplay_channel_2.jump_url}, or {gameplay_channel_3.jump_url}) to get started.",
            "-# If you have any questions, feel free to message Choccy or any of the other yellow names! We're happy to help :)",
        ]))

        try:
            await welcome_channel.send(embed=welcome_embed)
            logger.info(ansi_color(f'Sent welcome message for {member.name} ({member.id}) to #{welcome_channel.name}', 'green'))
        except discord.Forbidden:  # This might occur if the bot doesn't have send permissions in the welcome_channel
            logger.warning(ansi_color(f'Could not send welcome message to #{welcome_channel.name}. Bot might lack permissions.', 'yellow'))
        except Exception as e:
            logger.error(ansi_color(f'Failed to send welcome message for {member.name} ({member.id}) to #{welcome_channel.name}: {e}', 'red'))

    @tasks.loop(minutes=5)
    async def update_user_cache(self):
        if not isinstance(self.df_users_cache, dict):  # Initialize cache if not already a dictionary
            self.df_users_cache = {}
            initial_setup = True
        else:
            initial_setup = False
            await asyncio.sleep(55)  # Sleep so the updating of the user cache doesn't overlap with the notifier

        guild: discord.Guild = self.bot.get_guild(DF_GUILD_ID)
        current_member_ids = {member.id for member in guild.members}  # Create a set of current members' IDs

        for cached_member_id in list(self.df_users_cache.keys()):  # Remove users from cache who are no longer in the guild
            if cached_member_id not in current_member_ids:
                del self.df_users_cache[cached_member_id]

        async def add_discord_roles(member):
            user_role_ids = [role.id for role in member.roles]
            if WASTELANDER_ROLE not in user_role_ids:
                try:
                    await member.add_roles(*[self.wastelander_role, self.beta_role])
                except HTTPException as e:
                    logger.error(ansi_color(f'Couldn\'t add Player/Beta roles to user {member.display_name}: {e}', 'red'))

        for member in guild.members:  # Update cache with current members
            if member.id in self.df_users_cache:  # If the member is already in the cache, skip the API call
                await add_discord_roles(member)  # Add Alpha/Beta roles
                continue

            try:  # Fetch user data via API only if they aren't in the cache
                user_dict = await api_calls.get_user_by_discord(member.id)
                self.df_users_cache[member.id] = user_dict['user_id']  # Use Discord ID as key, DF user ID as value
                await add_discord_roles(member)  # Add Alpha/Beta roles
                logger.debug(ansi_color(f'discord user {member.name} ({user_dict['user_id']}) added to df_users_cache', 'green'))
            except RuntimeError as e:  # Just skip unregistered users
                logger.debug(ansi_color(f'discord user {member.name} is not registered: {e}', 'cyan'))
                continue
            except Exception as e:
                logger.error(ansi_color(f'Error updating the cache for user {member.name}: {e}', 'red'))

        if initial_setup:
            logger.info(ansi_color('User cache initialization complete', 'green'))
            self.cache_ready.set()  # Signal that the cache is ready

    @tasks.loop(minutes=1)
    async def notifier(self):
        if isinstance(self.df_users_cache, dict):  # If the cache has been initialized
            guild: discord.Guild = self.bot.get_guild(DF_GUILD_ID)
            notification_channel: discord.guild.GuildChannel = self.bot.get_channel(DF_CHANNEL_ID)

            for discord_user_id, df_id in self.df_users_cache.items():
                discord_user = guild.get_member(discord_user_id)  # Fetch the Discord member using the ID

                if discord_user:
                    logger.debug(ansi_color(f'Fetching notifications for user {discord_user.name} (discord id: {discord_user.id}) (DF id: {df_id})', 'blue'))
                    try:  # Fetch unseen dialogue for the DF user
                        unseen_dialogue_dicts = await api_calls.get_unseen_dialogue_for_user(df_id)
                        logger.debug(ansi_color(f'Got {len(unseen_dialogue_dicts)} unseen dialogues', 'cyan'))

                        seen_this_round = set()  # Ephemeral deduplication per user per run

                        if unseen_dialogue_dicts:
                            notifications = []
                            for dialogue in unseen_dialogue_dicts:
                                for message in dialogue['messages']:
                                    content = message['content'].strip()

                                    if not content or content in seen_this_round:
                                        logger.error(ansi_color('Got duplicate notification, skipping...', 'red'))
                                        continue

                                    seen_this_round.add(content)
                                    notifications.append({
                                        'message_content': content,
                                        'message_metadata': dialogue
                                    })

                            embeds_to_send = []
                            for notification in notifications:
                                # embed = discord.Embed(description=notification[:4096])  # Embed descriptions can be a maximum of 4096 chars
                                embed = discord.Embed(description=notification['message_content'][:4096])  # Embed descriptions can be a maximum of 4096 chars
                                embed.set_author(
                                    name=discord_user.display_name,
                                    icon_url=discord_user.avatar.url
                                )

                                user_convoy_id = notification['message_metadata']['char_b_id']

                                # XXX: use (currently nonexistent) messsage metadata to decide what sort of button to attach to the notification (Respond to encounter, Go to convoy, etc)
                                # view = RespondToConvoyView(user_discord_id=discord_user_id, user_convoy_id=user_convoy_id, user_cache=self.df_users_cache)

                                # await notification_channel.send(embed=embed, view=view)

                                embeds_to_send.append(embed)

                            ping = f'<@{discord_user.id}>'
                            await notification_channel.send(content=ping, embeds=embeds_to_send)
                            logger.info(ansi_color(f'Sent {len(notifications)} notification(s) to user {discord_user.nick} ({discord_user.id})', 'green'))

                            # Mark dialogue as seen after sending notification
                            await api_calls.mark_dialogue_as_seen(df_id)

                    except Exception as e:
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
        await bot.add_cog(DesolateCog(bot))

    asyncio.run(startup())

    bot.run(bot.DISCORD_TOKEN)


if __name__ == '__main__':
    main()
