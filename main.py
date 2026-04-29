import asyncio
import logging
import io
import re
import os
from typing import Optional, Union
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands

class BotConfig:
    EXTENSIONS = {
        "Video": (".mp4", ".mov", ".webm", ".mkv", ".flv", ".vob", ".avi", ".wmv"),
        "Audio": (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".aiff"),
        "Images": (".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".bmp", ".svg"),
        "Documents": (".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".rtf", ".odt"),
        "Programs": (".exe", ".msi", ".dmg", ".pkg", ".apk", ".deb", ".rpm", ".sh", ".bat", ".bin"),
        "Programming": (".py", ".c", ".h", ".cpp", ".hpp", ".java", ".js", ".ts", ".html", ".css", ".go", ".rs", ".php", ".cs", ".rb"),
        "Archives": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"),
        "All": None
    }
    DELAY_BETWEEN_CHANNELS = 1.0 
    PROGRESS_UPDATE_SECONDS = 5
    RATE_LIMIT_BACKOFF = 5.0

class SEB(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.logger = logging.getLogger("SEB")

    async def setup_hook(self):
        await self.tree.sync()
        self.logger.info("SEB Slash commands synced.")

    async def on_ready(self):
        print(f"SEB Online: {self.user}")

bot = SEB()

@bot.tree.command(
    name="scans",
    description="Scan for specific file types with advanced filtering."
)
@app_commands.describe(
    category="The category of files to look for",
    channel="Specific channel to scan (defaults to all)",
    days="Scan messages from the last X days (defaults to all time)",
    dm="Send the final report to your DM (defaults to No)",
    exclude="Mention channels to exclude (e.g. #secret #logs)"
)
@app_commands.choices(category=[
    app_commands.Choice(name="Video (MP4, MOV, WEBM, MKV)", value="Video"),
    app_commands.Choice(name="Audio (MP3, WAV, FLAC, M4A)", value="Audio"),
    app_commands.Choice(name="Images (JPG, PNG, GIF, WEBP)", value="Images"),
    app_commands.Choice(name="Documents (PDF, Office, TXT)", value="Documents"),
    app_commands.Choice(name="Programs (EXE, MSI, APK, SH)", value="Programs"),
    app_commands.Choice(name="Programming (PY, C, JS, RS)", value="Programming"),
    app_commands.Choice(name="Archives (ZIP, RAR, 7Z)", value="Archives"),
    app_commands.Choice(name="All (Everything with an extension)", value="All")
])
@app_commands.choices(dm=[
    app_commands.Choice(name="Yes", value=1),
    app_commands.Choice(name="No", value=0)
])
@app_commands.checks.has_permissions(administrator=True)
async def scans(
    interaction: discord.Interaction, 
    category: app_commands.Choice[str], 
    channel: Optional[Union[discord.TextChannel, discord.Thread]] = None,
    days: Optional[int] = None,
    dm: Optional[int] = 0,
    exclude: Optional[str] = None
):
    await interaction.response.defer(thinking=True)

    excluded_ids = [int(i) for i in re.findall(r'<#(\d+)>', exclude)] if exclude else []
    selected_exts = BotConfig.EXTENSIONS.get(category.value)
    after_date = datetime.now() - timedelta(days=days) if days else None
    
    if channel:
        channels_to_scan = [channel]
    else:
        channels_to_scan = [c for c in interaction.guild.text_channels if c.id not in excluded_ids]
    
    results = []
    total_scanned = 0
    loop = asyncio.get_event_loop()
    last_update = loop.time()
    
    embed = discord.Embed(
        title="SEB | Scan Initialized",
        description=(
            f"Category: `{category.name}`\n"
            f"Scope: `{channel.name if channel else 'Full Server'}`\n"
            f"Excluded: `{len(excluded_ids)} channels`\n"
            f"Timeframe: `{f'{days} days' if days else 'All time'}`\n"
            f"DM Report: `{'Yes' if dm else 'No'}`"
        ),
        color=discord.Color.blue()
    )
    await interaction.followup.send(embed=embed)

    for target_channel in channels_to_scan:
        perms = target_channel.permissions_for(interaction.guild.me)
        if not perms.read_message_history or not perms.view_channel:
            continue

        await asyncio.sleep(BotConfig.DELAY_BETWEEN_CHANNELS)
        
        try:
            async for message in target_channel.history(limit=None, after=after_date):
                total_scanned += 1

                for a in message.attachments:
                    found_ext = None
                    file_ext = os.path.splitext(a.filename)[1].lower()
                    
                    if category.value == "All":
                        if file_ext: found_ext = file_ext
                    elif file_ext.endswith(selected_exts):
                        found_ext = file_ext

                    if found_ext:
                        jump = f"https://discord.com{interaction.guild.id}/{target_channel.id}/{message.id}"
                        results.append(f"[{message.created_at.date()}] #{target_channel.name} | {message.author} | {jump} | TYPE: {found_ext.upper()}")

                if category.value in ["Video", "All"]:
                    for e in message.embeds:
                        if e.type == "video" or e.video:
                            jump = f"https://discord.com{interaction.guild.id}/{target_channel.id}/{message.id}"
                            if not any(jump in r for r in results):
                                results.append(f"[{message.created_at.date()}] #{target_channel.name} | {message.author} | {jump} | TYPE: EMBED_VIDEO")

                now = loop.time()
                if now - last_update >= BotConfig.PROGRESS_UPDATE_SECONDS:
                    update_embed = discord.Embed(title="SEB | Scanning...", color=discord.Color.orange())
                    update_embed.add_field(name="Current Channel", value=f"`#{target_channel.name}`", inline=False)
                    update_embed.add_field(name="Progress", value=f"Messages: `{total_scanned:,}`\nMatches: `{len(results)}`", inline=True)
                    await interaction.edit_original_response(embed=update_embed)
                    last_update = now

        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(BotConfig.RATE_LIMIT_BACKOFF)
            continue
        except Exception as e:
            logging.error(f"Error in {target_channel.name}: {e}")
            continue

    final_embed = discord.Embed(
        title="SEB | Scan Complete",
        description=f"Successfully indexed **{len(results)}** matches.",
        color=discord.Color.green()
    )
    await interaction.edit_original_response(embed=final_embed)

    if results:
        buffer = io.BytesIO("\n".join(results).encode("utf-8"))
        report_file = discord.File(fp=buffer, filename=f"SEB_{category.value}_Report.txt")
        
        if dm:
            try:
                await interaction.user.send(content=f"SEB Report: **{interaction.guild.name}**", file=report_file)
            except discord.Forbidden:
                await interaction.followup.send("DM failed. Check privacy settings.", ephemeral=True)
        else:
            await interaction.followup.send(file=report_file)

@scans.error
async def scans_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("Administrative privileges required.", ephemeral=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    bot.run("TOKEN")
