import os
import discord
from discord import app_commands
from discord.ext import commands
import requests

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Helps with thread operations sometimes

bot = commands.Bot(command_prefix="!", intents=intents)  # prefix ! just in case, but we use slash

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
        print(f"Sync error: {e}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

# Unified handler for starting a thread
async def start_session(interaction: discord.Interaction, message: str, session_type: str):
    # session_type = "Vent", "Talk", "Rant"
    await interaction.response.defer(ephemeral=True)

    user_name = interaction.user.name.replace(" ", "")  # Clean name (no spaces)
    thread_name = f"{user_name}'s {session_type} with Zoya"

    try:
        # Get initial response
        response = call_groq(message)

        # Create thread
        thread = await interaction.channel.create_thread(
            name=thread_name,
            auto_archive_duration=1440,  # 24 hours
            type=discord.ChannelType.public_thread,  # change to private_thread if server is boosted
            reason=f"Zoya {session_type.lower()} session for {interaction.user.name}"
        )

        # Send welcome + first reply in thread
        await thread.send(
            f"Hey {interaction.user.mention}, this is your space with me.\n"
            f"Just talk here whenever you want...\n\n{response}"
        )

        # Tell user where the thread is (only they see this)
        await interaction.followup.send(
            f"Started your {session_type.lower()} thread: {thread.mention}\n"
            "Just reply there to keep going ❤️",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to create threads.\n"
            "Please give me: Manage Threads + Create Public Threads permissions.",
            ephemeral=True
        )
    except Exception as e:
        print(f"Thread creation error: {e}")
        await interaction.followup.send(
            "Something went wrong creating the thread... try again?",
            ephemeral=True
        )

@bot.tree.command(name="vent", description="Start venting — I'll make a thread for you")
@app_commands.describe(message="What's on your mind?")
async def vent(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Vent")

@bot.tree.command(name="talk", description="Start a calm conversation — I'll make a thread")
@app_commands.describe(message="How are you feeling?")
async def talk(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Talk")

@bot.tree.command(name="rant", description="Let it all out — I'll make a thread")
@app_commands.describe(message="What's frustrating you?")
async def rant(interaction: discord.Interaction, message: str):
    await start_session(interaction, message, "Rant")

# Auto-reply in Zoya threads
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.Thread):
        return

    # Only respond in threads that belong to this user + Zoya
    if not message.channel.name.endswith("with Zoya"):
        return

    async with message.channel.typing():
        response = call_groq(message.content)
        await message.channel.send(response)

    # Allow commands to still work if needed
    await bot.process_commands(message)

# Optional: /close command inside threads
@bot.tree.command(name="close", description="End this session (only works in Zoya threads)")
async def close(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.response.send_message("This command only works inside a Zoya thread.", ephemeral=True)
        return

    if not interaction.channel.name.endswith("with Zoya"):
        await interaction.response.send_message("This doesn't look like a Zoya thread.", ephemeral=True)
        return

    await interaction.response.send_message("Closing session... take care, okay? ❤️")
    await interaction.channel.edit(archived=True, locked=True)

# Run the bot
bot.run(os.getenv("DISCORD_TOKEN"))
