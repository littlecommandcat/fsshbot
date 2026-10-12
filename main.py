import asyncio
import os

import discord
from discord.ext import commands
from discord.gateway import DiscordWebSocket
from dotenv import load_dotenv

from core import identify

load_dotenv()

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    allowed_mentions=discord.AllowedMentions(everyone=False, roles=False)
)


async def load_cogs():
    for filename in os.listdir("./cogs"):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        extension = f"cogs.{filename[:-3]}"

        try:
            await bot.load_extension(extension)
            print(f"[Cog] Loaded: {extension}")
        except Exception as e:
            print(f"[Cog] Failed: {extension} -> {type(e).__name__}: {e}")


@bot.event
async def setup_hook():
    await load_cogs()


@bot.event
async def on_ready():
    print(f"Bot login as {bot.user}({bot.user.id})")


async def main():
    print("Start bot")
    DiscordWebSocket.identify = identify
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())