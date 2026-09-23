import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import time
import re
import asyncio

# =========================
# הגדרות
# =========================

XP_PER_MESSAGE = 50
XP_COOLDOWN = 60

GUILD_ID = 1552344386526908488
GUILD = discord.Object(id=GUILD_ID)

STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "KING FOX"
}

# =========================
# Database
# =========================

db = sqlite3.connect("bot_data.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    warnings INTEGER DEFAULT 0
)
""")

db.commit()

# =========================
# Intents
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

last_xp = {}

# =========================
# Database Functions
# =========================

def ensure_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, xp, warnings) VALUES (?, 0, 0)",
        (user_id,)
    )
    db.commit()


def get_xp(user_id):
    ensure_user(user_id)

    cursor.execute(
        "SELECT xp FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()
    return result[0] if result else 0


def get_warnings(user_id):
    ensure_user(user_id)

    cursor.execute(
        "SELECT warnings FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()
    return result[0] if result else 0


def add_xp(user_id, amount):
    ensure_user(user_id)

    cursor.execute(
        "UPDATE users SET xp = xp + ? WHERE user_id = ?",
        (amount, user_id)
    )

    db.commit()


def add_warning(user_id):
    ensure_user(user_id)

    cursor.execute(
        "UPDATE users SET warnings = warnings + 1 WHERE user_id = ?",
        (user_id,)
    )

    db.commit()

    return get_warnings(user_id)


# =========================
# Staff Check
# =========================

def is_staff(member):
    if not isinstance(member, discord.Member):
        return False

    return any(
        role.name.upper() in STAFF_ROLES
        for role in member.roles
    )


# =========================
# Ticket Panel
# =========================

class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="פתיחת טיקט",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="open_ticket"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "בחר את סוג הפנייה שלך:",
            view=TicketTypeView(),
            ephemeral=True
        )


# =========================
# Ticket Type
# =========================

class TicketTypeView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        placeholder="בחר סוג פנייה...",
        options=[
            discord.SelectOption(
                label="באג",
                description="דיווח על תקלה או באג",
                emoji="🐛",
                value="bug"
            ),
            discord.SelectOption(
                label="התקבלות לצוות",
                description="בקשה להצטרף לצוות השרת",
                emoji="👮",
                value="staff"
            ),
            discord.SelectOption(
                label="דיווח על משתמש",
                description="דיווח על משתמש שעובר על חוקי השרת",
                emoji="🚨",
                value="report"
            )
        ]
    )
    async def ticket_type(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select
    ):

        guild = interaction.guild
        user = interaction.user

        existing_channel = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{user.id}"
        )

        if existing_channel:

            await interaction.response.send_message(
                f"❌ כבר יש לך טיקט פתוח: {existing_channel.mention}",
                ephemeral=True
            )

            return

        category = discord.utils.get(
            guild.categories,
            name="Tickets"
        )

        if category is None:

            category = await guild.create_category("Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),

            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            )
        }

        for role in guild.roles:

            if role.name.upper() in STAFF_ROLES:

                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel = await guild.create_text_channel(
            name=f"ticket-{user.id}",
            category=category,
            overwrites=overwrites
        )

        ticket_names = {
            "bug": "🐛 באג",
            "staff": "👮 התקבלות לצוות",
            "report": "🚨 דיווח על משתמש"
        }

        ticket_name = ticket_names.get(
            select.values[0],
            "פנייה"
        )

        embed = discord.Embed(
            title="🎫 טיקט חדש",
            description=(
                f"שלום {user.mention}\n\n"
                f"**סוג הפנייה:** {ticket_name}\n\n"
                "צוות השרת יטפל בפנייה בהקדם האפשרי.\n"
                "אין צורך לתייג את הצוות ללא צורך."
            ),
            color=discord.Color.blue()
        )

        embed.set_footer(
            text="מערכת הטיקטים"
        )

        await channel.send(
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ הטיקט נפתח בהצלחה: {channel.mention}",
            ephemeral=True
        )


# =========================
# Ticket Controls
# =========================

class TicketControlView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="לקחת טיפול",
        emoji="👤",
        style=discord.ButtonStyle.success,
        custom_id="claim_ticket"
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ רק צוות יכול לקחת טיפול בטיקט.",
                ephemeral=True
            )

            return

        button.disabled = True

        await interaction.response.edit_message(
            view=self
        )

        await interaction.followup.send(
            f"👤 **{interaction.user.mention} לקח טיפול בטיקט הזה.**"
        )


    @discord.ui.button(
        label="סגירת טיקט",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ רק צוות יכול לסגור טיקט.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 **הטיקט ייסגר בעוד 3 שניות.**"
        )

        await asyncio.sleep(3)

        try:
            await interaction.channel.delete()
        except:
            pass


# =========================
# Slash Commands
# =========================

@bot.tree.command(
    name="xp",
    description="בדיקת כמות ה-XP שלך",
    guild=GUILD
)
async def xp_command(interaction: discord.Interaction):

    xp = get_xp(interaction.user.id)

    embed = discord.Embed(
        title="📊 ה-XP שלך",
        description=f"יש לך כרגע **{xp} XP**.",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(
    name="warnings",
    description="בדיקת מספר האזהרות שלך",
    guild=GUILD
)
async def warnings_command(interaction: discord.Interaction):

    warnings = get_warnings(interaction.user.id)

    embed = discord.Embed(
        title="⚠️ האזהרות שלך",
        description=f"יש לך כרגע **{warnings} אזהרות**.",
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(
    name="warn",
    description="מתן אזהרה למשתמש",
    guild=GUILD
)
@app_commands.describe(
    member="המשתמש שיקבל את האזהרה",
    reason="סיבת האזהרה"
)
async def warn_command(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    warnings = add_warning(member.id)

    embed = discord.Embed(
        title="⚠️ אזהרה ניתנה",
        color=discord.Color.red()
    )

    embed.add_field(
        name="משתמש",
        value=member.mention,
        inline=False
    )

    embed.add_field(
        name="סיבה",
        value=reason,
        inline=False
    )

    embed.add_field(
        name="מספר אזהרות",
        value=str(warnings),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )

    try:

        await member.send(
            f"""⚠️ **קיבלת אזהרה**

שרת: **{interaction.guild.name}**

סיבה:
{reason}

מספר האזהרות שלך: **{warnings}**"""
        )

    except:
        pass


@bot.tree.command(
    name="ticket",
    description="שליחת פאנל פתיחת טיקט",
    guild=GUILD
)
async def ticket_command(
    interaction: discord.Interaction
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק צוות יכול לשלוח את פאנל הטיקטים.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎫 מערכת הטיקטים",
        description=(
            "ברוכים הבאים למערכת התמיכה.\n\n"
            "כדי לפתוח טיקט, לחצו על הכפתור "
            "**פתיחת טיקט** ובחרו את סוג הפנייה שלכם.\n\n"
            "🐛 **באג**\n"
            "דיווח על תקלה או בעיה.\n\n"
            "👮 **התקבלות לצוות**\n"
            "בקשה להצטרף לצוות השרת.\n\n"
            "🚨 **דיווח על משתמש**\n"
            "דיווח על משתמש שעובר על חוקי השרת."
        ),
        color=discord.Color.blue()
    )

    embed.set_footer(
        text="מערכת הטיקטים • צוות השרת"
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


# =========================
# XP + Links
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    user_id = message.author.id
    now = time.time()

    if (
        user_id not in last_xp
        or now - last_xp[user_id] >= XP_COOLDOWN
    ):
        add_xp(user_id, XP_PER_MESSAGE)
        last_xp[user_id] = now

    link_pattern = r"(https?://\S+|www\.\S+)"

    if re.search(
        link_pattern,
        message.content,
        re.IGNORECASE
    ):

        try:
            await message.delete()
        except:
            pass

        warnings = add_warning(user_id)

        try:

            await message.author.send(
                f"""⚠️ **אזהרה**

הודעה שלך נמחקה מכיוון שהיא הכילה קישור.

מספר האזהרות שלך: **{warnings}**

נא להקפיד על חוקי השרת."""
            )

        except:
            pass

        return

    await bot.process_commands(message)


# =========================
# Startup
# =========================

@bot.event
async def setup_hook():

    bot.add_view(TicketView())
    bot.add_view(TicketControlView())

    try:

        synced = await bot.tree.sync(
            guild=GUILD
        )

        print(
            f"סונכרנו {len(synced)} פקודות Slash לשרת"
        )

        for command in synced:
            print(f"/{command.name}")

    except Exception as e:

        print(
            f"שגיאה בסנכרון פקודות: {e}"
        )


@bot.event
async def on_ready():

    print("--------------------------------")
    print(f"הבוט מחובר בתור {bot.user}")
    print("--------------------------------")


# =========================
# Run
# =========================

TOKEN = os.environ.get("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN לא מוגדר ב-Railway"
    )

bot.run(TOKEN)