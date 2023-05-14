from typing import Dict, Optional
from discord import HTTPException, Interaction, Member
from discord.app_commands import command, guild_only
from discord.ext.commands import Bot, Cog

from goldenballs.game import Game, Player


UserId = int
ChannelId = int
GBPlayer = Player[Member]


class GoldenBalls(Cog):
    players: Dict[UserId, GBPlayer]
    games: Dict[ChannelId, Game]

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.games = {}
    
    def _get_player(self, member: Member) -> Player:
        # Register player if needed
        if member.id not in self.players:
            self.players[member.id] = Player(member.nick or member.name, member)
        
        return self.players[member.id]
    
    async def flush_message_queue(self, ctx: Interaction, game: Game):
        while game.has_channel_message():
            await ctx.channel.send(game.get_channel_message())
        for player in game.get_dm_subjects():
            while game.has_dm(player):
                member: Member = player.context
                dm = game.get_dm(player)
                try:
                    await member.create_dm()
                    await member.send(dm)
                except HTTPException as e:
                    await ctx.channel.send(f"Error sending dm to {player.get_name()}: {e}")
    
    async def _get_game(self, ctx: Interaction) -> Optional[Game]:
        game = self.games.get(ctx.channel_id)
        if game is None:
            await ctx.response.send_message("Error: there's no game in this channel.")
        return game

    @command()
    @guild_only()
    async def start(self, ctx: Interaction, user: Member = None):
        # Get target user
        user = user or ctx.user

        # Check if game can be started
        if ctx.channel_id in self.games:
            await ctx.response.send_message("Error: there's already a game in this channel.")
            return
        
        # Try start game
        host = self._get_player(ctx.user)
        game, message = Game.start_game(host)
        await ctx.response.send_message(message)
        if game is not None:
            self.games[ctx.channel_id] = game
            await self.flush_message_queue(ctx, game)

    @command()
    @guild_only()
    async def join(self, ctx: Interaction, user: Member = None):
        # Get target user
        user = user or ctx.user

        # Check if a game is in this channel
        game = await self._get_game(ctx)
        if game is None:
            return
        
        # Try join game
        player = self._get_player(user)
        msg = game.on_join(player)
        await ctx.response.send_message(msg)
        await self.flush_message_queue(ctx, game)
    
    @command()
    @guild_only()
    async def vote(self, ctx: Interaction, target: Member, user: Member = None):
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
        await self.flush_message_queue(ctx, game)
    
    @command()
    @guild_only()
    async def pick(self, ctx: Interaction, ball_id: int, user: Member = None):
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
        await self.flush_message_queue(ctx, game)
    


async def setup(bot: Bot):
    await bot.add_cog(GoldenBalls(bot))
