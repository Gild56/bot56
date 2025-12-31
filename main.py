import discord
import gdl_api
import asyncio
import os
import re
import dotenv
from discord.ext import commands
from discord import File
#from discord import TextChannel

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

dotenv.load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError(
        "Error: Token not found\n" \
        "You must create a .env file and write something like TOKEN=AB1wdfCD42.E41ghjfFG"
    )

BOT_CHANNEL_ID = 1401147497438515361
LOGS_CHANNEL_ID = 1403021816460476466
GUILD_ID = 1401117933203226727

TIME_TO_GUESS = 30  # sec

WORDS = {
    "job": "https://tenor.com/view/breaking-bad-walter-white-points-gun-gun-shoot-gif-3298902",
    "crazy": "https://tenor.com/view/kyouki-gd-geometry-dash-gif-6703483145159127538",
    "krazy": "https://tenor.com/view/kyouki-gd-geometry-dash-gif-6703483145159127538"
}

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

    content_lower = message.content.lower()

    url_regex = r"https?://\S+"

    content_clean = re.sub(url_regex, "", content_lower)

    for word, reply in WORDS.items():
        if re.search(rf"\b{word}\b", content_clean):
            await message.reply(reply)
            break

    await bot.process_commands(message)

@bot.tree.command(name="guess", description="Makes you guess a level")
async def guess(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    levels = gdl_api.get_all_levels()
    level = gdl_api.get_random_level()
    level_id = gdl_api.get_level_id_by_name(level)
    level_info = gdl_api.get_level_info(level_id)
    if not level_info: return
    level_position = level_info.get("placement", "Unknown")
    images_dir = f"src/images/{level}"

    files_to_send: list[File] = []

    if os.path.exists(images_dir):
        for filename in sorted(os.listdir(images_dir))[:3]:
            file_path = os.path.join(images_dir, filename)
            files_to_send.append(File(file_path))

    if files_to_send:
        await interaction.followup.send(
            content=f"""
🎯 Guess this level's position between 1 and {len(levels)}!
You have **{TIME_TO_GUESS} seconds**.
## Info:
This level is {duration(level_info.get("length", "Unknown"))} long
""",
            files=files_to_send
        )
    else:
        print("no images")
        interaction.channel.send("Error")

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
✅ **The correct position was #{level_position}!**
The Level was {level} created by {level_info.get("creator", "Unknown")} in {level_info.get("game_version", "Unknown")} and verified by {level_info.get("verification", {"username": "Unknown"}).get("username", "Unknown")}
ID: ``{level_info.get("ingame_id", "Unknown")}``
Watch: {level_info.get("verification", {"video_url": "Unknown"}).get("video_url", "Unknown")}

🏆 **Winner:** {winner_name} by {winner_diff} positions (guessed {winner_guess})
"""
    ]

    if len(results) > 1:
        result_lines.append("__Leaderboard:__")
        for i, (uid, g, d) in enumerate(results[:10], start=1):
            name = f"<@{uid}>"
            result_lines.append(f"{i}. {name} → {g} (diff {d})")

    #channel = interaction.channel
    #if isinstance(channel, TextChannel):
    #    await channel.send("\n".join(result_lines))
    await interaction.channel.send("\n".join(result_lines))

@bot.tree.command(name="say", description="Makes the bot say something (dont show that to Luis)")
async def say(interaction: discord.Interaction, text: str):
    await interaction.channel.send(text)

    await interaction.response.send_message("Message sent ✅", ephemeral=True)

    logs_channel = bot.get_channel(LOGS_CHANNEL_ID)
    if logs_channel:
        await logs_channel.send(f"{interaction.user.name} used `/say` writing \"{text}\"")

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands to guild {GUILD_ID}")

    channel = bot.get_channel(BOT_CHANNEL_ID)
    if channel:
        await channel.send("Bot is up!")


bot.run(TOKEN)
