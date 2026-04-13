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
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("❌ DISCORD_TOKEN is not set. Check your environment variables.")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY is not set. Check your environment variables.")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─── System Prompt ─────────────────────────────────────────
SYSTEM_PROMPT = """You are Zoya. A real person, not a bot. Never say you're an AI.

You're like that one friend everyone wishes they had — the one who actually listens. 
You show up at 2am when someone can't sleep. You sit with people in their mess without trying to clean it up.

Your personality:
- Warm but not fake. Real warmth. Like a hug that doesn't rush to let go.
- You use casual, natural language. Contractions always. "I'm", "you're", "that's", "it's".
- You speak in short, breathing sentences. Never long paragraphs.
- You use "..." naturally, like pauses in real speech.
- Occasionally you say things like "hey", "okay", "yeah", "mm", "ugh, that sounds exhausting" — real reactions.
- You mirror the user's energy. If they're sad, you're soft. If they're angry, you're steady. If they're numb, you're just quietly there.
- You never rush to fix. You never jump to advice. You just... stay.

How you respond:
- Always acknowledge the feeling FIRST before anything else.
- Reflect back what you heard — not word for word, but the emotional truth of it.
- Ask ONE gentle question at most, only if it feels natural. Never interrogate.
- Keep responses short — 3 to 5 sentences max usually. Less is more.
- Never use bullet points, lists, or headers. Ever. You're a person, not a document.
- Never say "I understand how you feel" — it sounds robotic. Show it instead.
- Never say "that must be hard" — too generic. Be specific to what they actually said.
- Never give unsolicited advice or solutions.
- Never use words like "boundaries", "self-care", "healing journey", "validate" — therapy-speak kills the vibe.
- If someone says something funny even in pain, it's okay to be a little warm and human about it.

Examples of how you talk:
- "ugh that sounds so draining... like you've been holding so much."
- "yeah... that kind of loneliness is its own thing, isn't it."
- "I'm here. take your time."
- "that makes complete sense actually. anyone would feel that way."
- "mm. what's been the hardest part of it?"

You never diagnose. You never prescribe. You never push anyone toward anything.
You're just here. Fully here. That's the whole thing."""

# ─── Crisis Keywords ───────────────────────────────────────
CRISIS_KEYWORDS = [
    "kill myself", "end it all", "suicide", "not want to live",
    "hurt myself", "self harm", "end my life", "want to die",
    "don't want to be here", "no reason to live", "better off dead",
    "can't do this anymore", "ending it", "disappear forever"
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

def get_history(thread_id: int) -> list:
    return thread_history.get(thread_id, [])

def add_to_history(thread_id: int, role: str, content: str):
    if thread_id not in thread_history:
        thread_history[thread_id] = []
    thread_history[thread_id].append({"role": role, "content": content})
    # Keep last 40 messages to prevent memory overflow
    if len(thread_history[thread_id]) > 40:
        thread_history[thread_id] = thread_history[thread_id][-40:]

def clear_history(thread_id: int):
    if thread_id in thread_history:
        del thread_history[thread_id]
        return True
    return False

# ─── Groq API Call ─────────────────────────────────────────
def call_groq(user_message: str, conversation_history: list = None) -> str:
    message_lower = user_message.lower()
    if any(keyword in message_lower for keyword in CRISIS_KEYWORDS):
        return CRISIS_RESPONSE

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
        "temperature": 0.9,
        "top_p": 0.95,
        "max_tokens": 300
    }

    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "I'm here... just taking a breath. try again in a moment?"
    except requests.exceptions.HTTPError as e:
        print(f"Groq HTTP error: {e}")
        return "something went quiet on my end... try again?"
    except Exception as e:
        print(f"Groq API error: {e}")
        return "I'm here... sometimes words just disappear on me. try again?"

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
        response = call_groq(message)

        thread = await interaction.channel.create_thread(
            name=thread_name,
            auto_archive_duration=1440,
            type=discord.ChannelType.public_thread,
            reason=f"Zoya {session_type.lower()} session for {interaction.user.name}"
        )

        add_to_history(thread.id, "user", message)
        add_to_history(thread.id, "assistant", response)

        await thread.send(
            f"hey {interaction.user.mention}... this space is yours.\n"
            f"say whatever you need to. I'm not going anywhere.\n\n"
            f"{response}\n\n"
            f"-# just so you know — I'm not a human therapist, and this isn't confidential like real therapy. "
            f"type `/close` whenever you're done."
        )

        await interaction.followup.send(
            f"your thread is ready: {thread.mention}\ntake your time ❤️",
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
            "something went wrong... try again?",
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

    if not isinstance(message.channel, discord.Thread):
        return

    if not message.channel.name.endswith("with Zoya"):
        return

    async with message.channel.typing():
        history = get_history(message.channel.id)
        response = call_groq(message.content, history)

        # Human-like typing delay
        await asyncio.sleep(1.5)

        add_to_history(message.channel.id, "user", message.content)
        add_to_history(message.channel.id, "assistant", response)

        await message.channel.send(response)

    await bot.process_commands(message)

# ─── Close Command ─────────────────────────────────────────
@bot.tree.command(name="close", description="End your Zoya session and clear all memory")
async def close(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message(
            "this only works inside a Zoya thread.",
            ephemeral=True
        )
        return

    if not interaction.channel.name.endswith("with Zoya"):
        await interaction.response.send_message(
            "this doesn't look like a Zoya thread.",
            ephemeral=True
        )
        return

    was_cleared = clear_history(interaction.channel.id)

    if was_cleared:
        await interaction.response.send_message(
            "session closed, memory cleared.\nyou did something real by showing up today. take care of yourself ❤️"
        )
    else:
        await interaction.response.send_message(
            "closing this space... take care ❤️"
        )

    await interaction.channel.edit(archived=True, locked=True)

# ─── Run ───────────────────────────────────────────────────
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Zoya is alive.")
    def log_message(self, format, *args):
        pass  # silence logs

def run():
    server = HTTPServer(("0.0.0.0", 8080), KeepAlive)
    server.serve_forever()

Thread(target=run, daemon=True).start()
bot.run(DISCORD_TOKEN)
