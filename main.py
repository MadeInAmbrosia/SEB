import asyncio
import discord
from discord.ext import commands
import os
import time
TOKEN = "PlaceYourTokenHereThanks<3"
INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.guilds = True
INTENTS.messages = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)
# I recommend letting the bot run with a role that has admin privileges if you want to scan the whole server.
# If not, lock it to a specific channel with channel perms or a role. 
# All of this below can be customized.
VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv")
CHUNK_SIZE = 1000
CHANNEL_DELAY = 1.25
CHUNK_DELAY = 0.75
RATE_LIMIT_DELAY = 5
PROGRESS_INTERVAL = 5  # seconds
# The bot WILL eventually get rate limited by Discord. Don't worry, it will still do it's job.
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def findvideos(ctx):
    guild = ctx.guild
    results = []

    scanned_messages = 0
    last_update = time.time()

    status_msg = await ctx.send("🔍 Starting full server scan…")

    for channel in guild.text_channels:
        await asyncio.sleep(CHANNEL_DELAY)

        before = None

        while True:
            try:
                messages = [
                    m async for m in channel.history(
                        limit=CHUNK_SIZE,
                        before=before,
                        oldest_first=False
                    )
                ]

                if not messages:
                    break

                for message in messages:
                    scanned_messages += 1
                    found = False

                    # attachments
                    for att in message.attachments:
                        if att.filename.lower().endswith(VIDEO_EXTENSIONS):
                            found = True

                    # embeds
                    for emb in message.embeds:
                        if emb.type == "video" or emb.video:
                            found = True

                    if found:
                        jump = (
                            f"https://discord.com/channels/"
                            f"{guild.id}/{channel.id}/{message.id}"
                        )
                        results.append(
                            f"[{message.created_at.date()}] "
                            f"#{channel.name} | "
                            f"{message.author} | "
                            f"{jump}"
                        )
                        #This above is the format for the data collected in the .txt file!
                before = messages[-1]
                await asyncio.sleep(CHUNK_DELAY)

                # Status of the current progress, as a message.
                now = time.time()
                if now - last_update >= PROGRESS_INTERVAL:
                    await status_msg.edit(
                        content=( 
                            f"🔍 Scanning…\n"
                            f"• Channel: **#{channel.name}**\n"
                            f"• Messages scanned: **{scanned_messages}**\n"
                            f"• Videos found: **{len(results)}**"
                        )
                    ) 
                    last_update = now
            except discord.Forbidden:
                break
            except discord.HTTPException:
                await asyncio.sleep(RATE_LIMIT_DELAY)

    filename = "videos.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(results))

    await status_msg.edit(
        content=f"✅ Scan complete — **{len(results)} videos found!**"
    )

    await ctx.send(file=discord.File(filename))
    os.remove(filename)


bot.run(TOKEN)
