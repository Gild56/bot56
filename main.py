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

    for word, reply in WORDS.items():

        if re.search(rf"{re.escape(word.lower())}", content_lower):
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
    global terminal_started, terminal_starting
    terminal_started = True
    terminal_starting = False

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


import time
from threading import Lock, Thread
from flask import Flask, request

app = Flask(__name__)


terminal_logs = []
terminal_lock = Lock()
terminal_started = False
terminal_starting = False

# Horloge fictive du terminal
virtual_seconds = 26 * 3600 + 98 * 60 + 26
VIRTUAL_DATE = "2067-13-21"

def terminal_log(level, logger, message):
    global virtual_seconds

    with terminal_lock:
        total = virtual_seconds
        virtual_seconds += 1

        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60

        timestamp = f"{VIRTUAL_DATE} {hours:02}:{minutes:02}:{seconds:02}"
        terminal_logs.append({
            "timestamp": timestamp,
            "level": level,
            "logger": logger,
            "message": str(message)
        })

        # Limite la mémoire utilisée
        if len(terminal_logs) > 500:
            del terminal_logs[:-500]


def add_initial_logs():
    initial_logs = [
        ("INFO", "david", "System entered"),
        ("INFO", "__main__", "Executing the command..."),
        ("INFO", "__main__", "Command executed, starting the bot..."),
        ("INFO", "discord.client", "logging in using static token"),
        ("INFO", "discord.gateway",
         "Shard ID None has connected to Gateway (Session ID: a1b2c3d4e5f6)"),
        ("INFO", "__main__", "Bot connected as GildBot#1234"),
        ("INFO", "__main__", f"Synced 2 commands to guild {GUILD_ID}"),
        ("INFO", "__main__", "Bot is up!"),
        ("INFO", "__main__", "Rickroll sent in #general: "
         "https://klipy.com/gifs/rickroll-15"),
        ("INFO", "__main__", "Next rickroll: 2026-10-21 18:42:00"),
        ("INFO", "discord.client", "logging in using static token"),
        ("INFO", "discord.gateway",
         "Shard ID None has connected to Gateway (Session ID: f7e8d9c0b1a2)"),
        ("INFO", "__main__", "Bot connected as GildBot#1234"),
        ("INFO", "__main__", f"Synced 2 commands to guild {GUILD_ID}"),
        ("INFO", "__main__", "Bot is up!"),
        ("INFO", "michael", "System entered"),
        ("INFO", "__main__", "Rickroll sent in #off-topic: "
         "https://klipy.com/gifs/hugs-rickroll"),
        ("INFO", "__main__", "Next rickroll: 2026-10-22 03:17:00"),
        ("INFO", "__main__", 'User123 used /say writing "Hello everyone!"'),
        ("INFO", "__main__", "Guess game started in #general"),
        ("INFO", "__main__", "Guess game ended: level position #42, 5 participants"),
        ("INFO", "__main__", "Rickroll sent in #general: "
         "https://klipy.com/gifs/rickroll-15"),
        ("INFO", "__main__", "Next rickroll: 2026-10-22 11:06:00"),
        ("WARN", "__main__", "Anomaly detected"),
        ("WARN", "__main__", "Something is wrong"),
        ("ERROR", "__main__", "Application crashed"),
        ("ERROR", "__main__", "??rtNGN??TFdF"),
        ("INFO", "michael", "Uhhh"),
        ("INFO", "michael", "What happened"),
        ("INFO", "michael", "What's wrong with this?"),
        ("INFO", "__main__", "Executing the command..."),
        ("ERROR", "__main__", "Wrong command!"),
        ("ERROR", "__main__", "The command 'will.launch()' does not exist"),
        ("INFO", "michael", "????"),
        ("INFO", "michael", "I've always used this and it worked"),
        ("INFO", "michael", "Lemme try one more time"),
        ("INFO", "__main__", "Executing the command..."),
        ("ERROR", "__main__", "Wrong command!"),
        ("ERROR", "__main__", "The command 'will.launch()' does not exist"),
    ]

    # Reproduit l'historique original avec ses timestamps exacts.
    original_timestamps = [
        "2026-10-21 01:06:02",
        "2026-10-21 01:06:05",
        "2026-10-21 01:06:06",
        "2026-10-21 01:06:12",
        "2026-10-21 01:06:13",
        "2026-10-21 01:06:15",
        "2026-10-21 01:06:15",
        "2026-10-21 01:06:16",
        "2026-10-21 01:06:17",
        "2026-10-21 01:06:17",
        "2026-10-21 01:06:17",
        "2026-10-21 01:06:18",
        "2026-10-21 01:06:20",
        "2026-10-21 01:06:20",
        "2026-10-21 01:06:21",
        "2026-10-21 01:06:21",
        "2026-10-21 01:06:22",
        "2026-10-21 01:06:22",
        "2026-10-21 01:07:04",
        "2026-10-21 01:08:11",
        "2026-10-21 01:08:21",
        "2026-10-21 18:42:05",
        "2026-10-21 18:42:16",
        "2026-10-21 19:89:35",
        "2067-10-21 19:92:47",
        "2067-13-21 19:95:63",
        "2067-13-21 26:97:89",
        "2067-13-21 26:97:90",
        "2067-13-21 26:97:95",
        "2067-13-21 26:97:98",
        "2067-13-21 26:98:05",
        "2067-13-21 26:98:06",
        "2067-13-21 26:98:07",
        "2067-13-21 26:98:08",
        "2067-13-21 26:98:15",
        "2067-13-21 26:98:20",
        "2067-13-21 26:98:24",
        "2067-13-21 26:98:25",
        "2067-13-21 26:98:26",
    ]

    with terminal_lock:
        for timestamp, (level, logger, message) in zip(
            original_timestamps, initial_logs
        ):
            terminal_logs.append({
                "timestamp": timestamp,
                "level": level,
                "logger": logger,
                "message": message
            })


add_initial_logs()


@app.route("/")
def home():
    return '<a href="/logs">Open terminal</a>'


@app.route("/logs")
def logs_page():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>System Terminal</title>
<style>
* { box-sizing: border-box; }
body {
    margin: 0;
    padding: 24px;
    background: #080b0a;
    color: #d5e5d8;
    font: 14px Consolas, "Courier New", monospace;
}
.terminal {
    max-width: 1200px;
    height: calc(100vh - 48px);
    margin: auto;
    display: flex;
    flex-direction: column;
    border: 1px solid #294333;
    background: #050706;
    box-shadow: 0 0 30px #0008;
}
.header {
    padding: 13px 16px;
    background: #101b14;
    border-bottom: 1px solid #294333;
    color: #8be9a2;
}
#logs {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
.line { margin-bottom: 5px; line-height: 1.5; }
.timestamp { color: #77867c; }
.INFO { color: #c4d5c8; }
.WARN { color: #f0c674; }
.ERROR { color: #ff7070; }
.prompt {
    display: flex;
    gap: 10px;
    padding: 14px 16px;
    border-top: 1px solid #294333;
    background: #0b100d;
}
.prompt span { color: #8be9a2; }
input {
    min-width: 0;
    flex: 1;
    border: 0;
    outline: none;
    background: transparent;
    color: #8be9a2;
    font: inherit;
}
input:disabled { opacity: .5; }
</style>
</head>
<body>
<div class="terminal">
    <div class="header">GILDBOT SYSTEM TERMINAL - <span id="status">ONLINE</span></div>
    <div id="logs"></div>
    <form class="prompt" id="command-form">
        <span>&gt;</span>
        <input id="command" autocomplete="off" autofocus
               placeholder="Enter command..." aria-label="Command">
    </form>
</div>
<script>
const output = document.getElementById("logs");
const form = document.getElementById("command-form");
const input = document.getElementById("command");
const status = document.getElementById("status");

let displayed = 0;
let busy = false;

function renderLog(log) {
    const line = document.createElement("div");
    line.className = "line";

    const timestamp = document.createElement("span");
    timestamp.className = "timestamp";
    timestamp.textContent = `[${log.timestamp}] `;

    const level = document.createElement("span");
    level.className = log.level;
    level.textContent = `[${log.level}] `;

    const logger = document.createElement("span");
    logger.textContent = log.logger + ": ";

    const message = document.createElement("span");
    message.textContent = log.message;

    line.append(timestamp, level, logger, message);
    output.appendChild(line);
}

async function refreshLogs() {
    try {
        const response = await fetch("/api/logs");
        const data = await response.json();

        for (const log of data.logs.slice(displayed)) {
            renderLog(log);
            displayed++;
        }

        if (output.scrollHeight - output.scrollTop - output.clientHeight < 50) {
            output.scrollTop = output.scrollHeight;
        }
        status.textContent = data.started ? "RUNNING" :
            data.starting ? "STARTING" : "WAITING";
    } catch (error) {
        status.textContent = "CONNECTION ERROR";
    }
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (busy || !input.value.trim()) return;

    const command = input.value.trim();
    input.value = "";
    busy = true;
    input.disabled = true;

    try {
        const response = await fetch("/api/command", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({command})
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Command failed");
        }
    } catch (error) {
        alert("Connection error");
    } finally {
        await refreshLogs();
        busy = false;
        input.disabled = false;
        input.focus();
    }
});

refreshLogs();
setInterval(refreshLogs, 500);
</script>
</body>
</html>
"""


@app.route("/api/logs")
def api_logs():
    with terminal_lock:
        logs = list(terminal_logs)

    return {
        "logs": logs,
        "started": terminal_started,
        "starting": terminal_starting
    }


@app.route("/api/command", methods=["POST"])
def api_command():
    global terminal_started, terminal_starting

    data = request.get_json(silent=True) or {}
    command = data.get("command", "").strip()

    if not command:
        return {"error": "Empty command"}, 400

    terminal_log("INFO", "__main__", "Executing the command...")

    if command != "bill.launch()":
        def report_error():
            time.sleep(1)
            terminal_log("ERROR", "__main__", "Wrong command!")

        Thread(target=report_error, daemon=True).start()
        return {"ok": True}

    with terminal_lock:
        if terminal_started or terminal_starting:
            terminal_log("WARN", "__main__", "Bot is already running!")
            return {"ok": True}

        terminal_starting = True

    terminal_log("INFO", "__main__", "Command accepted.")
    terminal_log("INFO", "__main__", "Initializing bill...")
    terminal_log("INFO", "__main__", "Launching Discord bot...")

    def launch_bot():
        global terminal_started, terminal_starting

        try:
            # bot.run() must only be called once.
            bot.run(DISCORD_TOKEN)
        except Exception as exc:
            terminal_log("ERROR", "__main__", f"Application crashed: {exc}")
        finally:
            terminal_started = False
            terminal_starting = False

    Thread(target=launch_bot, daemon=True).start()

    return {"ok": True}

if __name__ == "__main__":
    print("Starting Flask server...")
    app.run(host="0.0.0.0", port=5000, debug=False)
