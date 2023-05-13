from typing import Dict
from discord import Interaction, Member
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
    
    def get_player(self, member: Member) -> Player:
        # Register player if needed
        if member.id not in self.players:
            self.players[member.id] = Player(member.nick or member.name, member)
        
        return self.players[member.id]
    
    async def flush_message_queue(self, ctx: Interaction, game: Game):
        while game.has_message():
            await ctx.channel.send(game.get_message())

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
        host = self.get_player(ctx.user)
        game, message = Game.start_game(host)
        if game is not None:
            self.games[ctx.channel_id] = game
            await self.flush_message_queue(ctx, game)

        await ctx.response.send_message(message)

    @command()
    @guild_only()
    async def join(self, ctx: Interaction, user: Member = None):
        # Get target user
        user = user or ctx.user

        # Check if a game is in this channel
        game = self.games.get(ctx.channel_id)
        if game is None:
            await ctx.response.send_message("Error: there's no game in this channel.")
            return
        
        # Try join game
        player = self.get_player(user)
        msg = game.on_join(player)
        await self.flush_message_queue(ctx, game)
        await ctx.response.send_message(msg)


async def setup(bot: Bot):
    await bot.add_cog(GoldenBalls(bot))
