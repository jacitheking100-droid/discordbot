import discord
from discord.ext import commands
import re

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

LINK_REGEX = re.compile(
    r"(https?://\S+|www\.\S+|discord\.gg/\S+|discord\.com/invite/\S+)",
    re.IGNORECASE
)

@bot.event
async def on_ready():
    print(f"הבוט מחובר בתור {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if LINK_REGEX.search(message.content):
        try:
            await message.delete()

            try:
                await message.author.send("אסור לשלוח לינקים ישועל")
            except discord.Forbidden:
                pass

        except discord.Forbidden:
            print("אין לבוט הרשאה למחוק הודעות.")

    await bot.process_commands(message)


import os

bot.run(os.environ["DISCORD_TOKEN"])

