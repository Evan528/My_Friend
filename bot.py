import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os
import logging
import threading
from flask import Flask
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

# Flask server to keep bot alive
app = Flask(__name__)

@app.route('/')
def home():
    return f"Bot is online. {datetime.utcnow()}"

@app.route('/ping')
def ping():
    return "Pong", 200

def run_web_server():
    app.run(host="0.0.0.0", port=8080)

# Start Flask server in a separate thread
threading.Thread(target=run_web_server).start()

# Load environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

if not TOKEN:
    raise ValueError("Bot token not found. Set 'DISCORD_BOT_TOKEN' in environment variables.")
if CHANNEL_ID == 0:
    raise ValueError("Channel ID not found. Set 'DISCORD_CHANNEL_ID' in environment variables.")

# Setup bot
intents = discord.Intents.all()
client = commands.Bot(command_prefix="/", intents=intents)

# yt-dlp config
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'executable': 'ffmpeg',
    'before_options': '-nostdin',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.filename = ytdl.prepare_filename(data)

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or client.loop
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Events
@client.event
async def on_ready():
    logger.info(f'Bot connected as {client.user.name}')
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("The bot is now online.")
    else:
        logger.warning(f"Channel ID {CHANNEL_ID} not found.")

# Commands
@client.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("Bot is now offline.")
    await client.close()

@client.command()
async def join(ctx):
    if ctx.voice_client:
        await ctx.send("I'm already connected to a voice channel.")
        return
    if not ctx.author.voice:
        await ctx.send("You're not connected to a voice channel!")
        return
    await ctx.author.voice.channel.connect()
    await ctx.send(f"Joined {ctx.author.voice.channel.name}")

@client.command()
async def leave(ctx):
    if ctx.voice_client and ctx.voice_client.is_connected():
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I'm not connected to any voice channel.")

@client.command()
async def play(ctx, *, url):
    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=client.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: logger.error(f'Player error: {e}') if e else None)
            await ctx.send(f'Now playing: {player.title}')
        except Exception as e:
            logger.exception("Playback error:")
            await ctx.send("An error occurred while trying to play the song.")

@client.command()
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Playback stopped.")
    else:
        await ctx.send("No audio is playing.")

@client.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Playback paused.")
    else:
        await ctx.send("No audio is playing.")

@client.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Playback resumed.")
    else:
        await ctx.send("Nothing is paused.")

# Run bot
client.run(TOKEN)
