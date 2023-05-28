from typing import Dict, Optional

from discord import DiscordException, HTTPException, Interaction, Member
from discord.app_commands import command, Command, CheckFailure, Group, guild_only
from discord.ext.commands import Bot, Cog

from goldenballs.game import Game, Player
from goldenballs.messages import get_msg


UserId = int
GBPlayer = Player[Member]
GBGame = Game[GBPlayer]


class GoldenBalls(Cog):
    BOT_ADMINS = [
        569648667108179968
    ]

    # Discord bot instance
    bot: Bot

    # Player instances for each discord user
    players: Dict[UserId, GBPlayer]

    # Active games in each channel
    games: Dict[int, GBGame]

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.games = {}

    def _get_player(self, member: Member) -> Player:
        """Get the player instance for a discord member"""

        # Register player if needed
        if member.id not in self.players:
            self.players[member.id] = Player(member.nick or member.name, member.id, member)

        return self.players[member.id]

    async def _flush_message_queue(self, ctx: Interaction, game: GBGame):
        """Outputs all queued messages to discord"""

        # Handle channel messages
        while msg := game.get_channel_message():
            await ctx.channel.send(msg)

        # Handle dms
        for player in game.get_dm_subjects():
            while dm := game.get_dm(player):
                member: Member = player.context
                try:
                    await member.create_dm()
                    await member.send(dm)
                except HTTPException as e:
                    await ctx.channel.send(get_msg("dm.err.fail", name=player.get_name(), exception=e))

    async def _get_game(self, ctx: Interaction) -> Optional[GBGame]:
        """Gets the game for an interaction, if it exists"""

        game = self.games.get(ctx.channel_id)
        if game is None:
            await ctx.response.send_message(get_msg("channel.err.no_game"), ephemeral=True)

        return game

    async def _handle_game_update(self, ctx: Interaction):
        """Handles the changes to the game in a channel"""

        # Try get game
        game = await self._get_game(ctx)
        if game is None:
            return

        # Remove game if finished
        if game.is_finished():
            del self.games[ctx.channel_id]

        # Output queued messages
        await self._flush_message_queue(ctx, game)
    
    async def _require_authority(self, ctx: Interaction, game: Game) -> Optional[str]:
        if not (
            game.host == self._get_player(ctx.user) or
            ctx.user.guild_permissions.administrator or
            ctx.user.id in self.BOT_ADMINS
        ):
            return get_msg("command.err.no_perms")

    @command(description=get_msg("command.start.description"))
    @guild_only()
    async def start(self, ctx: Interaction):
        """Starts a game in a channel, if it's free"""

        # Get target user
        user = ctx.user

        # Check if game can be started
        if ctx.channel_id in self.games:
            await ctx.response.send_message(get_msg("channel.err.game"), ephemeral=True)
            return

        # Try start game
        host = self._get_player(user)
        game, message = Game.start_game(host)
        if game is not None:
            self.games[ctx.channel_id] = game
        await ctx.response.send_message(message, ephemeral=(game is None))
        await self._handle_game_update(ctx)

    @command(description=get_msg("command.join.description"))
    @guild_only()
    async def join(self, ctx: Interaction):
        """Joins the game in the channel, if it exists and the user is free"""

        # Get target user
        user = ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Try join game
        player = self._get_player(user)
        msg = game.on_join(player)
        await ctx.response.send_message(msg, ephemeral=(not player.is_busy()))
        await self._handle_game_update(ctx)

    @command(description=get_msg("command.vote.description"))
    @guild_only()
    async def vote(self, ctx: Interaction, target: Member):
        """Round 1 & 2 - votes for the player to remove"""

        # Get target user
        user = ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of vote
        player = self._get_player(user)
        target_player = self._get_player(target)
        msg = game.on_vote(player, target_player)
        await ctx.response.send_message(msg, ephemeral=True)
        await self._handle_game_update(ctx)
    
    @command(description=get_msg("command.view_balls.description"))
    @guild_only()
    async def view_balls(self, ctx: Interaction):
        """Round 1 & 2 - view your hidden balls"""

        # Get target user
        user = ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of vote
        player = self._get_player(user)
        msg = game.on_view_balls(player)
        await ctx.response.send_message(msg, ephemeral=True)
        await self._handle_game_update(ctx)

    @command(description=get_msg("command.pick.description"))
    @guild_only()
    async def pick(self, ctx: Interaction, ball_id: int):
        """Round 3 - picks a ball"""

        # Get target user
        user = ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of vote
        player = self._get_player(user)
        msg = game.on_pick(player, ball_id)
        await ctx.response.send_message(msg)
        await self._handle_game_update(ctx)

    @command(description=get_msg("command.split.description"))
    @guild_only()
    async def split(self, ctx: Interaction):
        """Round 4 - chooses to split the prize"""

        # Get target user
        user = ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of action
        player = self._get_player(user)
        msg = game.on_split(player)
        await ctx.response.send_message(msg, ephemeral=True)
        await self._handle_game_update(ctx)

    @command(description=get_msg("command.steal.description"))
    @guild_only()
    async def steal(self, ctx: Interaction):
        """Round 4 - chooses to steal the prize"""

        # Get target user
        user = ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of action
        player = self._get_player(user)
        msg = game.on_steal(player)
        await ctx.response.send_message(msg, ephemeral=True)
        await self._handle_game_update(ctx)

    @command(description=get_msg("command.leave.description"))
    @guild_only()
    async def leave(self, ctx: Interaction):
        """Leaves your current game, if in one"""

        # Get target user
        user = ctx.user

        # Check if player is in a game
        player = self._get_player(user)
        game = player.current_game
        if game is None:
            await ctx.response.send_message(get_msg("user.err.no_game"))
            return

        # Notify game of action
        msg = game.on_leave(player)
        await ctx.response.send_message(msg)
        await self._handle_game_update(ctx)

    @command(description=get_msg("command.kick.description"))
    @guild_only()
    async def kick(self, ctx: Interaction, target: Member):
        """Removes a player from the game in the channel"""

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Check player has permission to kick
        if msg := self._require_authority(ctx, game):
            await ctx.response.send_message(msg)
            return

        # Notify game of action
        player = self._get_player(target)
        msg = game.on_leave(player, True)
        await ctx.response.send_message(msg)
        await self._handle_game_update(ctx)


    class BotAdmin(Group):
        def interaction_check(self, ctx: Interaction) -> bool:
            if ctx.user.id not in GoldenBalls.BOT_ADMINS:
                raise CheckFailure("You must be a bot admin to use this command.")
            return True

    botadmin = BotAdmin(name="botadmin", description="Bot admin commands")

    @botadmin.command()
    async def list_games(self, ctx: Interaction):
        await ctx.response.send_message('\n'.join((
            f"## {len(self.games)} Active Games:",
            '\n'.join(
                f"- {game} in <#{channel}>" for channel, game in self.games.items()
            )
        )))

    @botadmin.command()
    async def kill_game(self, ctx: Interaction):
        game = self.games.pop(ctx.channel_id)
        txt = str(game)
        game.kill()
        await ctx.response.send_message(f"Killed game {txt}")
    
    @botadmin.command()
    async def kill_all_games(self, ctx: Interaction):
        ret = ["Killed games:"]
        for channel_id, game in self.games.copy().items():
            del self.games[channel_id]
            txt = str(game)
            game.kill()
            ret.append(f"- {txt} in <#{channel_id}>")
        await ctx.response.send_message('\n'.join(ret))
    
    @botadmin.command()
    async def list_players(self, ctx: Interaction):
        await ctx.response.send_message('\n'.join((
            f"## {len(self.games)} Known Players:",
            '\n'.join(
                f"- {player} ({user_id})"
                for user_id, player in self.players.items()
            )
        )))

    @botadmin.command()
    async def hard_reset(self, ctx: Interaction):
        self.games = {}
        self.players = {}
        await ctx.response.send_message("Reset all data")

    @botadmin.command()
    async def view_state(self, ctx: Interaction):
        game = await self._get_game(ctx)
        if game is None:
            return
        await ctx.response.send_message(game.view_state(), ephemeral=True)

    async def cog_app_command_error(self, ctx: Interaction, error: DiscordException):
        if isinstance(ctx.command, Command) and ctx.command.parent is self.botadmin:
            await ctx.response.send_message(str(error), ephemeral=True)
        elif isinstance(error, CheckFailure):
            await ctx.response.send_message(str(error), ephemeral=True)
        else:
            raise error


async def setup(bot: Bot):
    await bot.add_cog(GoldenBalls(bot))
