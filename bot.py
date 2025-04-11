import os
import discord
from discord.ext import commands
import yt_dlp
from keep_alive import keep_alive  # Optional: Only for Replit

# Keep-alive for Replit (you can remove this line if not using Replit)
keep_alive()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

if not TOKEN:
    raise ValueError("Set the 'DISCORD_BOT_TOKEN' env variable")
if CHANNEL_ID == 0:
    raise ValueError("Set the 'DISCORD_CHANNEL_ID' env variable")

intents = discord.Intents.all()
client = commands.Bot(command_prefix="/", intents=intents)

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
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'executable': "ffmpeg",
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin -loglevel warning',
    'options': '-vn -b:a 128k'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

async def ensure_voice_client(ctx):
    try:
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()
        return True
    except Exception as e:
        await ctx.send(f"Voice client error: {e}")
        return False

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or client.loop
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("✅ Bot is online!")

@client.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down...")
    await client.close()

@client.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        await ctx.send("Joined voice channel.")
    else:
        await ctx.send("You're not in a voice channel!")

@client.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel.")
    else:
        await ctx.send("I'm not in a voice channel!")

@client.command()
async def play(ctx, *, url):
    if not await ensure_voice_client(ctx):
        return
    async with ctx.typing():
        try:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            player = await YTDLSource.from_url(url, loop=client.loop, stream=True)
            def after_playing(error):
                if error:
                    client.loop.create_task(ctx.send(f"Player error: {error}"))
            ctx.voice_client.play(player, after=after_playing)
            await ctx.send(f"Now playing: {player.title}")
        except Exception as e:
            await ctx.send(f"Error: {e}")
            if ctx.voice_client:
                await ctx.voice_client.disconnect()

@client.command()
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Stopped playing.")
    else:
        await ctx.send("Nothing is playing.")

@client.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused.")
    else:
        await ctx.send("Nothing to pause.")

@client.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed playing.")

client.run(TOKEN)
