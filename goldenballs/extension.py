from typing import Dict, Optional

from discord import HTTPException, Interaction, Member
from discord.app_commands import command, guild_only
from discord.ext.commands import Bot, Cog

from goldenballs.game import Game, Player
from goldenballs.messages import get_msg


UserId = int
ChannelId = int
GBPlayer = Player[Member]
GBGame = Game[ChannelId]


class GoldenBalls(Cog):
    # Discord bot instance
    bot: Bot

    # Player instances for each discord user
    players: Dict[UserId, GBPlayer]

    # Active games in each channel
    games: Dict[ChannelId, GBGame]

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.games = {}

    def _get_player(self, member: Member) -> Player:
        """Get the player instance for a discord member"""

        # Register player if needed
        if member.id not in self.players:
            self.players[member.id] = Player(member.nick or member.name, member)

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

        # Output queued messages
        await self._flush_message_queue(ctx, game)

        # Remove game if finished
        if game.is_finished():
            del self.games[ctx.channel_id]

    @command()
    @guild_only()
    async def start(self, ctx: Interaction, user: Member = None):
        """Starts a game in a channel, if it's free"""

        # Get target user
        user = user or ctx.user

        # Check if game can be started
        if ctx.channel_id in self.games:
            await ctx.response.send_message(get_msg("channel.err.game"), ephemeral=True)
            return

        # Try start game
        host = self._get_player(user)
        game, message = Game.start_game(host)
        await ctx.response.send_message(message, ephemeral=(game is None))
        if game is not None:
            self.games[ctx.channel_id] = game
        await self._handle_game_update(ctx)

    @command()
    @guild_only()
    async def join(self, ctx: Interaction, user: Member = None):
        """Joins the game in the channel, if it exists and the user is free"""

        # Get target user
        user = user or ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Try join game
        player = self._get_player(user)
        msg = game.on_join(player)
        await ctx.response.send_message(msg, ephemeral=(not player.is_busy()))
        await self._handle_game_update(ctx)

    @command()
    @guild_only()
    async def vote(self, ctx: Interaction, target: Member, user: Member = None):
        """Round 1 & 2 - votes for the player to remove"""

        # Get target user
        user = user or ctx.user

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
    
    @command()
    @guild_only()
    async def view_balls(self, ctx: Interaction, user: Member = None):
        """Round 1 & 2 - view your hidden balls"""

        # Get target user
        user = user or ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of vote
        player = self._get_player(user)
        msg = game.on_view_balls(player)
        await ctx.response.send_message(msg, ephemeral=True)
        await self._handle_game_update(ctx)

    @command()
    @guild_only()
    async def pick(self, ctx: Interaction, ball_id: int, user: Member = None):
        """Round 3 - picks a ball"""

        # Get target user
        user = user or ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of vote
        player = self._get_player(user)
        msg = game.on_pick(player, ball_id)
        await ctx.response.send_message(msg)
        await self._handle_game_update(ctx)

    @command()
    @guild_only()
    async def split(self, ctx: Interaction, user: Member = None):
        """Round 4 - chooses to split the prize"""

        # Get target user
        user = user or ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of action
        player = self._get_player(user)
        msg = game.on_split(player)
        await ctx.response.send_message(msg, ephemeral=True)
        await self._handle_game_update(ctx)

    @command()
    @guild_only()
    async def steal(self, ctx: Interaction, user: Member = None):
        """Round 4 - chooses to steal the prize"""

        # Get target user
        user = user or ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return

        # Notify game of action
        player = self._get_player(user)
        msg = game.on_steal(player)
        await ctx.response.send_message(msg, ephemeral=True)
        await self._handle_game_update(ctx)

    @command()
    @guild_only()
    async def leave(self, ctx: Interaction, user: Member = None):
        """Leaves your current game, if in one"""

        # Get target user
        user = user or ctx.user

        # Notify game of action
        player = self._get_player(user)
        game = player.current_game
        if game is None:
            await ctx.response.send_message(get_msg("user.err.no_game"))
            return

        msg = game.on_leave(player)
        await ctx.response.send_message(msg)
        await self._handle_game_update(ctx)


async def setup(bot: Bot):
    await bot.add_cog(GoldenBalls(bot))
