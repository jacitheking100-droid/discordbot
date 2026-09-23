import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import time
import re
import asyncio


# =========================================================
# הגדרות
# =========================================================

XP_PER_MESSAGE = 50
XP_COOLDOWN = 60

STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "KING FOX"
}

DATABASE = "bot_data.db"


# =========================================================
# Database
# =========================================================

db = sqlite3.connect(DATABASE)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    warnings INTEGER DEFAULT 0
)
""")

db.commit()


# =========================================================
# Bot
# =========================================================

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


# =========================================================
# פונקציות
# =========================================================

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


def is_staff(member):
    if not isinstance(member, discord.Member):
        return False

    return any(
        role.name.upper() in STAFF_ROLES
        for role in member.roles
    )


# =========================================================
# התחברות
# =========================================================

@bot.event
async def on_ready():

    try:
        synced = await bot.tree.sync()

        print(
            f"סונכרנו {len(synced)} פקודות Slash."
        )

    except Exception as e:

        print(
            f"שגיאה בסנכרון פקודות: {e}"
        )

    print(
        f"הבוט מחובר בתור {bot.user}"
    )


# =========================================================
# XP + בדיקת קישורים
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    user_id = message.author.id
    current_time = time.time()

    # 50 XP פעם ב-60 שניות
    if (
        user_id not in last_xp
        or current_time - last_xp[user_id] >= XP_COOLDOWN
    ):

        add_xp(
            user_id,
            XP_PER_MESSAGE
        )

        last_xp[user_id] = current_time

    # בדיקת קישורים
    url_pattern = r"(https?://\S+|www\.\S+)"

    if re.search(
        url_pattern,
        message.content,
        re.IGNORECASE
    ):

        try:

            await message.delete()

            warning_number = add_warning(
                message.author.id
            )

            try:

                await message.author.send(
                    "⚠️ **קיבלת אזהרה**\n\n"
                    "שליחת קישורים אינה מותרת בשרת.\n"
                    "ההודעה שלך נמחקה באופן אוטומטי.\n\n"
                    f"מספר האזהרות שלך: **{warning_number}**"
                )

            except discord.Forbidden:
                pass

        except discord.Forbidden:
            pass

        except Exception as e:

            print(
                f"שגיאה בטיפול בקישור: {e}"
            )

        return

    await bot.process_commands(message)


# =========================================================
# /xp
# =========================================================

@bot.tree.command(
    name="xp",
    description="מציג את כמות ה-XP האישית שלך"
)
@app_commands.guild_only()
async def xp_command(
    interaction: discord.Interaction
):

    xp = get_xp(
        interaction.user.id
    )

    embed = discord.Embed(
        title="📊 ה־XP שלך",
        description=(
            f"יש לך כרגע **{xp} XP**."
        ),
        color=discord.Color.blue()
    )

    embed.set_footer(
        text="המידע הזה גלוי רק לך."
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /warnings
# =========================================================

@bot.tree.command(
    name="warnings",
    description="מציג את מספר האזהרות האישיות שלך"
)
@app_commands.guild_only()
async def warnings_command(
    interaction: discord.Interaction
):

    warnings = get_warnings(
        interaction.user.id
    )

    embed = discord.Embed(
        title="⚠️ האזהרות שלך",
        description=(
            f"יש לך כרגע **{warnings} אזהרות**."
        ),
        color=discord.Color.orange()
    )

    embed.set_footer(
        text="המידע הזה גלוי רק לך."
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /warn
# =========================================================

@bot.tree.command(
    name="warn",
    description="נותן אזהרה למשתמש"
)
@app_commands.describe(
    member="המשתמש שיקבל את האזהרה",
    reason="הסיבה לאזהרה"
)
@app_commands.guild_only()
async def warn_command(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str
):

    # בדיקת הרשאות
    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    # אי אפשר להזהיר בוט
    if member.bot:

        await interaction.response.send_message(
            "❌ אי אפשר לתת אזהרה לבוט.",
            ephemeral=True
        )

        return

    # אי אפשר להזהיר את עצמך
    if member.id == interaction.user.id:

        await interaction.response.send_message(
            "❌ אי אפשר לתת אזהרה לעצמך.",
            ephemeral=True
        )

        return

    warning_number = add_warning(
        member.id
    )

    # הודעה פרטית לצוות
    embed = discord.Embed(
        title="⚠️ אזהרה ניתנה",
        color=discord.Color.orange()
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
        value=str(warning_number),
        inline=False
    )

    embed.set_footer(
        text="ההודעה הזאת גלויה רק לך."
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )

    # DM למשתמש
    try:

        dm_embed = discord.Embed(
            title="⚠️ קיבלת אזהרה",
            color=discord.Color.orange()
        )

        dm_embed.add_field(
            name="שרת",
            value=interaction.guild.name,
            inline=False
        )

        dm_embed.add_field(
            name="סיבה",
            value=reason,
            inline=False
        )

        dm_embed.add_field(
            name="מספר אזהרות",
            value=str(warning_number),
            inline=False
        )

        await member.send(
            embed=dm_embed
        )

    except discord.Forbidden:
        pass


# =========================================================
# /ticket
# =========================================================

@bot.tree.command(
    name="ticket",
    description="פותח את מערכת הטיקטים"
)
@app_commands.guild_only()
async def ticket_command(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🎫 מערכת טיקטים",
        description=(
            "צריכים עזרה?\n\n"
            "לחצו על **פתיחת טיקט** "
            "כדי לפתוח פנייה חדשה."
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


# =========================================================
# כפתור פתיחת טיקט
# =========================================================

class TicketView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="פתיחת טיקט",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="open_ticket"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "🎫 **בחר את סוג הטיקט:**",
            view=TicketTypeView(),
            ephemeral=True
        )


# =========================================================
# בחירת סוג טיקט
# =========================================================

class TicketTypeView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=60
        )

    @discord.ui.select(
        placeholder="בחר סוג טיקט...",
        custom_id="ticket_type",

        options=[

            discord.SelectOption(
                label="באג",
                description="דיווח על באג או תקלה בשרת",
                emoji="🐛",
                value="bug"
            ),

            discord.SelectOption(
                label="התקבלות לצוות",
                description="בקשה להצטרפות לצוות השרת",
                emoji="👮",
                value="staff"
            ),

            discord.SelectOption(
                label="דיווח על משתמש",
                description="דיווח על משתמש שעבר על חוקי השרת",
                emoji="🚨",
                value="report"
            )
        ]
    )
    async def select_ticket(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select
    ):

        ticket_types = {

            "bug": "באג",

            "staff": "התקבלות לצוות",

            "report": "דיווח על משתמש"
        }

        ticket_type = ticket_types[
            select.values[0]
        ]

        guild = interaction.guild

        # בדיקה אם כבר יש טיקט
        existing_channel = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{interaction.user.id}"
        )

        if existing_channel:

            await interaction.response.send_message(
                f"❌ כבר יש לך טיקט פתוח: "
                f"{existing_channel.mention}",
                ephemeral=True
            )

            return

        # מציאת קטגוריית Tickets
        category = discord.utils.get(
            guild.categories,
            name="Tickets"
        )

        if category is None:

            category = await guild.create_category(
                "Tickets"
            )

        # הרשאות
        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )
        }

        # הרשאות לצוות
        for role in guild.roles:

            if role.name.upper() in STAFF_ROLES:

                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        # יצירת הטיקט
        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.id}",
            category=category,
            overwrites=overwrites
        )

        # הודעת הטיקט
        embed = discord.Embed(
            title="🎫 טיקט חדש",

            description=(
                f"**סוג הטיקט:** {ticket_type}\n\n"
                f"**נפתח על ידי:** "
                f"{interaction.user.mention}\n\n"
                "צוות השרת יטפל בפנייה בהקדם.\n\n"
                "איש צוות יכול ללחוץ על "
                "**לקחת טיפול** כדי לקחת אחריות "
                "על הטיקט."
            ),

            color=discord.Color.blue()
        )

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ הטיקט שלך נפתח: "
            f"{channel.mention}",
            ephemeral=True
        )


# =========================================================
# כפתורי הטיקט
# =========================================================

class TicketControlView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # =====================================================
    # לקחת טיפול
    # =====================================================

    @discord.ui.button(
        label="לקחת טיפול",
        style=discord.ButtonStyle.success,
        emoji="👤",
        custom_id="take_ticket"
    )
    async def take_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # רק MOD ומעלה
        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ רק MOD ומעלה יכולים לקחת טיפול בטיקט.",
                ephemeral=True
            )

            return

        # הודעה בצ'אט
        await interaction.response.send_message(
            f"🎫 **{interaction.user.mention} "
            f"לקח טיפול בטיקט הזה.**"
        )

        # ביטול הכפתור כדי שלא ייקחו טיפול שוב
        button.disabled = True

        await interaction.message.edit(
            view=self
        )

    # =====================================================
    # סגירת טיקט
    # =====================================================

    @discord.ui.button(
        label="סגירת טיקט",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # רק MOD ומעלה
        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ רק MOD ומעלה יכולים לסגור טיקט.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 **הטיקט ייסגר בעוד 3 שניות.**"
        )

        await asyncio.sleep(3)

        try:

            await interaction.channel.delete()

        except discord.NotFound:
            pass


# =========================================================
# הפעלת הבוט
# =========================================================

TOKEN = os.environ["DISCORD_TOKEN"]

bot.run(TOKEN)