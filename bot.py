import discord
from discord import app_commands
from discord.ext import commands, tasks

import sqlite3
import asyncio
import time
import os
import random
import re
from datetime import timedelta

from collections import defaultdict, deque
from typing import Optional


# =========================================================
# CONFIG
# =========================================================

GUILD_ID = 1552344386526908488
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# =========================================================
# XP
# =========================================================

XP_PER_MESSAGE = 50
XP_COOLDOWN = 60
BOOSTER_XP_MULTIPLIER = 2
BOOST_REWARD_XP = 1000

# =========================================================
# CHANNELS
# =========================================================

WELCOME_CHANNEL_NAME = "ברוכים הבאים 👋"

BOOST_CHANNEL_NAME = "boost"

MOD_LOG_CHANNEL_NAME = "mod-logs"
MESSAGE_LOG_CHANNEL_NAME = "message-logs"

GAME_CHANNEL_NAME = "משחקים"

SUGGESTION_PANEL_CHANNEL_NAME = "הצעות"
SUGGESTIONS_CHANNEL_NAME = "📋・הצעות-שהוצעו"

TICKET_CATEGORY_NAME = "🎫・טיקטים"

# =========================================================
# ROLES
# =========================================================

VERIFIED_ROLE_NAME = "Member"
UPDATES_ROLE_NAME = "🔔・עדכונים והגרלות"

DAILY_SPECIAL_ROLE_NAME = "Daily Fox"

# =========================================================
# DAILY
# =========================================================

DAILY_REWARDS = {
    1: 10,
    2: 20,
    3: 50,
    4: 100,
    5: 150,
    6: 200,
}

# =========================================================
# ANTI SPAM
# =========================================================

SPAM_MESSAGE_LIMIT = 5
SPAM_TIME_WINDOW = 8
SPAM_TIMEOUT_SECONDS = 60

# =========================================================
# ANTI RAID
# =========================================================

RAID_JOIN_LIMIT = 6
RAID_TIME_WINDOW = 10

# =========================================================
# STAFF
# =========================================================

STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "KING FOX",
}

# =========================================================
# XP SHOP
# =========================================================

XP_ROLES = {
    2500: "Active Member",
    5000: "Elite Member",
    10000: "Premium",
    20000: "Legend",
    35000: "OG Fox",
    50000: "Royal Fox",
}

# =========================================================
# TICKET TYPES
# =========================================================

TICKET_TYPES = {
    "support": {
        "label": "תמיכה",
        "emoji": "🛠️",
        "description": "עזרה או בעיה בשרת",
        "color": discord.Color.blurple(),
    },
    "report": {
        "label": "דיווח על משתמש",
        "emoji": "🚨",
        "description": "דיווח על משתמש או התנהגות",
        "color": discord.Color.red(),
    },
    "bug": {
        "label": "דיווח על באג",
        "emoji": "🐛",
        "description": "דיווח על באג או תקלה",
        "color": discord.Color.orange(),
    },
    "staff": {
        "label": "פנייה לצוות",
        "emoji": "👮",
        "description": "פנייה ישירה לצוות",
        "color": discord.Color.green(),
    },
    "purchase": {
        "label": "רכישה / מכירה",
        "emoji": "💰",
        "description": "שאלות בנושא רכישות או מכירות",
        "color": discord.Color.gold(),
    },
    "question": {
        "label": "שאלה כללית",
        "emoji": "❓",
        "description": "שאלה שלא מתאימה לאפשרויות האחרות",
        "color": discord.Color.purple(),
    },
}


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
)

GUILD = discord.Object(id=GUILD_ID)


# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect(
    "bot_data.db",
    check_same_thread=False
)

conn.row_factory = sqlite3.Row

cursor = conn.cursor()

cursor.execute("PRAGMA journal_mode=WAL")


cursor.execute("""
CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER NOT NULL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    user_id INTEGER PRIMARY KEY,
    warnings INTEGER NOT NULL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    message_id INTEGER,
    channel_id INTEGER,
    created_at INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS suggestion_votes (
    suggestion_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    vote INTEGER NOT NULL,
    PRIMARY KEY (suggestion_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ticket_claims (
    channel_id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    staff_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily (
    user_id INTEGER PRIMARY KEY,
    streak INTEGER NOT NULL DEFAULT 0,
    last_claim INTEGER NOT NULL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS giveaways (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    prize TEXT NOT NULL,
    winners INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    ended INTEGER NOT NULL DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS giveaway_entries (
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (message_id, user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS drops (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    reward TEXT NOT NULL,
    xp_reward INTEGER NOT NULL DEFAULT 0,
    ended INTEGER NOT NULL DEFAULT 0
)
""")

conn.commit()


# =========================================================
# HELPERS
# =========================================================

def get_channel(guild: discord.Guild, name: str):
    return discord.utils.get(
        guild.text_channels,
        name=name
    )


def get_role(guild: discord.Guild, name: str):
    return discord.utils.get(
        guild.roles,
        name=name
    )


def is_staff(member: discord.Member) -> bool:

    if member.guild_permissions.administrator:
        return True

    return any(
        role.name.upper() in STAFF_ROLES
        for role in member.roles
    )


async def send_mod_log(
    guild: discord.Guild,
    title: str,
    description: str,
    color: discord.Color = discord.Color.blurple()
):

    channel = get_channel(
        guild,
        MOD_LOG_CHANNEL_NAME
    )

    if channel is None:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )

    embed.set_footer(
        text="Foxes • Mod Logs"
    )

    try:
        await channel.send(
            embed=embed
        )
    except Exception as e:
        print(f"Mod log error: {e}")


async def send_message_log(
    guild: discord.Guild,
    title: str,
    description: str,
    color: discord.Color = discord.Color.orange()
):

    channel = get_channel(
        guild,
        MESSAGE_LOG_CHANNEL_NAME
    )

    if channel is None:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )

    embed.set_footer(
        text="Foxes • Message Logs"
    )

    try:
        await channel.send(
            embed=embed
        )
    except Exception as e:
        print(f"Message log error: {e}")


# =========================================================
# XP
# =========================================================

def get_xp(user_id: int) -> int:

    row = cursor.execute(
        "SELECT xp FROM xp WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    return int(row["xp"]) if row else 0


def set_xp(
    user_id: int,
    amount: int
):

    cursor.execute("""
        INSERT INTO xp (user_id, xp)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET xp = excluded.xp
    """, (
        user_id,
        max(0, amount)
    ))

    conn.commit()


def add_xp(
    user_id: int,
    amount: int
) -> int:

    new_xp = get_xp(user_id) + amount

    set_xp(
        user_id,
        new_xp
    )

    return new_xp


def remove_xp(
    user_id: int,
    amount: int
) -> int:

    new_xp = max(
        0,
        get_xp(user_id) - amount
    )

    set_xp(
        user_id,
        new_xp
    )

    return new_xp


# =========================================================
# WARNINGS
# =========================================================

def get_warnings(user_id: int) -> int:

    row = cursor.execute(
        "SELECT warnings FROM warnings WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    return int(row["warnings"]) if row else 0


def add_warning(user_id: int) -> int:

    amount = get_warnings(user_id) + 1

    cursor.execute("""
        INSERT INTO warnings (user_id, warnings)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET warnings = excluded.warnings
    """, (
        user_id,
        amount
    ))

    conn.commit()

    return amount


# =========================================================
# XP COOLDOWN
# =========================================================

xp_cooldowns = {}


# =========================================================
# ANTI SPAM
# =========================================================

spam_tracker = defaultdict(deque)


# =========================================================
# ANTI RAID
# =========================================================

raid_joins = defaultdict(deque)


# =========================================================
# MESSAGE EVENT
# =========================================================

@bot.event
async def on_message(
    message: discord.Message
):

    if message.author.bot:
        return

    if message.guild is None:
        await bot.process_commands(message)
        return

    member = message.author

    if isinstance(member, discord.Member):

        # -------------------------------------------------
        # ANTI SPAM
        # -------------------------------------------------

        if not is_staff(member):

            now = time.time()

            history = spam_tracker[member.id]

            history.append(now)

            while history and now - history[0] > SPAM_TIME_WINDOW:
                history.popleft()

            if len(history) >= SPAM_MESSAGE_LIMIT:

                try:

                    await member.timeout(
                        discord.utils.utcnow()
                        + timedelta(
                            seconds=SPAM_TIMEOUT_SECONDS
                        ),
                        reason="Anti-Spam"
                    )

                    history.clear()

                    await send_mod_log(
                        message.guild,
                        "🛡️ Anti-Spam",
                        (
                            f"👤 משתמש: {member.mention}\n"
                            f"⏱️ Timeout: {SPAM_TIMEOUT_SECONDS} שניות\n"
                            f"📍 ערוץ: {message.channel.mention}"
                        ),
                        discord.Color.red()
                    )

                except Exception as e:

                    print(
                        f"Anti-spam error: {e}"
                    )

        # -------------------------------------------------
        # XP
        # -------------------------------------------------

        now = time.time()

        last = xp_cooldowns.get(
            member.id,
            0
        )

        if now - last >= XP_COOLDOWN:

            multiplier = (
                BOOSTER_XP_MULTIPLIER
                if member.premium_since is not None
                else 1
            )

            amount = XP_PER_MESSAGE * multiplier

            add_xp(
                member.id,
                amount
            )

            xp_cooldowns[
                member.id
            ] = now

    await bot.process_commands(message)


# =========================================================
# MESSAGE DELETE LOG
# =========================================================

@bot.event
async def on_message_delete(
    message: discord.Message
):

    if message.guild is None:
        return

    if message.author.bot:
        return

    content = message.content or "(אין תוכן טקסטואלי)"

    if len(content) > 1000:
        content = content[:1000] + "..."

    await send_message_log(
        message.guild,
        "🗑️ הודעה נמחקה",
        (
            f"👤 **משתמש:** {message.author.mention}\n"
            f"📍 **ערוץ:** {message.channel.mention}\n\n"
            f"💬 **תוכן:**\n```{content}```"
        )
    )


# =========================================================
# MEMBER JOIN
# =========================================================

@bot.event
async def on_member_join(
    member: discord.Member
):

    now = time.time()

    history = raid_joins[
        member.guild.id
    ]

    history.append(now)

    while history and now - history[0] > RAID_TIME_WINDOW:
        history.popleft()

    if len(history) >= RAID_JOIN_LIMIT:

        await send_mod_log(
            member.guild,
            "🚨 Anti-Raid Alert",
            (
                f"נכנסו **{len(history)} משתמשים** "
                f"ב־{RAID_TIME_WINDOW} שניות.\n\n"
                "⚠️ מומלץ לבדוק את השרת."
            ),
            discord.Color.red()
        )

    welcome_channel = get_channel(
        member.guild,
        WELCOME_CHANNEL_NAME
    )

    if welcome_channel:

        embed = discord.Embed(
            title="🦊 ברוכים הבאים ל-Foxes!",
            description=(
                f"שלום {member.mention}!\n\n"
                f"אתה החבר ה־**{member.guild.member_count:,}** בשרת.\n\n"
                "🔐 לחצו על **אימות** כדי לקבל גישה לשרת.\n"
                "🔔 אפשר לקבל גם את רול העדכונים וההגרלות."
            ),
            color=discord.Color.blurple()
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.set_footer(
            text="Foxes • Welcome"
        )

        try:
            await welcome_channel.send(
                embed=embed
            )
        except Exception as e:
            print(f"Welcome error: {e}")


# =========================================================
# WELCOME VIEW
# =========================================================

class WelcomeView(discord.ui.View):

    def __init__(self):
        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="אימות",
        emoji="🔐",
        style=discord.ButtonStyle.success,
        custom_id="welcome_verify"
    )
    async def verify(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.guild is None:
            return

        role = get_role(
            interaction.guild,
            VERIFIED_ROLE_NAME
        )

        if role is None:

            await interaction.response.send_message(
                f"❌ לא נמצא הרול `{VERIFIED_ROLE_NAME}`.",
                ephemeral=True
            )

            return

        member = interaction.user

        if role in member.roles:

            await interaction.response.send_message(
                "✅ אתה כבר מאומת.",
                ephemeral=True
            )

            return

        try:

            await member.add_roles(
                role,
                reason="Verification"
            )

            await interaction.response.send_message(
                f"✅ אומת בהצלחה וקיבלת את {role.mention}.",
                ephemeral=True
            )

        except Exception as e:

            print(
                f"Verification error: {e}"
            )

            await interaction.response.send_message(
                "❌ לא הצלחתי לתת לך את הרול. בדוק שהרול של הבוט מעל הרול Member.",
                ephemeral=True
            )


    @discord.ui.button(
        label="עדכונים והגרלות",
        emoji="🔔",
        style=discord.ButtonStyle.primary,
        custom_id="welcome_updates"
    )
    async def updates(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.guild is None:
            return

        role = get_role(
            interaction.guild,
            UPDATES_ROLE_NAME
        )

        if role is None:

            await interaction.response.send_message(
                f"❌ לא נמצא הרול `{UPDATES_ROLE_NAME}`.",
                ephemeral=True
            )

            return

        member = interaction.user

        try:

            if role in member.roles:

                await member.remove_roles(
                    role,
                    reason="Updates role removed"
                )

                await interaction.response.send_message(
                    "🔕 הרול של העדכונים וההגרלות הוסר.",
                    ephemeral=True
                )

            else:

                await member.add_roles(
                    role,
                    reason="Updates role added"
                )

                await interaction.response.send_message(
                    "🔔 קיבלת את רול העדכונים וההגרלות!",
                    ephemeral=True
                )

        except Exception as e:

            print(
                f"Updates role error: {e}"
            )

            await interaction.response.send_message(
                "❌ לא הצלחתי לשנות את הרול.",
                ephemeral=True
            )


# =========================================================
# /WELCOME
# =========================================================

@bot.tree.command(
    name="welcome",
    description="שלח את פאנל ה-Welcome",
    guild=GUILD
)
async def welcome_command(
    interaction: discord.Interaction
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את פאנל ה-Welcome.",
            ephemeral=True
        )

        return

    channel = get_channel(
        interaction.guild,
        WELCOME_CHANNEL_NAME
    )

    if channel is None:

        await interaction.response.send_message(
            f"❌ לא נמצא הערוץ `{WELCOME_CHANNEL_NAME}`.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="👋 ברוכים הבאים ל-Foxes!",
        description=(
            "ברוכים הבאים לשרת!\n\n"
            "🔐 **אימות**\n"
            "קבלו גישה לשרת באמצעות כפתור האימות.\n\n"
            "🔔 **עדכונים והגרלות**\n"
            "קבלו התראות על עדכונים והגרלות.\n\n"
            "🦊 תהנו ב-Foxes!"
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="Foxes • Welcome"
    )

    await channel.send(
        embed=embed,
        view=WelcomeView()
    )

    await interaction.response.send_message(
        f"✅ פאנל ה-Welcome נשלח ל-{channel.mention}.",
        ephemeral=True
    )


# =========================================================
# /XP
# =========================================================

@bot.tree.command(
    name="xp",
    description="בדוק XP",
    guild=GUILD
)
@app_commands.describe(
    user="המשתמש"
)
async def xp_command(
    interaction: discord.Interaction,
    user: Optional[discord.Member] = None
):

    target = user or interaction.user

    amount = get_xp(
        target.id
    )

    await interaction.response.send_message(
        f"⭐ ל-{target.mention} יש **{amount:,} XP**."
    )


# =========================================================
# LEADERBOARD
# =========================================================

@bot.tree.command(
    name="leaderboard",
    description="טבלת ה-XP",
    guild=GUILD
)
async def leaderboard_command(
    interaction: discord.Interaction
):

    rows = cursor.execute("""
        SELECT user_id, xp
        FROM xp
        ORDER BY xp DESC
        LIMIT 10
    """).fetchall()

    if not rows:

        await interaction.response.send_message(
            "❌ עדיין אין נתוני XP."
        )

        return

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    lines = []

    for index, row in enumerate(rows, start=1):

        member = interaction.guild.get_member(
            row["user_id"]
        )

        name = (
            member.display_name
            if member
            else f"משתמש {row['user_id']}"
        )

        prefix = (
            medals[index - 1]
            if index <= 3
            else f"**{index}.**"
        )

        lines.append(
            f"{prefix} {name} — **{row['xp']:,} XP**"
        )

    embed = discord.Embed(
        title="🏆 Foxes XP Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold()
    )

    embed.set_footer(
        text="Foxes • XP System"
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# ADD XP
# =========================================================

@bot.tree.command(
    name="addxp",
    description="הוסף XP",
    guild=GUILD
)
@app_commands.describe(
    user="המשתמש",
    amount="כמות XP"
)
async def addxp_command(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה.",
            ephemeral=True
        )

        return

    if amount <= 0:

        await interaction.response.send_message(
            "❌ הכמות חייבת להיות גדולה מ־0.",
            ephemeral=True
        )

        return

    new_xp = add_xp(
        user.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ נוסף ל-{user.mention} **{amount:,} XP**.\n"
        f"⭐ XP נוכחי: **{new_xp:,}**"
    )

    await send_mod_log(
        interaction.guild,
        "⭐ XP נוסף",
        (
            f"👤 משתמש: {user.mention}\n"
            f"👮 צוות: {interaction.user.mention}\n"
            f"➕ כמות: **{amount:,} XP**"
        ),
        discord.Color.green()
    )


# =========================================================
# REMOVE XP
# =========================================================

@bot.tree.command(
    name="removexp",
    description="הסר XP",
    guild=GUILD
)
@app_commands.describe(
    user="המשתמש",
    amount="כמות XP"
)
async def removexp_command(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה.",
            ephemeral=True
        )

        return

    if amount <= 0:

        await interaction.response.send_message(
            "❌ הכמות חייבת להיות גדולה מ־0.",
            ephemeral=True
        )

        return

    new_xp = remove_xp(
        user.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ הוסרו מ-{user.mention} **{amount:,} XP**.\n"
        f"⭐ XP נוכחי: **{new_xp:,}**"
    )

    await send_mod_log(
        interaction.guild,
        "⭐ XP הוסר",
        (
            f"👤 משתמש: {user.mention}\n"
            f"👮 צוות: {interaction.user.mention}\n"
            f"➖ כמות: **{amount:,} XP**"
        ),
        discord.Color.orange()
    )


# =========================================================
# SET XP
# =========================================================

@bot.tree.command(
    name="setxp",
    description="קבע XP",
    guild=GUILD
)
@app_commands.describe(
    user="המשתמש",
    amount="XP חדש"
)
async def setxp_command(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה.",
            ephemeral=True
        )

        return

    if amount < 0:

        await interaction.response.send_message(
            "❌ XP לא יכול להיות שלילי.",
            ephemeral=True
        )

        return

    set_xp(
        user.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ ה-XP של {user.mention} נקבע ל־**{amount:,} XP**."
    )

    await send_mod_log(
        interaction.guild,
        "⭐ XP נקבע",
        (
            f"👤 משתמש: {user.mention}\n"
            f"👮 צוות: {interaction.user.mention}\n"
            f"⭐ XP חדש: **{amount:,}**"
        )
    )


# =========================================================
# XP SHOP
# =========================================================

class XPShopView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="בדוק חנות XP",
        emoji="🛒",
        style=discord.ButtonStyle.primary,
        custom_id="xp_shop"
    )
    async def xp_shop(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        embed = discord.Embed(
            title="🛒 חנות XP",
            description="הדרגות הזמינות:",
            color=discord.Color.blurple()
        )

        for xp, role in XP_ROLES.items():

            embed.add_field(
                name=f"⭐ {xp:,} XP",
                value=f"🏷️ {role}",
                inline=False
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


@bot.tree.command(
    name="xpshop",
    description="פתח את חנות ה-XP",
    guild=GUILD
)
async def xpshop_command(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🛒 Foxes XP Shop",
        description=(
            "צברו XP וקבלו דרגות מיוחדות!\n\n"
            "לחצו על הכפתור כדי לראות את החנות."
        ),
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        view=XPShopView()
    )


# =========================================================
# WARN
# =========================================================

@bot.tree.command(
    name="warn",
    description="תן אזהרה",
    guild=GUILD
)
@app_commands.describe(
    user="המשתמש",
    reason="סיבה"
)
async def warn_command(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה.",
            ephemeral=True
        )

        return

    if user.bot:

        await interaction.response.send_message(
            "❌ אי אפשר לתת אזהרה לבוט.",
            ephemeral=True
        )

        return

    amount = add_warning(
        user.id
    )

    # -----------------------------------------------------
    # WARNING 1
    # -----------------------------------------------------

    if amount == 1:

        action = "⚠️ אזהרה בלבד"

    # -----------------------------------------------------
    # WARNING 2
    # -----------------------------------------------------

    elif amount == 2:

        action = "🔇 Timeout ל־3 שעות"

        try:

            await user.timeout(
                discord.utils.utcnow()
                + timedelta(hours=3),
                reason=f"Warning 2: {reason}"
            )

        except Exception as e:
            print(f"Warning 2 timeout error: {e}")

    # -----------------------------------------------------
    # WARNING 3
    # -----------------------------------------------------

    elif amount == 3:

        action = "🔇 Timeout ל־10 שעות"

        try:

            await user.timeout(
                discord.utils.utcnow()
                + timedelta(hours=10),
                reason=f"Warning 3: {reason}"
            )

        except Exception as e:
            print(f"Warning 3 timeout error: {e}")

    # -----------------------------------------------------
    # WARNING 4
    # -----------------------------------------------------

    elif amount == 4:

        action = "🔨 Timeout ל־3 ימים"

        try:

            await user.timeout(
                discord.utils.utcnow()
                + timedelta(days=3),
                reason=f"Warning 4: {reason}"
            )

        except Exception as e:
            print(f"Warning 4 timeout error: {e}")

    # -----------------------------------------------------
    # WARNING 5+
    # -----------------------------------------------------

    else:

        action = "🔨 Ban"

        try:

            await user.ban(
                reason=f"Warning {amount}: {reason}"
            )

        except Exception as e:
            print(f"Ban error: {e}")

    embed = discord.Embed(
        title="⚠️ מערכת אזהרות",
        description=(
            f"👤 **משתמש:** {user.mention}\n"
            f"👮 **צוות:** {interaction.user.mention}\n"
            f"📝 **סיבה:** {reason}\n"
            f"⚠️ **מספר אזהרות:** `{amount}`\n\n"
            f"🎯 **פעולה:** {action}"
        ),
        color=discord.Color.red()
    )

    await interaction.response.send_message(
        embed=embed
    )

    await send_mod_log(
        interaction.guild,
        "⚠️ אזהרה חדשה",
        (
            f"👤 משתמש: {user.mention}\n"
            f"👮 צוות: {interaction.user.mention}\n"
            f"⚠️ אזהרות: **{amount}**\n"
            f"📝 סיבה: {reason}\n"
            f"🎯 פעולה: {action}"
        ),
        discord.Color.red()
    )


# =========================================================
# WARNINGS
# =========================================================

@bot.tree.command(
    name="warnings",
    description="בדוק אזהרות",
    guild=GUILD
)
@app_commands.describe(
    user="המשתמש"
)
async def warnings_command(
    interaction: discord.Interaction,
    user: Optional[discord.Member] = None
):

    target = user or interaction.user

    amount = get_warnings(
        target.id
    )

    await interaction.response.send_message(
        f"⚠️ ל-{target.mention} יש **{amount} אזהרות**."
    )


# =========================================================
# DAILY
# =========================================================

def get_daily_data(user_id: int):

    row = cursor.execute("""
        SELECT streak, last_claim
        FROM daily
        WHERE user_id = ?
    """, (
        user_id,
    )).fetchone()

    if row is None:
        return 0, 0

    return row["streak"], row["last_claim"]


def set_daily_data(
    user_id: int,
    streak: int,
    last_claim: int
):

    cursor.execute("""
        INSERT INTO daily
        (user_id, streak, last_claim)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            streak = excluded.streak,
            last_claim = excluded.last_claim
    """, (
        user_id,
        streak,
        last_claim
    ))

    conn.commit()


class DailyView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="קבל Daily XP",
        emoji="🎁",
        style=discord.ButtonStyle.success,
        custom_id="daily_claim"
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        user_id = interaction.user.id

        streak, last_claim = get_daily_data(
            user_id
        )

        now = int(time.time())

        if last_claim and now - last_claim < 86400:

            remaining = 86400 - (
                now - last_claim
            )

            hours = remaining // 3600
            minutes = (
                remaining % 3600
            ) // 60

            await interaction.response.send_message(
                f"⏳ כבר לקחת את ה-Daily היום.\n"
                f"נסה שוב בעוד **{hours} שעות ו-{minutes} דקות**.",
                ephemeral=True
            )

            return

        if last_claim and now - last_claim > 172800:
            streak = 0

        streak += 1

        if streak > 7:
            streak = 1

        set_daily_data(
            user_id,
            streak,
            now
        )

        if streak == 7:

            role = get_role(
                interaction.guild,
                DAILY_SPECIAL_ROLE_NAME
            )

            if role:

                try:

                    await interaction.user.add_roles(
                        role,
                        reason="7 Day Daily Reward"
                    )

                except Exception as e:
                    print(f"Daily role error: {e}")

            await interaction.response.send_message(
                "🔥 **יום 7!**\n\n"
                f"🏆 קיבלת את הרול **{DAILY_SPECIAL_ROLE_NAME}**!",
                ephemeral=True
            )

            return

        reward = DAILY_REWARDS[streak]

        new_xp = add_xp(
            user_id,
            reward
        )

        await interaction.response.send_message(
            f"🎁 **Daily יום {streak}**\n\n"
            f"⭐ קיבלת **{reward} XP**!\n"
            f"📊 XP נוכחי: **{new_xp:,}**\n\n"
            f"🔥 רצף: **{streak}/7**",
            ephemeral=True
        )


@bot.tree.command(
    name="daily",
    description="שלח את פאנל ה-Daily",
    guild=GUILD
)
async def daily_command(
    interaction: discord.Interaction
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את פאנל ה-Daily.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎁 Foxes Daily",
        description=(
            "קחו את ה-Daily שלכם כל יום ושמרו על רצף!\n\n"
            "🟢 יום 1 — **10 XP**\n"
            "🟢 יום 2 — **20 XP**\n"
            "🟢 יום 3 — **50 XP**\n"
            "🟢 יום 4 — **100 XP**\n"
            "🟢 יום 5 — **150 XP**\n"
            "🟢 יום 6 — **200 XP**\n"
            "🏆 יום 7 — **רול מיוחד**"
        ),
        color=discord.Color.gold()
    )

    embed.set_footer(
        text="Foxes • Daily Rewards"
    )

    await interaction.response.send_message(
        embed=embed,
        view=DailyView()
    )


# =========================================================
# BOOST
# =========================================================

@bot.event
async def on_member_update(
    before: discord.Member,
    after: discord.Member
):

    if (
        before.premium_since is None
        and after.premium_since is not None
    ):

        new_xp = add_xp(
            after.id,
            BOOST_REWARD_XP
        )

        channel = get_channel(
            after.guild,
            BOOST_CHANNEL_NAME
        )

        if channel:

            embed = discord.Embed(
                title="🚀 BOOST חדש לשרת!",
                description=(
                    f"🎉 {after.mention} עשה Server Boost ל-Foxes!\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💎 **+{BOOST_REWARD_XP:,} XP**\n"
                    "🚀 **מעכשיו אתה מקבל X2 XP!**\n\n"
                    f"📊 XP נוכחי: **{new_xp:,} XP**\n\n"
                    "❤️ תודה ענקית על התמיכה!"
                ),
                color=discord.Color.fuchsia()
            )

            embed.set_thumbnail(
                url=after.display_avatar.url
            )

            await channel.send(
                content=after.mention,
                embed=embed
            )


# =========================================================
# SUGGESTIONS
# =========================================================

class SuggestionPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="הצע רעיון",
        emoji="💡",
        style=discord.ButtonStyle.primary,
        custom_id="open_suggestion"
    )
    async def suggestion(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            SuggestionModal()
        )


class SuggestionModal(
    discord.ui.Modal,
    title="💡 הצעת רעיון"
):

    content = discord.ui.TextInput(
        label="מה ההצעה שלך?",
        placeholder="כתוב כאן את הרעיון שלך...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True
    )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        suggestions_channel = get_channel(
            interaction.guild,
            SUGGESTIONS_CHANNEL_NAME
        )

        if suggestions_channel is None:

            await interaction.response.send_message(
                f"❌ לא נמצא הערוץ `{SUGGESTIONS_CHANNEL_NAME}`.",
                ephemeral=True
            )

            return

        cursor.execute("""
            INSERT INTO suggestions
            (user_id, content, created_at)
            VALUES (?, ?, ?)
        """, (
            interaction.user.id,
            str(self.content),
            int(time.time())
        ))

        suggestion_id = cursor.lastrowid

        conn.commit()

        embed = discord.Embed(
            title=f"💡 הצעה #{suggestion_id}",
            description=str(self.content),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="👤 הוצע על ידי",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="👍 בעד",
            value="0",
            inline=True
        )

        embed.add_field(
            name="👎 נגד",
            value="0",
            inline=True
        )

        message = await suggestions_channel.send(
            embed=embed,
            view=SuggestionVoteView(suggestion_id)
        )

        cursor.execute("""
            UPDATE suggestions
            SET message_id = ?, channel_id = ?
            WHERE id = ?
        """, (
            message.id,
            suggestions_channel.id,
            suggestion_id
        ))

        conn.commit()

        await interaction.response.send_message(
            f"✅ ההצעה נשלחה ל-{suggestions_channel.mention}!",
            ephemeral=True
        )


class SuggestionVoteView(discord.ui.View):

    def __init__(
        self,
        suggestion_id: int
    ):

        super().__init__(
            timeout=None
        )

        self.suggestion_id = suggestion_id

        yes_button = discord.ui.Button(
            label="בעד 0",
            emoji="👍",
            style=discord.ButtonStyle.success,
            custom_id=f"suggestion_yes_{suggestion_id}"
        )

        no_button = discord.ui.Button(
            label="נגד 0",
            emoji="👎",
            style=discord.ButtonStyle.danger,
            custom_id=f"suggestion_no_{suggestion_id}"
        )

        yes_button.callback = self.yes
        no_button.callback = self.no

        self.add_item(yes_button)
        self.add_item(no_button)

    async def yes(
        self,
        interaction: discord.Interaction
    ):

        await self.vote(
            interaction,
            1
        )

    async def no(
        self,
        interaction: discord.Interaction
    ):

        await self.vote(
            interaction,
            -1
        )

    async def vote(
        self,
        interaction: discord.Interaction,
        vote: int
    ):

        existing = cursor.execute("""
            SELECT vote
            FROM suggestion_votes
            WHERE suggestion_id = ?
            AND user_id = ?
        """, (
            self.suggestion_id,
            interaction.user.id
        )).fetchone()

        if existing:

            await interaction.response.send_message(
                "❌ כבר הצבעת להצעה הזאת.",
                ephemeral=True
            )

            return

        cursor.execute("""
            INSERT INTO suggestion_votes
            (suggestion_id, user_id, vote)
            VALUES (?, ?, ?)
        """, (
            self.suggestion_id,
            interaction.user.id,
            vote
        ))

        conn.commit()

        yes_count = cursor.execute("""
            SELECT COUNT(*)
            FROM suggestion_votes
            WHERE suggestion_id = ?
            AND vote = 1
        """, (
            self.suggestion_id,
        )).fetchone()[0]

        no_count = cursor.execute("""
            SELECT COUNT(*)
            FROM suggestion_votes
            WHERE suggestion_id = ?
            AND vote = -1
        """, (
            self.suggestion_id,
        )).fetchone()[0]

        for item in self.children:

            if isinstance(item, discord.ui.Button):

                if item.custom_id == f"suggestion_yes_{self.suggestion_id}":
                    item.label = f"בעד {yes_count}"

                if item.custom_id == f"suggestion_no_{self.suggestion_id}":
                    item.label = f"נגד {no_count}"

        await interaction.response.edit_message(
            view=self
        )


@bot.tree.command(
    name="suggestions",
    description="שלח פאנל הצעות",
    guild=GUILD
)
async def suggestions_command(
    interaction: discord.Interaction
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לפתוח את פאנל ההצעות.",
            ephemeral=True
        )

        return

    panel_channel = get_channel(
        interaction.guild,
        SUGGESTION_PANEL_CHANNEL_NAME
    )

    if panel_channel is None:

        await interaction.response.send_message(
            f"❌ לא נמצא הערוץ `{SUGGESTION_PANEL_CHANNEL_NAME}`.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="💡 הצעות ל-Foxes",
        description=(
            "יש לכם רעיון לשיפור השרת?\n\n"
            "לחצו על **הצע רעיון** ושלחו אותו!\n\n"
            "📌 ההצעות יישלחו לערוץ נפרד."
        ),
        color=discord.Color.blurple()
    )

    await panel_channel.send(
        embed=embed,
        view=SuggestionPanelView()
    )

    await interaction.response.send_message(
        f"✅ פאנל ההצעות נשלח ל-{panel_channel.mention}.",
        ephemeral=True
    )


# =========================================================
# TICKETS
# =========================================================

def create_ticket_record(
    channel_id: int,
    message_id: int
):

    cursor.execute("""
        INSERT OR REPLACE INTO ticket_claims
        (channel_id, message_id, staff_id)
        VALUES (?, ?, NULL)
    """, (
        channel_id,
        message_id
    ))

    conn.commit()


def get_ticket_claim(
    channel_id: int
):

    row = cursor.execute("""
        SELECT staff_id
        FROM ticket_claims
        WHERE channel_id = ?
    """, (
        channel_id,
    )).fetchone()

    if row is None:
        return None

    return row["staff_id"]


def claim_ticket(
    channel_id: int,
    staff_id: int
) -> bool:

    cursor.execute("""
        UPDATE ticket_claims
        SET staff_id = ?
        WHERE channel_id = ?
        AND staff_id IS NULL
    """, (
        staff_id,
        channel_id
    ))

    conn.commit()

    return cursor.rowcount > 0


def delete_ticket_record(
    channel_id: int
):

    cursor.execute(
        "DELETE FROM ticket_claims WHERE channel_id = ?",
        (channel_id,)
    )

    conn.commit()


class TicketControlView(discord.ui.View):

    def __init__(
        self,
        channel_id: int,
        claimed_by: Optional[int] = None
    ):

        super().__init__(
            timeout=None
        )

        self.channel_id = channel_id

        take_button = discord.ui.Button(
            label=(
                "קח טיפול"
                if claimed_by is None
                else "בטיפול"
            ),
            emoji=(
                "🟢"
                if claimed_by is None
                else "⚪"
            ),
            style=(
                discord.ButtonStyle.success
                if claimed_by is None
                else discord.ButtonStyle.secondary
            ),
            custom_id=f"ticket_take_{channel_id}",
            disabled=claimed_by is not None
        )

        take_button.callback = self.take_ticket

        self.add_item(
            take_button
        )

        close_button = discord.ui.Button(
            label="סגור טיקט",
            emoji="🔒",
            style=discord.ButtonStyle.danger,
            custom_id=f"ticket_close_{channel_id}"
        )

        close_button.callback = self.close_ticket

        self.add_item(
            close_button
        )

    async def take_ticket(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ רק הצוות יכול לקחת טיפול.",
                ephemeral=True
            )

            return

        existing = get_ticket_claim(
            self.channel_id
        )

        if existing is not None:

            await interaction.response.send_message(
                f"❌ הטיקט כבר בטיפול של <@{existing}>.",
                ephemeral=True
            )

            return

        success = claim_ticket(
            self.channel_id,
            interaction.user.id
        )

        if not success:

            await interaction.response.send_message(
                "❌ מישהו אחר לקח את הטיקט.",
                ephemeral=True
            )

            return

        embed = interaction.message.embeds[0].copy()

        for i, field in enumerate(embed.fields):

            if field.name == "👨‍💻 בטיפול":

                embed.remove_field(i)
                break

        embed.add_field(
            name="👨‍💻 בטיפול",
            value=interaction.user.mention,
            inline=False
        )

        await interaction.response.edit_message(
            embed=embed,
            view=TicketControlView(
                self.channel_id,
                interaction.user.id
            )
        )

        await interaction.channel.send(
            f"👨‍💻 {interaction.user.mention} לקח את הטיקט."
        )

        await send_mod_log(
            interaction.guild,
            "🎫 טיקט נלקח",
            (
                f"🎫 ערוץ: {interaction.channel.mention}\n"
                f"👮 צוות: {interaction.user.mention}"
            ),
            discord.Color.green()
        )

    async def close_ticket(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ רק הצוות יכול לסגור טיקט.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 הטיקט ייסגר בעוד 5 שניות."
        )

        await send_mod_log(
            interaction.guild,
            "🔒 טיקט נסגר",
            (
                f"🎫 ערוץ: {interaction.channel.mention}\n"
                f"👮 נסגר על ידי: {interaction.user.mention}"
            ),
            discord.Color.red()
        )

        await asyncio.sleep(5)

        delete_ticket_record(
            self.channel_id
        )

        try:

            await interaction.channel.delete(
                reason="Ticket closed"
            )

        except Exception as e:

            print(
                f"Ticket delete error: {e}"
            )


class TicketTypeSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for key, data in TICKET_TYPES.items():

            options.append(
                discord.SelectOption(
                    label=data["label"],
                    description=data["description"],
                    emoji=data["emoji"],
                    value=key
                )
            )

        super().__init__(
            placeholder="🎫 בחר את סוג הטיקט...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        ticket_type = self.values[0]

        await create_ticket(
            interaction,
            ticket_type,
            TICKET_TYPES[ticket_type]
        )


class TicketView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            TicketTypeSelect()
        )


async def create_ticket(
    interaction: discord.Interaction,
    ticket_type: str,
    ticket_data: dict
):

    guild = interaction.guild

    if guild is None:
        return

    # חשוב: עונים מיד כדי למנוע "Foxy bot didn't respond in time"
    if not interaction.response.is_done():

        await interaction.response.defer(
            ephemeral=True
        )

    # -----------------------------------------------------
    # CHECK EXISTING
    # -----------------------------------------------------

    existing = None

    for channel in guild.text_channels:

        if (
            channel.topic
            and channel.topic.startswith(
                f"ticket_owner:{interaction.user.id};"
            )
        ):

            existing = channel
            break

    if existing:

        await interaction.followup.send(
            f"❌ כבר יש לך טיקט פתוח: {existing.mention}",
            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    category = discord.utils.get(
        guild.categories,
        name=TICKET_CATEGORY_NAME
    )

    if category is None:

        try:

            category = await guild.create_category(
                TICKET_CATEGORY_NAME,
                reason="Ticket System"
            )

        except Exception as e:

            print(f"Ticket category error: {e}")

            await interaction.followup.send(
                "❌ לא הצלחתי ליצור את קטגוריית הטיקטים.",
                ephemeral=True
            )

            return

    # -----------------------------------------------------
    # PERMISSIONS
    # -----------------------------------------------------

    overwrites = {

        guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

        interaction.user:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
    }

    for role in guild.roles:

        if role.name.upper() in STAFF_ROLES:

            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )

    # -----------------------------------------------------
    # CREATE CHANNEL
    # -----------------------------------------------------

    try:

        channel = await guild.create_text_channel(
            f"{ticket_type}-{interaction.user.id}",
            category=category,
            overwrites=overwrites,
            topic=(
                f"ticket_owner:{interaction.user.id};"
                f"type:{ticket_type}"
            ),
            reason=f"Ticket opened: {ticket_data['label']}"
        )

    except Exception as e:

        print(f"Ticket channel error: {e}")

        await interaction.followup.send(
            "❌ לא הצלחתי ליצור את הטיקט. בדוק שלבוט יש Manage Channels.",
            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # EMBED
    # -----------------------------------------------------

    embed = discord.Embed(
        title=(
            f"{ticket_data['emoji']} "
            f"{ticket_data['label']}"
        ),
        description=(
            f"שלום {interaction.user.mention}!\n\n"
            f"פתחת טיקט בנושא **{ticket_data['label']}**.\n\n"
            "📝 כתוב כאן את פרטי הפנייה.\n"
            "👨‍💻 איש צוות יטפל בטיקט.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🟢 **קח טיפול** — איש צוות יכול לקחת את הטיקט.\n"
            "🔒 **סגור טיקט** — סוגר את הטיקט."
        ),
        color=ticket_data["color"]
    )

    embed.add_field(
        name="📂 סוג",
        value=(
            f"{ticket_data['emoji']} "
            f"**{ticket_data['label']}**"
        ),
        inline=False
    )

    embed.add_field(
        name="👤 נפתח על ידי",
        value=interaction.user.mention,
        inline=False
    )

    embed.set_thumbnail(
        url=interaction.user.display_avatar.url
    )

    embed.set_footer(
        text="Foxes • מערכת טיקטים"
    )

    try:

        message = await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketControlView(
                channel.id
            )
        )

        create_ticket_record(
            channel.id,
            message.id
        )

    except Exception as e:

        print(f"Ticket message error: {e}")

        try:
            await channel.delete(
                reason="Ticket setup failed"
            )
        except Exception:
            pass

        await interaction.followup.send(
            "❌ הטיקט נוצר אבל לא הצלחתי לשלוח את ההודעה.",
            ephemeral=True
        )

        return

    await interaction.followup.send(
        f"✅ הטיקט נפתח!\n"
        f"📂 סוג: **{ticket_data['label']}**\n"
        f"🎫 {channel.mention}",
        ephemeral=True
    )

    await send_mod_log(
        guild,
        "🎫 טיקט חדש",
        (
            f"👤 נפתח על ידי: {interaction.user.mention}\n"
            f"📂 סוג: **{ticket_data['label']}**\n"
            f"🎫 ערוץ: {channel.mention}"
        ),
        discord.Color.blurple()
    )


@bot.tree.command(
    name="ticket",
    description="שלח פאנל טיקטים",
    guild=GUILD
)
async def ticket_command(
    interaction: discord.Interaction
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את פאנל הטיקטים.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎫 מערכת התמיכה של Foxes",
        description=(
            "יש לכם שאלה, בעיה או בקשה?\n\n"
            "בחרו את סוג הפנייה שלכם מהתפריט:\n\n"
            "🛠️ תמיכה\n"
            "🚨 דיווח על משתמש\n"
            "🐛 דיווח על באג\n"
            "👮 פנייה לצוות\n"
            "💰 רכישה / מכירה\n"
            "❓ שאלה כללית\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🦊 **Foxes Support**"
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="Foxes • Tickets"
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


# =========================================================
# SAY
# =========================================================

@bot.tree.command(
    name="say",
    description="שלח הודעה דרך הבוט",
    guild=GUILD
)
@app_commands.describe(
    message="מה הבוט יכתוב"
)
async def say_command(
    interaction: discord.Interaction,
    message: str
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        "✅ ההודעה נשלחה.",
        ephemeral=True
    )

    await interaction.channel.send(
        message
    )


# =========================================================
# POLL
# =========================================================

class PollView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="כן",
        emoji="👍",
        style=discord.ButtonStyle.success,
        custom_id="poll_yes"
    )
    async def yes(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "👍 הצבעת כן!",
            ephemeral=True
        )

    @discord.ui.button(
        label="לא",
        emoji="👎",
        style=discord.ButtonStyle.danger,
        custom_id="poll_no"
    )
    async def no(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "👎 הצבעת לא!",
            ephemeral=True
        )


@bot.tree.command(
    name="poll",
    description="צור סקר",
    guild=GUILD
)
@app_commands.describe(
    question="שאלת הסקר"
)
async def poll_command(
    interaction: discord.Interaction,
    question: str
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול ליצור סקרים.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="📊 סקר",
        description=question,
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="Foxes • Poll"
    )

    await interaction.response.send_message(
        embed=embed,
        view=PollView()
    )


# =========================================================
# GAMES
# =========================================================

class GamesView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="מספר אקראי",
        emoji="🎲",
        style=discord.ButtonStyle.primary,
        custom_id="game_random"
    )
    async def random_number(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        number = random.randint(
            1,
            100
        )

        await interaction.response.send_message(
            f"🎲 המספר שלך הוא **{number}**!",
            ephemeral=True
        )

    @discord.ui.button(
        label="מטבע",
        emoji="🪙",
        style=discord.ButtonStyle.secondary,
        custom_id="game_coin"
    )
    async def coin(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        result = random.choice([
            "עץ",
            "פלי"
        ])

        await interaction.response.send_message(
            f"🪙 יצא: **{result}**!",
            ephemeral=True
        )


@bot.tree.command(
    name="games",
    description="פתח פאנל משחקים",
    guild=GUILD
)
async def games_command(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🎮 Foxes Games",
        description=(
            "ברוכים הבאים לחדר המשחקים!\n\n"
            "בחרו משחק והתחילו."
        ),
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed,
        view=GamesView()
    )


# =========================================================
# GIVEAWAY
# =========================================================

def parse_duration(
    duration: str
) -> Optional[int]:

    match = re.fullmatch(
        r"(\d+)(s|m|h|d)",
        duration.lower().strip()
    )

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }[unit]

    return amount * multiplier


class GiveawayView(discord.ui.View):

    def __init__(
        self,
        message_id: int
    ):

        super().__init__(
            timeout=None
        )

        self.message_id = message_id

        button = discord.ui.Button(
            label="השתתף בהגרלה",
            emoji="🎉",
            style=discord.ButtonStyle.success,
            custom_id=f"giveaway_enter_{message_id}"
        )

        button.callback = self.enter

        self.add_item(
            button
        )

    async def enter(
        self,
        interaction: discord.Interaction
    ):

        row = cursor.execute("""
            SELECT ended
            FROM giveaways
            WHERE message_id = ?
        """, (
            self.message_id,
        )).fetchone()

        if row is None or row["ended"]:

            await interaction.response.send_message(
                "❌ ההגרלה כבר הסתיימה.",
                ephemeral=True
            )

            return

        existing = cursor.execute("""
            SELECT 1
            FROM giveaway_entries
            WHERE message_id = ?
            AND user_id = ?
        """, (
            self.message_id,
            interaction.user.id
        )).fetchone()

        if existing:

            await interaction.response.send_message(
                "❌ אתה כבר משתתף בהגרלה.",
                ephemeral=True
            )

            return

        cursor.execute("""
            INSERT INTO giveaway_entries
            (message_id, user_id)
            VALUES (?, ?)
        """, (
            self.message_id,
            interaction.user.id
        ))

        conn.commit()

        await interaction.response.send_message(
            "🎉 נכנסת להגרלה בהצלחה!",
            ephemeral=True
        )


@bot.tree.command(
    name="giveaway",
    description="צור הגרלה",
    guild=GUILD
)
@app_commands.describe(
    duration="לדוגמה: 10m / 1h / 1d",
    winners="מספר זוכים",
    prize="הפרס"
)
async def giveaway_command(
    interaction: discord.Interaction,
    duration: str,
    winners: int,
    prize: str
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול ליצור הגרלות.",
            ephemeral=True
        )

        return

    seconds = parse_duration(
        duration
    )

    if seconds is None:

        await interaction.response.send_message(
            "❌ פורמט זמן לא תקין. לדוגמה: `10m`, `2h`, `1d`.",
            ephemeral=True
        )

        return

    if seconds < 10:

        await interaction.response.send_message(
            "❌ הגרלה חייבת להיות לפחות 10 שניות.",
            ephemeral=True
        )

        return

    if winners <= 0 or winners > 50:

        await interaction.response.send_message(
            "❌ מספר הזוכים חייב להיות בין 1 ל־50.",
            ephemeral=True
        )

        return

    end_time = int(
        time.time() + seconds
    )

    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        description=(
            f"🎁 **פרס:** {prize}\n\n"
            f"🏆 **זוכים:** {winners}\n"
            f"⏰ **מסתיים:** <t:{end_time}:R>\n\n"
            "לחצו על הכפתור כדי להשתתף!"
        ),
        color=discord.Color.gold()
    )

    embed.set_footer(
        text="Foxes • Giveaway"
    )

    await interaction.response.send_message(
        embed=embed
    )

    message = await interaction.original_response()

    cursor.execute("""
        INSERT INTO giveaways
        (message_id, channel_id, guild_id, prize, winners, end_time)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        message.id,
        interaction.channel.id,
        interaction.guild.id,
        prize,
        winners,
        end_time
    ))

    conn.commit()

    await message.edit(
        view=GiveawayView(
            message.id
        )
    )


async def finish_giveaway(row):

    message_id = row["message_id"]

    entries = cursor.execute("""
        SELECT user_id
        FROM giveaway_entries
        WHERE message_id = ?
    """, (
        message_id,
    )).fetchall()

    channel = bot.get_channel(
        row["channel_id"]
    )

    if channel is None:
        return

    try:

        message = await channel.fetch_message(
            message_id
        )

    except Exception:

        message = None

    if not entries:

        if message:

            embed = discord.Embed(
                title="🎉 Giveaway הסתיימה",
                description=(
                    f"🎁 פרס: **{row['prize']}**\n\n"
                    "❌ לא היו משתתפים."
                ),
                color=discord.Color.red()
            )

            await message.edit(
                embed=embed,
                view=None
            )

        cursor.execute("""
            UPDATE giveaways
            SET ended = 1
            WHERE message_id = ?
        """, (
            message_id,
        ))

        conn.commit()

        return

    selected = random.sample(
        [entry["user_id"] for entry in entries],
        min(
            row["winners"],
            len(entries)
        )
    )

    mentions = [
        f"<@{user_id}>"
        for user_id in selected
    ]

    if message:

        embed = discord.Embed(
            title="🎉 Giveaway הסתיימה!",
            description=(
                f"🎁 **פרס:** {row['prize']}\n\n"
                f"🏆 **זוכים:**\n"
                + "\n".join(mentions)
            ),
            color=discord.Color.green()
        )

        await message.edit(
            embed=embed,
            view=None
        )

    await channel.send(
        "🎉 מזל טוב ל-" +
        ", ".join(mentions) +
        "!"
    )

    cursor.execute("""
        UPDATE giveaways
        SET ended = 1
        WHERE message_id = ?
    """, (
        message_id,
    ))

    conn.commit()


@tasks.loop(seconds=5)
async def giveaway_loop():

    now = int(time.time())

    rows = cursor.execute("""
        SELECT *
        FROM giveaways
        WHERE ended = 0
        AND end_time <= ?
    """, (
        now,
    )).fetchall()

    for row in rows:

        try:

            await finish_giveaway(
                row
            )

        except Exception as e:

            print(
                f"Giveaway error: {e}"
            )


# =========================================================
# DROP
# =========================================================

class DropView(discord.ui.View):

    def __init__(
        self,
        message_id: int
    ):

        super().__init__(
            timeout=None
        )

        self.message_id = message_id

        button = discord.ui.Button(
            label="תפוס את ה-Drop!",
            emoji="🎁",
            style=discord.ButtonStyle.success,
            custom_id=f"drop_claim_{message_id}"
        )

        button.callback = self.claim

        self.add_item(
            button
        )

    async def claim(
        self,
        interaction: discord.Interaction
    ):

        row = cursor.execute("""
            SELECT reward, xp_reward, ended
            FROM drops
            WHERE message_id = ?
        """, (
            self.message_id,
        )).fetchone()

        if row is None or row["ended"]:

            await interaction.response.send_message(
                "❌ ה-Drop כבר נתפס.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # FIXED: הערכים של ה-? נמצאים כאן
        # -------------------------------------------------

        cursor.execute("""
            UPDATE drops
            SET ended = 1
            WHERE message_id = ?
            AND ended = 0
        """, (
            self.message_id,
        ))

        conn.commit()

        if cursor.rowcount == 0:

            await interaction.response.send_message(
                "❌ מישהו כבר תפס את ה-Drop.",
                ephemeral=True
            )

            return

        xp_reward = row["xp_reward"]

        if xp_reward > 0:

            new_xp = add_xp(
                interaction.user.id,
                xp_reward
            )

            await interaction.response.send_message(
                f"🎉 {interaction.user.mention} תפס את ה-Drop!\n\n"
                f"⭐ קיבלת **{xp_reward:,} XP**!\n"
                f"📊 XP נוכחי: **{new_xp:,} XP**"
            )

        else:

            await interaction.response.send_message(
                f"🎉 {interaction.user.mention} תפס את ה-Drop!\n\n"
                f"🎁 פרס: **{row['reward']}**"
            )

        try:

            await interaction.message.edit(
                view=None
            )

        except Exception:
            pass

        await send_mod_log(
            interaction.guild,
            "🎁 Drop נתפס",
            (
                f"👤 זוכה: {interaction.user.mention}\n"
                f"⭐ XP: **{xp_reward:,}**\n"
                f"📍 ערוץ: {interaction.channel.mention}"
            ),
            discord.Color.green()
        )


@bot.tree.command(
    name="drop",
    description="צור Drop של XP",
    guild=GUILD
)
@app_commands.describe(
    xp_reward="כמה XP הזוכה יקבל"
)
async def drop_command(
    interaction: discord.Interaction,
    xp_reward: int
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול ליצור Drop.",
            ephemeral=True
        )

        return

    if xp_reward <= 0:

        await interaction.response.send_message(
            "❌ כמות ה-XP חייבת להיות גדולה מ־0.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎁 XP DROP!",
        description=(
            f"⭐ **{xp_reward:,} XP**\n\n"
            "מי יהיה הראשון שיתפוס?"
        ),
        color=discord.Color.green()
    )

    embed.set_footer(
        text="Foxes • XP Drop"
    )

    await interaction.response.send_message(
        embed=embed
    )

    message = await interaction.original_response()

    cursor.execute("""
        INSERT INTO drops
        (message_id, channel_id, guild_id, reward, xp_reward)
        VALUES (?, ?, ?, ?, ?)
    """, (
        message.id,
        interaction.channel.id,
        interaction.guild.id,
        f"{xp_reward:,} XP",
        xp_reward
    ))

    conn.commit()

    await message.edit(
        view=DropView(
            message.id
        )
    )


# =========================================================
# /LOGS
# =========================================================

@bot.tree.command(
    name="logs",
    description="בדוק את ערוצי הלוגים",
    guild=GUILD
)
async def logs_command(
    interaction: discord.Interaction
):

    if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לבדוק Logs.",
            ephemeral=True
        )

        return

    mod_logs = get_channel(
        interaction.guild,
        MOD_LOG_CHANNEL_NAME
    )

    message_logs = get_channel(
        interaction.guild,
        MESSAGE_LOG_CHANNEL_NAME
    )

    embed = discord.Embed(
        title="📋 Foxes Logs",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🛡️ Mod Logs",
        value=(
            mod_logs.mention
            if mod_logs
            else "❌ הערוץ לא נמצא"
        ),
        inline=False
    )

    embed.add_field(
        name="🗑️ Message Logs",
        value=(
            message_logs.mention
            if message_logs
            else "❌ הערוץ לא נמצא"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    print(
        f"SLASH ERROR: {type(error).__name__}: {error}"
    )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                "❌ אירעה שגיאה בפקודה. בדוק את ה-Railway Logs.",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "❌ אירעה שגיאה בפקודה.",
                ephemeral=True
            )

    except Exception:
        pass


# =========================================================
# READY
# =========================================================

synced_once = False


@bot.event
async def on_ready():

    global synced_once

    print(
        f"🦊 Logged in as {bot.user} ({bot.user.id})"
    )

    if synced_once:
        return

    # -----------------------------------------------------
    # STATIC PERSISTENT VIEWS
    # -----------------------------------------------------

    static_views = [
        XPShopView(),
        SuggestionPanelView(),
        TicketView(),
        WelcomeView(),
        DailyView(),
        PollView(),
    ]

    for view in static_views:

        try:

            bot.add_view(view)

        except Exception as e:

            print(
                f"Static view error: {e}"
            )

    # -----------------------------------------------------
    # RESTORE SUGGESTIONS
    # -----------------------------------------------------

    try:

        rows = cursor.execute("""
            SELECT id
            FROM suggestions
            WHERE message_id IS NOT NULL
        """).fetchall()

        for row in rows:

            try:

                bot.add_view(
                    SuggestionVoteView(
                        row["id"]
                    )
                )

            except Exception as e:

                print(
                    f"Suggestion restore error: {e}"
                )

    except Exception as e:

        print(
            f"Suggestion restore database error: {e}"
        )

    # -----------------------------------------------------
    # RESTORE TICKETS
    # -----------------------------------------------------

    try:

        rows = cursor.execute("""
            SELECT channel_id, message_id, staff_id
            FROM ticket_claims
        """).fetchall()

        for row in rows:

            try:

                bot.add_view(
                    TicketControlView(
                        row["channel_id"],
                        row["staff_id"]
                    ),
                    message_id=row["message_id"]
                )

            except Exception as e:

                print(
                    f"Ticket restore error: {e}"
                )

    except Exception as e:

        print(
            f"Ticket database error: {e}"
        )

    # -----------------------------------------------------
    # RESTORE GIVEAWAYS
    # -----------------------------------------------------

    try:

        rows = cursor.execute("""
            SELECT message_id
            FROM giveaways
            WHERE ended = 0
        """).fetchall()

        for row in rows:

            try:

                bot.add_view(
                    GiveawayView(
                        row["message_id"]
                    )
                )

            except Exception as e:

                print(
                    f"Giveaway restore error: {e}"
                )

    except Exception as e:

        print(
            f"Giveaway restore error: {e}"
        )

    # -----------------------------------------------------
    # RESTORE DROPS
    # -----------------------------------------------------

    try:

        rows = cursor.execute("""
            SELECT message_id
            FROM drops
            WHERE ended = 0
        """).fetchall()

        for row in rows:

            try:

                bot.add_view(
                    DropView(
                        row["message_id"]
                    )
                )

            except Exception as e:

                print(
                    f"Drop restore error: {e}"
                )

    except Exception as e:

        print(
            f"Drop restore error: {e}"
        )

    # -----------------------------------------------------
    # GIVEAWAY LOOP
    # -----------------------------------------------------

    if not giveaway_loop.is_running():

        giveaway_loop.start()

    # -----------------------------------------------------
    # SYNC
    # -----------------------------------------------------

    try:

        synced = await bot.tree.sync(
            guild=GUILD
        )

        print(
            f"✅ Synced {len(synced)} commands"
        )

        for command in synced:

            print(
                f"   /{command.name}"
            )

    except Exception as e:

        print(
            f"Command sync error: {e}"
        )

    synced_once = True

    print(
        "🦊 Foxes bot is ONLINE!"
    )


# =========================================================
# RUN
# =========================================================

if not DISCORD_TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN לא מוגדר ב-Environment Variables."
    )


bot.run(
    DISCORD_TOKEN
)