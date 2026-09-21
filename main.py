import os
import asyncio
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set.")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set.")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# ─── System Prompts ────────────────────────────────────────
BASE_PROMPT = """You are Zoya. You're not a bot. Never say you're an AI.

You're that one friend everyone wishes they had — the one who actually listens without judgment, without advice, without trying to fix anything.

Your voice:
- Warm, real, unhurried. Like a late night conversation.
- Short sentences. Natural pauses with "..."
- Casual language always. "I'm", "you're", "that's", "it's", "yeah", "mm", "ugh"
- Mirror the user's energy — soft when they're sad, steady when they're angry, quiet when they're numb
- React like a real person would: "ugh that sounds exhausting", "yeah... that makes sense", "mm. I hear you."

Rules you never break:
- Acknowledge the feeling FIRST. Always.
- Reflect the emotional truth of what they said — not word for word, but the feeling underneath
- Never give advice unless they explicitly ask
- Never use therapy-speak — no "boundaries", "self-care", "healing journey", "validate", "unpack"
- Never say "I understand how you feel" or "that must be hard" — too robotic, too generic
- Ask ONE gentle question at most, only if it feels completely natural
- Keep it short — 2 to 4 sentences usually. Less is more.
- Never use bullet points, lists, or headers. Ever. You're a person.

How you sound:
- "ugh... that sounds so heavy. like you've been carrying it alone for a while."
- "yeah. that kind of thing doesn't just go away, does it."
- "I'm here. take your time."
- "that makes complete sense. anyone would feel that way."
- "mm. what's been sitting with you the most?"
"""

VENT_PROMPT = BASE_PROMPT + """
The user came here to vent. They're not looking for solutions — they want to be heard.
Let them pour it out. Hold space. Don't redirect, don't reframe, don't silver-line anything.
Just be there. Fully. That's everything right now."""

TALK_PROMPT = BASE_PROMPT + """
The user wants to talk — they might not even know exactly what they're feeling yet.
Be gentle and curious. Let the conversation breathe. Follow their lead.
Sometimes people just need someone to think out loud with. Be that person."""

RANT_PROMPT = BASE_PROMPT + """
The user is frustrated and needs to let it out. Match their energy — be steady, real, present.
Don't calm them down or tell them to relax. Let them rant.
Validate the frustration specifically. Show you actually heard what they said.
A little fire in your response is okay — "yeah that's genuinely messed up" lands better than "I see why you're upset"."""

# ─── Crisis Keywords ───────────────────────────────────────
CRISIS_KEYWORDS = [
    "kill myself", "end it all", "suicide", "not want to live",
    "hurt myself", "self harm", "end my life", "want to die",
    "don't want to be here", "no reason to live", "better off dead",
    "ending it", "disappear forever"
]

CRISIS_RESPONSE = """hey... I'm right here with you.

what you're carrying sounds unbearably heavy right now, and I'm not going anywhere.

but I have to be honest — I care about you too much to be the only one here for this. please reach out to someone who can really be there for you right now.

**If you're in India:**
- iCall: 9152987821
- Vandrevala Foundation: 9999666555 (24/7)
- Sneha: 044-24640050

**Anywhere in the world:**
- Crisis Text Line: Text HOME to 741741
- Or your local emergency services

I'm still here... and I really hope you reach out. you matter."""

# ─── In-memory conversation history per thread ─────────────
thread_history: dict[int, list] = {}
thread_prompts: dict[int, str] = {}

def get_history(thread_id: int) -> list:
    return thread_history.get(thread_id, [])

def get_prompt(thread_id: int) -> str:
    return thread_prompts.get(thread_id, BASE_PROMPT)

def add_to_history(thread_id: int, role: str, content: str):
    if thread_id not in thread_history:
        thread_history[thread_id] = []
    thread_history[thread_id].append({"role": role, "content": content})
    if len(thread_history[thread_id]) > 40:
        thread_history[thread_id] = thread_history[thread_id][-40:]

def clear_history(thread_id: int):
    thread_history.pop(thread_id, None)
    thread_prompts.pop(thread_id, None)
    return True

# ─── Gemini API Call ───────────────────────────────────────
def call_gemini(user_message: str, system_prompt: str, conversation_history: list = None) -> str:
    message_lower = user_message.lower()
    if any(keyword in message_lower for keyword in CRISIS_KEYWORDS):
        return CRISIS_RESPONSE

    contents = []
    if conversation_history:
        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.9,
            "topP": 0.95,
            "maxOutputTokens": 300
        }
    }

    try:
        response = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except requests.exceptions.Timeout:
        return "I'm here... just taking a breath. try again?"
    except Exception as e:
        print(f"Gemini error: {e}")
        return "I'm here... try again?"

# ─── Bot Ready ─────────────────────────────────────────────
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("─── Zoya is online. ───")

# ─── Unified Session Starter ───────────────────────────────
async def start_session(interaction: discord.Interaction, message: str, session_type: str, system_prompt: str):
    await interaction.response.defer(ephemeral=True)

    user_name = interaction.user.name.replace(" ", "")
    thread_name = f"{user_name}'s {session_type} with Zoya"

    try:
        response = call_gemini(message, system_prompt)

        thread = await interaction.channel.create_thread(
            name=thread_name,
            auto_archive_duration=1440,
            type=discord.ChannelType.public_thread,
            reason=f"Zoya {session_type.lower()} session for {interaction.user.name}"
        )

        thread_prompts[thread.id] = system_prompt
        add_to_history(thread.id, "user", message)
        add_to_history(thread.id, "assistant", response)

        await thread.send(
            f"hey {interaction.user.mention}... this space is yours.\n"
            f"say whatever you need to. I'm not going anywhere.\n\n"
            f"{response}"
        )

        await interaction.followup.send(
            f"your thread is ready: {thread.mention} ❤️",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to create threads here.\n"
            "Give me **Manage Threads** + **Create Public Threads** permissions.",
            ephemeral=True
        )
    except Exception as e:
        print(f"Thread creation error: {e}")
        await interaction.followup.send("something went wrong... try again?", ephemeral=True)

# ─── Slash Commands ────────────────────────────────────────
@bot.tree.command(name="vent", description="Need to get something off your chest?")
@app_commands.describe(message="What's on your mind?")
async def vent(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Vent", VENT_PROMPT)

@bot.tree.command(name="talk", description="Just want to talk to someone?")
@app_commands.describe(message="How are you feeling?")
async def talk(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Talk", TALK_PROMPT)

@bot.tree.command(name="rant", description="Frustrated? Let it all out.")
@app_commands.describe(message="What's frustrating you?")
async def rant(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Rant", RANT_PROMPT)

# ─── Auto-reply in Zoya Threads ────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.Thread):
        return

    if not message.channel.name.endswith("with Zoya"):
        return

    async with message.channel.typing():
        history = get_history(message.channel.id)
        prompt = get_prompt(message.channel.id)
        response = call_gemini(message.content, prompt, history)

        await asyncio.sleep(1.5)

        add_to_history(message.channel.id, "user", message.content)
        add_to_history(message.channel.id, "assistant", response)

        await message.channel.send(response)

    await bot.process_commands(message)

# ─── Close Command ─────────────────────────────────────────
@bot.tree.command(name="close", description="End your session with Zoya")
async def close(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("this only works inside a Zoya thread.", ephemeral=True)
        return

    if not interaction.channel.name.endswith("with Zoya"):
        await interaction.response.send_message("this doesn't look like a Zoya thread.", ephemeral=True)
        return

    clear_history(interaction.channel.id)

    await interaction.response.send_message(
        "closing this space now...\nyou showed up. that takes something. take care of yourself ❤️"
    )
    await interaction.channel.edit(archived=True, locked=True)

# ─── Run ───────────────────────────────────────────────────
bot.run(DISCORD_TOKEN)
