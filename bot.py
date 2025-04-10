import discord
from discord.ext import commands
import yt_dlp as youtube_dl  # Use yt-dlp for better support
import os  # Required for environment variables
from flask import Flask
from threading import Thread

# Flask web server for keep-alive
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Store your bot token securely using environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Set in Render's environment variables
if not TOKEN:
    raise ValueError("Bot token not found. Set 'DISCORD_BOT_TOKEN' in environment variables.")

# Replace with your actual channel ID
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))  # Set channel ID via environment variables
if CHANNEL_ID == 0:
    raise ValueError("Channel ID not found. Set 'DISCORD_CHANNEL_ID' in environment variables.")

# Set up the bot with the command prefix "/"
intents = discord.Intents.all()
client = commands.Bot(command_prefix="/", intents=intents)

# Music-related variables
youtube_dl.utils.bug_reports_message = lambda: ''

# Set yt-dlp options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # Bind to IPv4
}

ffmpeg_options = {
    'executable': "ffmpeg",  # Use default ffmpeg path on Render
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

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or client.loop
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # If it's a playlist, take the first item
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Bot Events
@client.event
async def on_ready():
    print(f'Bot is connected to Discord as {client.user.name}')
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("The bot is now online.")
    else:
        print(f"Channel with ID {CHANNEL_ID} not found.")

# Commands
@client.command()
@commands.is_owner()
async def shutdown(ctx):
    """Shuts down the bot."""
    await ctx.send("Bot is now offline")
    await client.close()

@client.command()
async def join(ctx):
    """Bot joins the voice channel."""
    if ctx.voice_client:
        await ctx.send("I'm already connected to a voice channel.")
        return
    if not ctx.author.voice:
        await ctx.send("You're not connected to a voice channel!")
        return
    channel = ctx.author.voice.channel
    await channel.connect()
    await ctx.send(f"Joined {channel.name}")

@client.command()
async def leave(ctx):
    """Bot leaves the voice channel."""
    if ctx.voice_client and ctx.voice_client.is_connected():
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I'm not connected to a voice channel.")

@client.command()
async def play(ctx, *, url):
    """Plays music from a YouTube URL."""
    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=client.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
            await ctx.send(f'Now playing: {player.title}')
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            await ctx.send("An error occurred while trying to play the song.")

@client.command()
async def stop(ctx):
    """Stops the currently playing song."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Playback stopped.")
    else:
        await ctx.send("No audio is playing at the moment.")

@client.command()
async def pause(ctx):
    """Pauses the currently playing song."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Playback paused.")
    else:
        await ctx.send("No audio is playing at the moment.")

@client.command()
async def resume(ctx):
    """Resumes a paused song."""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Playback resumed.")
    else:
        await ctx.send("No audio is paused at the moment.")

# Keep the Flask server running
keep_alive()

# Run the bot
client.run(TOKEN)
