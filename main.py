import discord
import gdl_api
import asyncio
import os
import re
import io
import aiohttp
import dotenv
import json
from discord.ext import commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import random


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

dotenv.load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError(
        "Error: Discord token not found\n" \
        "You must create a .env file and write something like DISCORD_TOKEN=AB1wdfCD42.E41ghjfFG"
    )


BOT_CHANNEL_ID = 1401147497438515361
LOGS_CHANNEL_ID = 1403021816460476466
GUILD_ID = 1401117933203226727
GENERAL_CATEGORY_ID = 1401117934633488404
RICKROLL_GIF_URLS = [
    "https://klipy.com/gifs/hugs-rickroll", "https://klipy.com/gifs/rickroll-never-gonna-give-you-up-9",
    "https://klipy.com/gifs/very-importatn", "https://klipy.com/gifs/rick-roll-50", "https://klipy.com/gifs/spoiler-3",
    "https://klipy.com/gifs/oh-no-bro", "https://klipy.com/gifs/rickroll-15", "https://klipy.com/gifs/zant-just-got-rick-rolled",
    "https://klipy.com/gifs/bread-rickroll", "https://klipy.com/gifs/trade-offer-rickroll-1"
]

TIME_TO_GUESS = 10  # sec

with open("words.json", "r", encoding="utf-8") as f:
    WORDS = json.load(f)

def duration(sec: int | str):
    if not isinstance(sec, int) or sec < 0:
        return sec

    h = sec // 3600
    sec %= 3600
    m = sec // 60
    s = sec % 60

    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s or not parts:
        parts.append(f"{s}s")

    return " ".join(parts)

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    for word, reply in WORDS.items():
        if word.startswith("<") and word.endswith(">"):
            if word in message.content:
                await message.reply(reply)
                return

    content_lower = message.content.lower()

    url_regex = r"https?://\S+"
    content_clean = re.sub(url_regex, "", content_lower)

    discord_tag_regex = r"<[@#&]!?\d+>|<a?:\w+:\d+>"
    content_clean = re.sub(discord_tag_regex, "", content_clean)

    for word, reply in WORDS.items():
        if word.startswith("<@") and word.endswith(">"):
            continue

        if re.search(rf"{re.escape(word.lower())}", content_clean):
            await message.reply(reply)
            break

    await bot.process_commands(message)

active_guess_channels = set()
@bot.tree.command(name="guess", description="Makes you guess a level")
async def guess(interaction: discord.Interaction):

    channel_id = interaction.channel.id

    if channel_id in active_guess_channels:
        await interaction.response.send_message(
            "❌ A `/guess` is already running in this channel!",
            ephemeral=True
        )
        return

    active_guess_channels.add(channel_id)

    try:
        await interaction.response.defer(thinking=True)

        levels = gdl_api.get_all_levels()
        level = gdl_api.get_random_level()
        level_id = gdl_api.get_level_id_by_name(level)
        level_info = gdl_api.get_level_info(level_id)
        if not level_info: return
        level_position = level_info.get("placement", "Unknown")
        image_url = f'https://levelthumbs.prevter.me/thumbnail/{level_info.get("ingame_id", "Unknown")}'

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("Impossible de récupérer la miniature.")
                    return

                image_data = await resp.read()

        image_file = discord.File(
            io.BytesIO(image_data),
            filename="level.png"
        )

        await interaction.followup.send(
            content=f"""
## :fire: Guess this level's position between 1 and {len(levels)}!
You have **{TIME_TO_GUESS} seconds**.
## Info:
This level is {duration(level_info.get("length", "Unknown"))} long
""",
            file=image_file
        )

        guesses = {}

        def check(msg: discord.Message):
            if msg.channel != interaction.channel:
                return False
            if not msg.content.isdigit():
                return False
            if msg.author.id in guesses:
                return False
            return True

        try:
            while True:
                msg = await bot.wait_for("message", timeout=TIME_TO_GUESS, check=check)
                guesses[msg.author.id] = int(msg.content)
        except asyncio.TimeoutError:
            pass

        if not guesses:
            await interaction.channel.send("Nobody guessed! You're wasting my time :c")
            return


        results = []
        for user_id, guess in guesses.items():
            diff = abs(guess - level_position)
            results.append((user_id, guess, diff))

        results.sort(key=lambda x: x[2])

        winner_id, winner_guess, winner_diff = results[0]

        winner_user = interaction.guild.get_member(winner_id) or bot.get_user(winner_id)
        winner_name = winner_user.mention if winner_user else f"<@{winner_id}>"

        result_lines = [
            f"""
# ✅ The correct position was #{level_position}!
The Level was {level} created by {level_info.get("creator", "Unknown")} in {level_info.get("game_version", "Unknown")} and verified by {level_info.get("verification", {"username": "Unknown"}).get("username", "Unknown")}
ID: ``{level_info.get("ingame_id", "Unknown")}``
Watch: {level_info.get("verification", {"video_url": "Unknown"}).get("video_url", "Unknown")}

## 🏆 Winner: {winner_name} by {winner_diff} positions (guessed {winner_guess})
""" + (
                "-# Touch grass, get some friends vro"
                if len(guesses) == 1
                else ""
            )
        ]

        if len(results) > 1:
            result_lines.append("__Leaderboard:__")
            for i, (uid, g, d) in enumerate(results[:10], start=1):
                name = f"<@{uid}>"
                result_lines.append(f"{i}. {name} guessed {g} (off by {d})")

        #channel = interaction.channel
        #if isinstance(channel, TextChannel):
        #    await channel.send("\n".join(result_lines))
        await interaction.channel.send("\n".join(result_lines))

    finally:
        active_guess_channels.remove(channel_id)

@bot.tree.command(name="say", description="Makes the bot say something lmao")
async def say(interaction: discord.Interaction, text: str):
    await interaction.channel.send(text)

    await interaction.response.send_message("Message sent ✅", ephemeral=True)

    logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
    if logs_channel:
        await logs_channel.send(f"{interaction.user.name} used `/say` writing \"{text}\"")


rickroll_task_started = False
next_rickroll_time = None


async def send_rickroll():
    guild = bot.get_guild(GUILD_ID)

    if not guild:
        print("Guild not found!")
        return

    channels = [
        channel
        for channel in guild.text_channels
        if channel.category_id == GENERAL_CATEGORY_ID
        and channel.permissions_for(guild.me).send_messages
    ]

    if not channels:
        print("No channel available for rickroll!")
        return

    channel = random.choice(channels)
    gif_url = random.choice(RICKROLL_GIF_URLS)

    await channel.send(gif_url)

    print(f"Rickroll sent in #{channel.name}: {gif_url}")


@tasks.loop(seconds=60)
async def daily_rickroll():
    global next_rickroll_time

    now = datetime.now()

    if now >= next_rickroll_time:
        await send_rickroll()

        tomorrow = now + timedelta(days=1)

        random_hour = random.randint(0, 23)
        random_minute = random.randint(0, 59)

        next_rickroll_time = tomorrow.replace(
            hour=random_hour,
            minute=random_minute,
            second=0,
            microsecond=0
        )

        print(f"Next rickroll: {next_rickroll_time}")


@daily_rickroll.before_loop
async def before_daily_rickroll():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    global rickroll_task_started
    global next_rickroll_time

    print(f"Bot connected as {bot.user}")

    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands to guild {GUILD_ID}")

    channel = bot.get_channel(BOT_CHANNEL_ID)
    if channel:
        await channel.send("Bot is up!")

    await send_rickroll()

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    random_hour = random.randint(0, 23)
    random_minute = random.randint(0, 59)

    next_rickroll_time = tomorrow.replace(
        hour=random_hour,
        minute=random_minute,
        second=0,
        microsecond=0
    )

    print(f"Next rickroll: {next_rickroll_time}")

    if not rickroll_task_started:
        daily_rickroll.start()
        rickroll_task_started = True


from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is online!"

def run_web():
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )

threading.Thread(target=run_web, daemon=True).start()


bot.run(DISCORD_TOKEN)
