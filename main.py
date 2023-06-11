from os import environ

from discord import Intents
from discord.ext.commands import Bot

extensions = ('goldenballs.extension',)

ANNOUNCEMENTS_CHANNEL = 610974864706371585

if __name__ == '__main__':
    intents = Intents.default()
    intents.message_content = True

    bot = Bot(command_prefix='gb.', intents=intents)

    @bot.event
    async def setup_hook() -> None:
        for extension in extensions:
            await bot.load_extension(extension)

        await bot.tree.sync()
        print("Logged on to", bot.user)
        
        channel = await bot.fetch_channel(ANNOUNCEMENTS_CHANNEL)
        await channel.send("Bot started.")
 
    bot.run(environ["GOLDEN_BALLS_TOKEN"])
