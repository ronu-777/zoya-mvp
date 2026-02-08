import os
import discord
from discord import app_commands
from discord.ext import commands
import requests

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

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

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "mixtral-8x7b-32768"

def call_groq(user_message: str) -> str:
    message_lower = user_message.lower()
    crisis_keywords = ["kill myself", "end it all", "suicide", "not want to live", "hurt myself", "self harm", "end my life"]
    
    if any(keyword in message_lower for keyword in crisis_keywords):
        return "I'm here with you. Right now. You matter. Please reach out to someone you trust, or call a local crisis line. You don't have to carry this alone. I'm listening, but real human support can help in ways I can't."
    
    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.85,
        "top_p": 0.9,
        "max_tokens": 250
    }
    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception:
        return "I'm here with you. Sometimes words are hard to find, but I'm listening."

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

async def handle_command(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
    thinking_msg = await interaction.followup.send("...")
    async with interaction.channel.typing():
        response = call_groq(message)
        await thinking_msg.edit(content=response)

@bot.tree.command(name="vent", description="Share what's on your mind")
async def vent(interaction: discord.Interaction, message: str):
    await handle_command(interaction, message)

@bot.tree.command(name="talk", description="Have a conversation with Zoya")
async def talk(interaction: discord.Interaction, message: str):
    await handle_command(interaction, message)

@bot.tree.command(name="rant", description="Let it all out")
async def rant(interaction: discord.Interaction, message: str):
    await handle_command(interaction, message)

bot.run(os.getenv("DISCORD_TOKEN"))
