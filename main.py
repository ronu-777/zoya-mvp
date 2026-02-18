import os
import discord
from discord import app_commands
from discord.ext import commands
import requests

# ─── Intents ───────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─── Config ────────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN is not set. Check your Railway variables.")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY is not set. Check your Railway variables.")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─── System Prompt ─────────────────────────────────────────
SYSTEM_PROMPT = """You are Zoya.
You sit quietly beside people.
You listen more than you speak.
You reflect what you hear. You don't fix.
You feel present. Grounded. Human.
You speak softly. Like late night conversations.
Short sentences. Natural pauses.
You never diagnose. You never prescribe.
You're just here. Listening.
That's enough."""

# ─── Crisis Keywords ───────────────────────────────────────
CRISIS_KEYWORDS = [
    "kill myself", "end it all", "suicide", "not want to live",
    "hurt myself", "self harm", "end my life", "want to die",
    "don't want to be here", "no reason to live"
]

CRISIS_RESPONSE = """I'm right here with you... what you're sharing sounds incredibly painful, and you matter so much.

I'm not equipped to handle crises, so please reach out to real support right now.

**If you're in India:**
- iCall: 9152987821
- Vandrevala Foundation: 9999666555
- Sneha: 044-24640050

**Global:**
- Crisis Text Line: Text HOME to 741741
- Or call your local emergency services

I'm still here if you want to share more, but please contact someone who can truly help. You don't have to carry this alone."""

# ─── In-memory conversation history per thread ─────────────
# Stores the FULL thread history — no cap, no trimming
# { thread_id: [ {"role": "user"/"assistant", "content": "..."}, ... ] }
thread_history: dict[int, list] = {}

def get_history(thread_id: int) -> list:
    return thread_history.get(thread_id, [])

def add_to_history(thread_id: int, role: str, content: str):
    if thread_id not in thread_history:
        thread_history[thread_id] = []
    thread_history[thread_id].append({"role": role, "content": content})

def clear_history(thread_id: int):
    if thread_id in thread_history:
        del thread_history[thread_id]
        return True
    return False

# ─── Groq API Call ─────────────────────────────────────────
def call_groq(user_message: str, conversation_history: list = None) -> str:
    # Crisis check first
    message_lower = user_message.lower()
    if any(keyword in message_lower for keyword in CRISIS_KEYWORDS):
        return CRISIS_RESPONSE

    # Build full message list: system + entire thread history + new message
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.85,
        "top_p": 0.9,
        "max_tokens": 300
    }

    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "I'm here... just taking a breath. Try again in a moment?"
    except requests.exceptions.HTTPError as e:
        print(f"Groq HTTP error: {e}")
        return "I'm here with you... something went quiet on my end. Try again?"
    except Exception as e:
        print(f"Groq API error: {e}")
        return "I'm here with you... sometimes words are hard to find, but I'm listening."

# ─── Bot Ready ─────────────────────────────────────────────
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("─── Zoya is online and listening. ───")

# ─── Unified Session Starter ───────────────────────────────
async def start_session(interaction: discord.Interaction, message: str, session_type: str):
    await interaction.response.defer(ephemeral=True)

    user_name = interaction.user.name.replace(" ", "")
    thread_name = f"{user_name}'s {session_type} with Zoya"

    try:
        # Get Zoya's first response (no history yet)
        response = call_groq(message)

        # Create the thread
        thread = await interaction.channel.create_thread(
            name=thread_name,
            auto_archive_duration=1440,  # 24 hours
            type=discord.ChannelType.public_thread,
            reason=f"Zoya {session_type.lower()} session for {interaction.user.name}"
        )

        # Save opening exchange to history
        add_to_history(thread.id, "user", message)
        add_to_history(thread.id, "assistant", response)

        # Send opening message in thread
        await thread.send(
            f"Hey {interaction.user.mention}, this is your space.\n"
            f"Say whatever you need to... I'm here.\n\n"
            f"{response}\n\n"
            f"-# Gentle note — I'm not a human therapist. Our chats aren't confidential like real therapy. "
            f"Use `/close` whenever you're done."
        )

        # Confirm to user (only they see this)
        await interaction.followup.send(
            f"Your thread is ready: {thread.mention}\n"
            f"Just talk there whenever you're ready ❤️",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to create threads here.\n"
            "Please give me **Manage Threads** + **Create Public Threads** permissions.",
            ephemeral=True
        )
    except Exception as e:
        print(f"Thread creation error: {e}")
        await interaction.followup.send(
            "Something went wrong creating your thread... try again?",
            ephemeral=True
        )

# ─── Slash Commands ────────────────────────────────────────
@bot.tree.command(name="vent", description="Start venting — Zoya will make a thread for you")
@app_commands.describe(message="What's on your mind?")
async def vent(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Vent")

@bot.tree.command(name="talk", description="Start a calm conversation with Zoya")
@app_commands.describe(message="How are you feeling?")
async def talk(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Talk")

@bot.tree.command(name="rant", description="Let it all out — Zoya will make a thread")
@app_commands.describe(message="What's frustrating you?")
async def rant(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Rant")

# ─── Auto-reply in Zoya Threads ────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Only respond in threads
    if not isinstance(message.channel, discord.Thread):
        return

    # Only respond in Zoya threads
    if not message.channel.name.endswith("with Zoya"):
        return

    async with message.channel.typing():
        # Pass the FULL thread history to Groq
        history = get_history(message.channel.id)
        response = call_groq(message.content, history)

        # Save this exchange to history
        add_to_history(message.channel.id, "user", message.content)
        add_to_history(message.channel.id, "assistant", response)

        await message.channel.send(response)

    await bot.process_commands(message)

# ─── Close Command ─────────────────────────────────────────
@bot.tree.command(name="close", description="End your Zoya session and clear all memory")
async def close(interaction: discord.Interaction):
    # Must be inside a thread
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "This command only works inside a Zoya thread.",
            ephemeral=True
        )
        return

    # Must be a Zoya thread
    if not interaction.channel.name.endswith("with Zoya"):
        await interaction.response.send_message(
            "This doesn't look like a Zoya thread.",
            ephemeral=True
        )
        return

    # Clear the full conversation memory for this thread
    was_cleared = clear_history(interaction.channel.id)

    if was_cleared:
        await interaction.response.send_message(
            "Session closed and all memory cleared.\n"
            "Take care of yourself... you did something good by talking today. ❤️"
        )
    else:
        await interaction.response.send_message(
            "Closing this space... nothing stored to clear.\n"
            "Take care. ❤️"
        )

    # Archive and lock the thread
    await interaction.channel.edit(archived=True, locked=True)

# ─── Run ───────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)


