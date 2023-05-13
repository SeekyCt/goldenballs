from typing import List
from discord import Interaction, Member
from discord.app_commands import command, guild_only
from discord.ext.commands import Bot, Cog


class GoldenBalls(Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @command()
    @guild_only()
    async def start(self, ctx: Interaction, player_2: Member, player_3: Member, player_4: Member):
        await ctx.response.send_message("Hello")
    

async def setup(bot: Bot):
    await bot.add_cog(GoldenBalls(bot))
