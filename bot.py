code = r'''import discord
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

XP_PER_MESSAGE = 50
XP_COOLDOWN = 60
BOOSTER_XP_MULTIPLIER = 2
BOOST_REWARD_XP = 1000

WELCOME_CHANNEL_NAME = "ברוכים-הבאים-👋"
BOOST_CHANNEL_NAME = "boost"
MOD_LOG_CHANNEL_NAME = "mod-logs"
MESSAGE_LOG_CHANNEL_NAME = "message-logs"
GAME_CHANNEL_NAME = "משחקים"

SUGGESTION_PANEL_CHANNEL_NAME = "הצעות"
SUGGESTIONS_CHANNEL_NAME = "📋・הצעות-שהוצעו"
TICKET_CATEGORY_NAME = "🎫・טיקטים"
LOG_CATEGORY_NAME = "📋・לוגים"

VERIFIED_ROLE_NAME = "Member"
UPDATES_ROLE_NAME = "🔔・עדכונים"
GIVEAWAYS_ROLE_NAME = "🎉・הגרלות"
DAILY_SPECIAL_ROLE_NAME = "Daily Fox"

RULES_CHANNEL_NAME = "📜・חוקים"

DAILY_REWARDS = {
    1: 10,
    2: 20,
    3: 50,
    4: 100,
    5: 150,
    6: 200
}

SPAM_MESSAGE_LIMIT = 5
SPAM_TIME_WINDOW = 8
SPAM_TIMEOUT_SECONDS = 20

RAID_JOIN_LIMIT = 6
RAID_TIME_WINDOW = 10

STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "KING FOX"
}

XP_ROLES = {
    2500: "Active Member",
    5000: "Elite Member",
    10000: "Premium",
    20000: "Legend",
    35000: "OG Fox",
    50000: "Royal Fox",
}

TICKET_TYPES = {
    "support": {
        "label": "תמיכה",
        "emoji": "🛠️",
        "description": "עזרה או בעיה בשרת",
        "color": discord.Color.blurple()
    },
    "report": {
        "label": "דיווח על משתמש",
        "emoji": "🚨",
        "description": "דיווח על משתמש או התנהגות",
        "color": discord.Color.red()
    },
    "bug": {
        "label": "דיווח על באג",
        "emoji": "🐛",
        "description": "דיווח על באג או תקלה",
        "color": discord.Color.orange()
    },
    "staff": {
        "label": "פנייה לצוות",
        "emoji": "👮",
        "description": "פנייה ישירה לצוות",
        "color": discord.Color.green()
    },
    "purchase": {
        "label": "רכישה / מכירה",
        "emoji": "💰",
        "description": "שאלות בנושא רכישות או מכירות",
        "color": discord.Color.gold()
    },
    "question": {
        "label": "שאלה כללית",
        "emoji": "❓",
        "description": "שאלה שלא מתאימה לאפשרויות האחרות",
        "color": discord.Color.purple()
    },
}

# Anti-Link: checked on every guild message, in every channel.
# Includes common URL forms even when users omit http/https.
LINK_RE = re.compile(
    r"(?ix)"
    r"(?:"
    r"https?://\S+"
    r"|www\.\S+"
    r"|discord\.gg/\S+"
    r"|discord(?:app)?\.com/invite/\S+"
    r"|(?:^|\s)(?:[a-z0-9-]+\.)+(?:com|net|org|gg|co\.il|il|me|io|dev|xyz|site|store|shop)(?:/\S*)?"
    r")"
)

GREETINGS = {
    "בוקר טוב": "בוקר טוב",
    "צהריים טובים": "צהריים טובים",
    "ערב טוב": "ערב טוב",
    "לילה טוב": "לילה טוב",
}

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
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

conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")

conn.executescript("""
CREATE TABLE IF NOT EXISTS xp (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS warnings (
    user_id INTEGER PRIMARY KEY,
    warnings INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    message_id INTEGER,
    channel_id INTEGER,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestion_votes (
    suggestion_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    vote INTEGER NOT NULL,
    PRIMARY KEY (suggestion_id, user_id)
);

CREATE TABLE IF NOT EXISTS ticket_claims (
    channel_id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL,
    staff_id INTEGER
);

CREATE TABLE IF NOT EXISTS daily (
    user_id INTEGER PRIMARY KEY,
    streak INTEGER NOT NULL DEFAULT 0,
    last_claim INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS giveaways (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    prize TEXT NOT NULL,
    winners INTEGER NOT NULL,
    end_time INTEGER NOT NULL,
    ended INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS giveaway_entries (
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (message_id, user_id)
);

CREATE TABLE IF NOT EXISTS drops (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    reward TEXT NOT NULL,
    xp_reward INTEGER NOT NULL DEFAULT 0,
    ended INTEGER NOT NULL DEFAULT 0,
    winner_id INTEGER
);
""")

# Migration for older bot_data.db files.
try:
    conn.execute("ALTER TABLE drops ADD COLUMN winner_id INTEGER")
    conn.commit()
except sqlite3.OperationalError:
    pass

conn.commit()

db_lock = asyncio.Lock()
log_lock = asyncio.Lock()
ticket_lock = asyncio.Lock()

# =========================================================
# HELPERS
# =========================================================

def db_one(sql, params=()):
    return conn.execute(sql, params).fetchone()


def db_all(sql, params=()):
    return conn.execute(sql, params).fetchall()


def db_run(sql, params=()):
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.rowcount, cur.lastrowid


def get_channel(guild, name):
    return discord.utils.get(guild.text_channels, name=name)


def get_role(guild, name):
    return discord.utils.get(guild.roles, name=name)


def is_staff(member):
    return bool(
        member.guild_permissions.administrator
        or any(
            role.name.upper() in STAFF_ROLES
            for role in member.roles
        )
    )


def staff_roles(guild):
    return sorted(
        [
            r for r in guild.roles
            if not r.managed and r.name.upper() in STAFF_ROLES
        ],
        key=lambda r: r.position,
        reverse=True,
    )


def staff_mentions(guild):
    return " ".join(
        r.mention for r in staff_roles(guild)
    )


async def ensure_log_channel(guild, name):
    existing = get_channel(guild, name)

    if existing:
        return existing

    async with log_lock:
        existing = get_channel(guild, name)

        if existing:
            return existing

        me = guild.me

        if not me or not me.guild_permissions.manage_channels:
            return None

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                read_message_history=True,
                manage_messages=True,
            ),
        }

        for role in staff_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                embed_links=True,
            )

        category = discord.utils.get(
            guild.categories,
            name=LOG_CATEGORY_NAME
        )

        if category is None:
            try:
                category = await guild.create_category(
                    LOG_CATEGORY_NAME,
                    reason="Foxes log system"
                )
            except discord.HTTPException:
                category = None

        try:
            return await guild.create_text_channel(
                name,
                category=category,
                overwrites=overwrites,
                reason="Foxes log system",
            )
        except discord.HTTPException as e:
            print(f"Create log channel error: {e}")
            return None


async def send_mod_log(
    guild,
    title,
    description,
    color=discord.Color.blurple()
):
    channel = await ensure_log_channel(
        guild,
        MOD_LOG_CHANNEL_NAME
    )

    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    embed.set_footer(text="Foxes • Mod Logs")

    try:
        await channel.send(embed=embed)
    except discord.HTTPException as e:
        print(f"Mod log error: {e}")


async def send_message_log(
    guild,
    title,
    description,
    color=discord.Color.orange()
):
    channel = await ensure_log_channel(
        guild,
        MESSAGE_LOG_CHANNEL_NAME
    )

    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    embed.set_footer(text="Foxes • Message Logs")

    try:
        await channel.send(embed=embed)
    except discord.HTTPException as e:
        print(f"Message log error: {e}")


def get_xp(user_id):
    row = db_one(
        "SELECT xp FROM xp WHERE user_id = ?",
        (user_id,)
    )
    return int(row["xp"]) if row else 0


def set_xp(user_id, amount):
    amount = max(0, int(amount))

    db_run(
        """
        INSERT INTO xp(user_id, xp)
        VALUES(?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET xp=excluded.xp
        """,
        (user_id, amount)
    )

    # Verify the exact value actually stored.
    return get_xp(user_id)


def add_xp(user_id, amount):
    amount = int(amount)

    db_run(
        """
        INSERT INTO xp(user_id, xp)
        VALUES(?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET xp=xp+excluded.xp
        """,
        (user_id, amount)
    )

    return get_xp(user_id)


def remove_xp(user_id, amount):
    amount = max(0, int(amount))

    db_run(
        """
        INSERT INTO xp(user_id, xp)
        VALUES(?, 0)
        ON CONFLICT(user_id) DO NOTHING
        """,
        (user_id,)
    )

    db_run(
        """
        UPDATE xp
        SET xp=MAX(0, xp-?)
        WHERE user_id=?
        """,
        (amount, user_id)
    )

    return get_xp(user_id)


def get_warnings(user_id):
    row = db_one(
        "SELECT warnings FROM warnings WHERE user_id=?",
        (user_id,)
    )
    return int(row["warnings"]) if row else 0


def add_warning(user_id):
    amount = get_warnings(user_id) + 1

    db_run(
        """
        INSERT INTO warnings(user_id, warnings)
        VALUES(?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET warnings=excluded.warnings
        """,
        (user_id, amount)
    )

    return amount


def get_daily_data(user_id):
    row = db_one(
        "SELECT streak,last_claim FROM daily WHERE user_id=?",
        (user_id,)
    )

    return (
        (row["streak"], row["last_claim"])
        if row
        else (0, 0)
    )


def set_daily_data(user_id, streak, last_claim):
    db_run(
        """
        INSERT INTO daily(user_id,streak,last_claim)
        VALUES(?,?,?)
        ON CONFLICT(user_id)
        DO UPDATE SET
        streak=excluded.streak,
        last_claim=excluded.last_claim
        """,
        (user_id, streak, last_claim)
    )


def can_moderate(actor, target):
    if target.id == actor.id:
        return False

    if target.id == actor.guild.owner_id:
        return False

    if actor.guild_permissions.administrator:
        return True

    return target.top_role < actor.top_role


def bot_can_moderate(guild, target):
    me = guild.me

    if not me:
        return False

    if target.id == guild.owner_id:
        return False

    if target.id == me.id:
        return False

    return target.top_role < me.top_role


# =========================================================
# MODERATION / WARNING ENGINE
# =========================================================

async def apply_warning(
    guild,
    user,
    reason,
    moderator=None,
    source="Manual"
):
    amount = add_warning(user.id)

    action = "⚠️ אזהרה בלבד"
    action_ok = True

    if amount == 2:
        action = "🔇 Timeout ל־3 שעות"

        if bot_can_moderate(guild, user):
            try:
                await user.timeout(
                    timedelta(hours=3),
                    reason=f"Warning 2: {reason}"[:512],
                )
            except discord.HTTPException:
                action_ok = False
        else:
            action_ok = False

    elif amount == 3:
        action = "🔇 Timeout ל־10 שעות"

        if bot_can_moderate(guild, user):
            try:
                await user.timeout(
                    timedelta(hours=10),
                    reason=f"Warning 3: {reason}"[:512],
                )
            except discord.HTTPException:
                action_ok = False
        else:
            action_ok = False

    elif amount == 4:
        action = "🔨 Timeout ל־3 ימים"

        if bot_can_moderate(guild, user):
            try:
                await user.timeout(
                    timedelta(days=3),
                    reason=f"Warning 4: {reason}"[:512],
                )
            except discord.HTTPException:
                action_ok = False
        else:
            action_ok = False

    elif amount >= 5:
        action = "🔨 Ban"

        if bot_can_moderate(guild, user):
            try:
                await user.ban(
                    reason=f"Warning {amount}: {reason}"[:512]
                )
            except discord.HTTPException:
                action_ok = False
        else:
            action_ok = False

    if not action_ok:
        action += " — ❌ הפעולה נכשלה"

    dm = discord.Embed(
        title="⚠️ קיבלת אזהרה ב-Foxes",
        description=(
            f"📝 **סיבה:** {reason}\n"
            f"⚠️ **מספר אזהרות:** {amount}\n"
            f"🎯 **פעולה:** {action}"
        ),
        color=discord.Color.red(),
    )

    try:
        await user.send(embed=dm)
    except discord.HTTPException:
        pass

    moderator_text = (
        moderator.mention
        if moderator
        else "מערכת Anti-Link"
    )

    await send_mod_log(
        guild,
        "⚠️ אזהרה חדשה",
        (
            f"👤 משתמש: {user.mention}\n"
            f"👮 מבצע: {moderator_text}\n"
            f"⚠️ אזהרות: **{amount}**\n"
            f"📝 סיבה: {reason}\n"
            f"🎯 פעולה: {action}\n"
            f"🤖 מקור: {source}"
        ),
        discord.Color.red(),
    )

    return amount, action


# =========================================================
# MESSAGE EVENTS
# =========================================================

xp_cooldowns = {}
spam_tracker = defaultdict(deque)
raid_joins = defaultdict(deque)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.guild is None:
        await bot.process_commands(message)
        return

    member = message.author

    if not isinstance(member, discord.Member):
        await bot.process_commands(message)
        return

    # =====================================================
    # ANTI-LINK
    # Works in EVERY channel of EVERY guild the bot is in.
    # Staff are exempt.
    # =====================================================
    if (
        not is_staff(member)
        and LINK_RE.search(message.content or "")
    ):
        try:
            await message.delete(
                reason="Anti-Link"
            )
        except discord.Forbidden:
            print(
                f"Anti-Link: missing Manage Messages in "
                f"{message.guild.name} / #{message.channel.name}"
            )
        except discord.HTTPException as e:
            print(f"Anti-Link delete error: {e}")

        amount, action = await apply_warning(
            message.guild,
            member,
            "שליחת קישור אסורה בשרת.",
            source="Anti-Link",
        )

        try:
            await message.channel.send(
                (
                    f"❌ {member.mention}, אסור לשלוח קישורים בשרת.\n"
                    f"⚠️ אזהרה #{amount} • {action}"
                ),
                delete_after=8,
                allowed_mentions=discord.AllowedMentions(
                    users=True
                ),
            )
        except discord.HTTPException:
            pass

        return

    # =====================================================
    # STAFF MENTION PROTECTION
    # =====================================================
    if not is_staff(member):
        mentioned_staff_role = any(
            role.name.upper() in STAFF_ROLES
            for role in message.role_mentions
        )

        mentioned_staff_user = any(
            isinstance(u, discord.Member)
            and is_staff(u)
            for u in message.mentions
        )

        if mentioned_staff_role or mentioned_staff_user:
            try:
                await message.delete(
                    reason="Mention protection"
                )
            except discord.HTTPException:
                pass

            try:
                await message.channel.send(
                    "❌ אינך יכול לתייג מודים ומעלה.",
                    delete_after=6,
                )
            except discord.HTTPException:
                pass

            await send_mod_log(
                message.guild,
                "🛡️ חסימת תיוג צוות",
                (
                    f"👤 משתמש: {member.mention}\n"
                    f"📍 ערוץ: {message.channel.mention}"
                ),
                discord.Color.orange(),
            )

            return

    # Greetings
    content = (message.content or "").strip()

    greeting = next(
        (
            reply
            for phrase, reply in GREETINGS.items()
            if phrase in content
        ),
        None
    )

    if greeting:
        try:
            await message.channel.send(
                f"{greeting}, {member.mention}! 🦊",
                allowed_mentions=discord.AllowedMentions(
                    users=True
                ),
            )
        except discord.HTTPException:
            pass

    # Anti-spam
    if not is_staff(member):
        now = time.time()
        history = spam_tracker[
            (message.guild.id, member.id)
        ]

        history.append(now)

        while (
            history
            and now - history[0] > SPAM_TIME_WINDOW
        ):
            history.popleft()

        if len(history) >= SPAM_MESSAGE_LIMIT:
            if bot_can_moderate(
                message.guild,
                member
            ):
                try:
                    await member.timeout(
                        timedelta(
                            seconds=SPAM_TIMEOUT_SECONDS
                        ),
                        reason="Anti-Spam",
                    )

                    history.clear()

                    await send_mod_log(
                        message.guild,
                        "🛡️ Anti-Spam",
                        (
                            f"👤 משתמש: {member.mention}\n"
                            f"⏱️ Timeout: "
                            f"{SPAM_TIMEOUT_SECONDS} שניות\n"
                            f"📍 ערוץ: "
                            f"{message.channel.mention}"
                        ),
                        discord.Color.red(),
                    )

                except discord.HTTPException as e:
                    print(
                        f"Anti-spam error: {e}"
                    )

    # XP
    now = time.time()
    cooldown_key = (message.guild.id, member.id)
    last = xp_cooldowns.get(
        cooldown_key,
        0
    )

    if now - last >= XP_COOLDOWN:
        multiplier = (
            BOOSTER_XP_MULTIPLIER
            if member.premium_since
            else 1
        )

        add_xp(
            member.id,
            XP_PER_MESSAGE * multiplier
        )

        xp_cooldowns[cooldown_key] = now

    await bot.process_commands(message)


@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot:
        return

    content = (
        message.content
        or "(אין תוכן טקסטואלי)"
    )

    if len(content) > 1000:
        content = content[:1000] + "..."

    await send_message_log(
        message.guild,
        "🗑️ הודעה נמחקה",
        (
            f"👤 **משתמש:** {message.author.mention}\n"
            f"📍 **ערוץ:** {message.channel.mention}\n\n"
            f"💬 **תוכן:**\n```{content}```"
        ),
    )


@bot.event
async def on_message_edit(before, after):
    if (
        not before.guild
        or before.author.bot
        or before.content == after.content
    ):
        return

    old = (
        before.content
        or "(ריק)"
    )[:700]

    new = (
        after.content
        or "(ריק)"
    )[:700]

    await send_message_log(
        before.guild,
        "✏️ הודעה נערכה",
        (
            f"👤 **משתמש:** {before.author.mention}\n"
            f"📍 **ערוץ:** {before.channel.mention}\n\n"
            f"🔴 **לפני:**\n```{old}```\n"
            f"🟢 **אחרי:**\n```{new}```"
        ),
        discord.Color.gold(),
    )


@bot.event
async def on_member_join(member):
    now = time.time()

    history = raid_joins[
        member.guild.id
    ]

    history.append(now)

    while (
        history
        and now - history[0] > RAID_TIME_WINDOW
    ):
        history.popleft()

    if len(history) >= RAID_JOIN_LIMIT:
        await send_mod_log(
            member.guild,
            "🚨 Anti-Raid Alert",
            (
                f"נכנסו **{len(history)} משתמשים** "
                f"ב־{RAID_TIME_WINDOW} שניות."
            ),
            discord.Color.red(),
        )

    channel = get_channel(
        member.guild,
        WELCOME_CHANNEL_NAME
    )

    if channel:
        embed = discord.Embed(
            title="🦊 ברוכים הבאים ל-Foxes!",
            description=(
                f"שלום {member.mention}!\n\n"
                f"ברוכים הבאים ל־**Foxes**.\n"
                f"אתה החבר ה־**{member.guild.member_count:,}** בשרת.\n\n"
                f"📜 קראו את {f'<#{get_channel(member.guild, RULES_CHANNEL_NAME).id}>' if get_channel(member.guild, RULES_CHANNEL_NAME) else f'`{RULES_CHANNEL_NAME}`'}.\n"
                "🔔 בחרו בפאנל למטה אם תרצו לקבל עדכונים.\n"
                "🎉 אפשר לבחור גם התראות על הגרלות.\n\n"
                "🦊 תהנו ב-Foxes!"
            ),
            color=discord.Color.blurple(),
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.set_footer(
            text="Foxes • Welcome"
        )

        try:
            await channel.send(
                embed=embed
            )

            await channel.send(
                embed=role_panel_embed(member.guild),
                view=RoleSelectionView()
            )
        except discord.HTTPException as e:
            print(
                f"Welcome error: {e}"
            )


@bot.event
async def on_member_remove(member):
    await send_mod_log(
        member.guild,
        "👋 משתמש עזב",
        (
            f"👤 **משתמש:** "
            f"{member} (`{member.id}`)"
        ),
        discord.Color.orange(),
    )


@bot.event
async def on_member_update(before, after):
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
                    f"🎉 {after.mention} עשה "
                    "Server Boost ל-Foxes!\n\n"
                    f"💎 **+{BOOST_REWARD_XP:,} XP**\n"
                    "🚀 **מעכשיו אתה מקבל X2 XP!**\n\n"
                    f"📊 XP נוכחי: **{new_xp:,} XP**\n\n"
                    "❤️ תודה ענקית על התמיכה!"
                ),
                color=discord.Color.fuchsia(),
            )

            embed.set_thumbnail(
                url=after.display_avatar.url
            )

            await channel.send(
                content=after.mention,
                embed=embed
            )


# =========================================================
# WELCOME / ROLES PANEL
# =========================================================

def role_panel_embed(guild):
    rules_channel = get_channel(
        guild,
        RULES_CHANNEL_NAME
    )

    rules_text = (
        f"{rules_channel.mention}"
        if rules_channel
        else f"`{RULES_CHANNEL_NAME}`"
    )

    return discord.Embed(
        title="📜 חוקים ורולים",
        description=(
            f"קודם כל עברו על החוקים: {rules_text}\n\n"
            "🔔 **עדכונים** — קבלו התראות ועדכונים מהשרת.\n"
            "🎉 **הגרלות** — קבלו התראות על הגרלות.\n\n"
            "אפשר לבחור **אחד מהם או את שניהם**.\n"
            "לחיצה נוספת על אותו כפתור תסיר את הרול."
        ),
        color=discord.Color.blurple()
    )


class RoleSelectionView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(
        self,
        interaction,
        role_name,
        label
    ):
        role = get_role(
            interaction.guild,
            role_name
        )

        if not role:
            return await interaction.response.send_message(
                f"❌ לא נמצא הרול `{role_name}`. צור אותו קודם.",
                ephemeral=True
            )

        me = interaction.guild.me

        if me and role >= me.top_role:
            return await interaction.response.send_message(
                f"❌ הבוט לא יכול לנהל את הרול `{role.name}`. "
                "שים את רול הבוט מעל הרול הזה.",
                ephemeral=True
            )

        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(
                    role,
                    reason="Role selection"
                )

                await interaction.response.send_message(
                    f"🔕 רול **{label}** הוסר ממך.",
                    ephemeral=True
                )
            else:
                await interaction.user.add_roles(
                    role,
                    reason="Role selection"
                )

                await interaction.response.send_message(
                    f"🔔 קיבלת את רול **{label}**!",
                    ephemeral=True
                )

        except discord.HTTPException as e:
            print(f"Role selection error: {e}")

            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ לא הצלחתי לשנות את הרול.",
                    ephemeral=True
                )

    @discord.ui.button(
        label="עדכונים",
        emoji="🔔",
        style=discord.ButtonStyle.primary,
        custom_id="role_updates_toggle"
    )
    async def updates(
        self,
        interaction,
        button
    ):
        await self.toggle_role(
            interaction,
            UPDATES_ROLE_NAME,
            "עדכונים"
        )

    @discord.ui.button(
        label="הגרלות",
        emoji="🎉",
        style=discord.ButtonStyle.success,
        custom_id="role_giveaways_toggle"
    )
    async def giveaways(
        self,
        interaction,
        button
    ):
        await self.toggle_role(
            interaction,
            GIVEAWAYS_ROLE_NAME,
            "הגרלות"
        )


@bot.tree.command(
    name="welcome",
    description="שלח את פאנל החוקים והרולים",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
async def welcome_command(interaction):
    if not is_staff(interaction.user):
        return await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את הפאנל.",
            ephemeral=True
        )

    channel = get_channel(
        interaction.guild,
        WELCOME_CHANNEL_NAME
    )

    if not channel:
        return await interaction.response.send_message(
            f"❌ לא נמצא הערוץ `{WELCOME_CHANNEL_NAME}`.",
            ephemeral=True
        )

    await channel.send(
        embed=role_panel_embed(interaction.guild),
        view=RoleSelectionView()
    )

    await interaction.response.send_message(
        f"✅ פאנל החוקים והרולים נשלח ל-{channel.mention}.",
        ephemeral=True
    )


# =========================================================
# XP COMMANDS
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
    interaction,
    user: Optional[discord.Member] = None
):
    target = user or interaction.user

    await interaction.response.send_message(
        f"⭐ ל-{target.mention} יש "
        f"**{get_xp(target.id):,} XP**."
    )


@bot.tree.command(
    name="leaderboard",
    description="טבלת ה-XP",
    guild=GUILD
)
async def leaderboard_command(interaction):
    rows = db_all(
        "SELECT user_id,xp FROM xp "
        "ORDER BY xp DESC LIMIT 10"
    )

    if not rows:
        return await interaction.response.send_message(
            "❌ עדיין אין נתוני XP."
        )

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    lines = []

    for i, row in enumerate(rows, 1):
        member = interaction.guild.get_member(
            row["user_id"]
        )

        name = (
            member.display_name
            if member
            else f"משתמש {row['user_id']}"
        )

        prefix = (
            medals[i - 1]
            if i <= 3
            else f"**{i}.**"
        )

        lines.append(
            f"{prefix} {name} — "
            f"**{row['xp']:,} XP**"
        )

    embed = discord.Embed(
        title="🏆 Foxes XP Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold()
    )

    await interaction.response.send_message(
        embed=embed
    )


async def staff_check(interaction):
    if (
        not isinstance(
            interaction.user,
            discord.Member
        )
        or not is_staff(interaction.user)
    ):
        await interaction.response.send_message(
            "❌ אין לך הרשאה.",
            ephemeral=True
        )
        return False

    return True


@bot.tree.command(
    name="addxp",
    description="הוסף XP",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    user="המשתמש",
    amount="כמות XP"
)
async def addxp_command(
    interaction,
    user: discord.Member,
    amount: int
):
    if not await staff_check(interaction):
        return

    if amount <= 0:
        return await interaction.response.send_message(
            "❌ הכמות חייבת להיות גדולה מ־0.",
            ephemeral=True
        )

    new = add_xp(
        user.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ נוסף ל-{user.mention} "
        f"**{amount:,} XP**.\n"
        f"⭐ XP נוכחי: **{new:,}**"
    )

    await send_mod_log(
        interaction.guild,
        "⭐ XP נוסף",
        (
            f"👤 משתמש: {user.mention}\n"
            f"👮 צוות: {interaction.user.mention}\n"
            f"➕ **{amount:,} XP**"
        ),
        discord.Color.green()
    )


@bot.tree.command(
    name="removexp",
    description="הסר XP",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    user="המשתמש",
    amount="כמות XP"
)
async def removexp_command(
    interaction,
    user: discord.Member,
    amount: int
):
    if not await staff_check(interaction):
        return

    if amount <= 0:
        return await interaction.response.send_message(
            "❌ הכמות חייבת להיות גדולה מ־0.",
            ephemeral=True
        )

    new = remove_xp(
        user.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ הוסרו מ-{user.mention} "
        f"**{amount:,} XP**.\n"
        f"⭐ XP נוכחי: **{new:,}**"
    )

    await send_mod_log(
        interaction.guild,
        "⭐ XP הוסר",
        (
            f"👤 משתמש: {user.mention}\n"
            f"👮 צוות: {interaction.user.mention}\n"
            f"➖ **{amount:,} XP**"
        ),
        discord.Color.orange()
    )


@bot.tree.command(
    name="setxp",
    description="קבע XP",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    user="המשתמש",
    amount="XP חדש"
)
async def setxp_command(
    interaction,
    user: discord.Member,
    amount: int
):
    if not await staff_check(interaction):
        return

    if amount < 0:
        return await interaction.response.send_message(
            "❌ XP לא יכול להיות שלילי.",
            ephemeral=True
        )

    actual = set_xp(
        user.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ ה-XP של {user.mention} "
        f"נקבע ל־**{actual:,} XP**.\n"
        f"🔎 נבדק ונשמר במסד הנתונים: **{get_xp(user.id):,} XP**"
    )

    await send_mod_log(
        interaction.guild,
        "⭐ XP נקבע",
        (
            f"👤 משתמש: {user.mention}\n"
            f"👮 צוות: {interaction.user.mention}\n"
            f"⭐ **{actual:,} XP**"
        )
    )


# =========================================================
# XP SHOP
# =========================================================

class XPShopButton(discord.ui.Button):

    def __init__(
        self,
        cost,
        role_name,
        row
    ):
        super().__init__(
            label=f"{cost:,} XP",
            emoji="🛒",
            style=discord.ButtonStyle.primary,
            custom_id=f"xp_buy_{cost}",
            row=row,
        )

        self.cost = cost
        self.role_name = role_name

    async def callback(self, interaction):
        role = get_role(
            interaction.guild,
            self.role_name
        )

        if not role:
            return await interaction.response.send_message(
                f"❌ הרול `{self.role_name}` לא קיים.",
                ephemeral=True
            )

        if role in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ כבר יש לך את הרול הזה.",
                ephemeral=True
            )

        current_xp = get_xp(
            interaction.user.id
        )

        if current_xp < self.cost:
            return await interaction.response.send_message(
                (
                    f"❌ אין לך מספיק XP.\n"
                    f"⭐ דרוש: **{self.cost:,}**\n"
                    f"⭐ יש לך: **{current_xp:,}**"
                ),
                ephemeral=True
            )

        if (
            interaction.guild.me
            and role >= interaction.guild.me.top_role
        ):
            return await interaction.response.send_message(
                "❌ הבוט לא יכול לתת את הרול הזה. "
                "שים את רול הבוט מעליו.",
                ephemeral=True
            )

        # Atomic purchase: deduct only if the user still
        # has enough XP. This also keeps the shop and /setxp
        # on the exact same database value.
        count, _ = db_run(
            """
            UPDATE xp
            SET xp=xp-?
            WHERE user_id=?
            AND xp>=?
            """,
            (
                self.cost,
                interaction.user.id,
                self.cost
            )
        )

        if count == 0:
            current_xp = get_xp(interaction.user.id)

            return await interaction.response.send_message(
                (
                    "❌ ה-XP השתנה לפני הרכישה.\n"
                    f"⭐ יש לך כרגע: **{current_xp:,} XP**"
                ),
                ephemeral=True
            )

        try:
            await interaction.user.add_roles(
                role,
                reason="XP Shop purchase"
            )

        except discord.HTTPException:
            add_xp(
                interaction.user.id,
                self.cost
            )

            return await interaction.response.send_message(
                "❌ לא הצלחתי לתת את הרול, וה-XP הוחזר.",
                ephemeral=True
            )

        await interaction.response.send_message(
            (
                f"🎉 קנית את **{role.name}** "
                f"תמורת **{self.cost:,} XP**!\n"
                f"⭐ נשארו לך **"
                f"{get_xp(interaction.user.id):,}"
                f" XP**."
            ),
            ephemeral=True
        )


class XPShopView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        for i, (cost, role) in enumerate(
            XP_ROLES.items()
        ):
            self.add_item(
                XPShopButton(
                    cost,
                    role,
                    i // 3
                )
            )


@bot.tree.command(
    name="xpshop",
    description="פתח את חנות ה-XP",
    guild=GUILD
)
async def xpshop_command(interaction):
    embed = discord.Embed(
        title="🛒 Foxes XP Shop",
        description=(
            "בחרו דרגה כדי לקנות אותה ב-XP."
        ),
        color=discord.Color.blurple()
    )

    for cost, role in XP_ROLES.items():
        embed.add_field(
            name=f"⭐ {cost:,} XP",
            value=f"🏷️ {role}",
            inline=True
        )

    await interaction.response.send_message(
        embed=embed,
        view=XPShopView()
    )


# =========================================================
# WARNINGS
# =========================================================

@bot.tree.command(
    name="warn",
    description="תן אזהרה",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    user="המשתמש",
    reason="סיבה"
)
async def warn_command(
    interaction,
    user: discord.Member,
    reason: str
):
    if not await staff_check(interaction):
        return

    if user.bot:
        return await interaction.response.send_message(
            "❌ אי אפשר לתת אזהרה לבוט.",
            ephemeral=True
        )

    if not can_moderate(
        interaction.user,
        user
    ):
        return await interaction.response.send_message(
            "❌ אינך יכול לבצע פעולה על משתמש בדרגה זהה או גבוהה משלך.",
            ephemeral=True
        )

    if not bot_can_moderate(
        interaction.guild,
        user
    ):
        return await interaction.response.send_message(
            "❌ הרול של המשתמש גבוה מדי עבור הבוט.",
            ephemeral=True
        )

    amount, action = await apply_warning(
        interaction.guild,
        user,
        reason,
        interaction.user,
        "Manual /warn"
    )

    embed = discord.Embed(
        title="⚠️ מערכת אזהרות",
        description=(
            f"👤 **משתמש:** {user.mention}\n"
            f"👮 **צוות:** {interaction.user.mention}\n"
            f"📝 **סיבה:** {reason}\n"
            f"⚠️ **אזהרות:** `{amount}`\n"
            f"🎯 **פעולה:** {action}"
        ),
        color=discord.Color.red()
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="warnings",
    description="בדוק אזהרות",
    guild=GUILD
)
@app_commands.describe(
    user="המשתמש"
)
async def warnings_command(
    interaction,
    user: Optional[discord.Member] = None
):
    target = user or interaction.user

    await interaction.response.send_message(
        f"⚠️ ל-{target.mention} יש "
        f"**{get_warnings(target.id)} אזהרות**."
    )


# =========================================================
# DAILY
# =========================================================

class DailyView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="קבל Daily XP",
        emoji="🎁",
        style=discord.ButtonStyle.success,
        custom_id="daily_claim"
    )
    async def claim(self, interaction, button):
        user_id = interaction.user.id

        streak, last = get_daily_data(
            user_id
        )

        now = int(time.time())

        if last and now - last < 86400:
            remaining = 86400 - (
                now - last
            )

            return await interaction.response.send_message(
                (
                    "⏳ כבר לקחת את ה-Daily היום.\n"
                    f"נסה שוב בעוד **"
                    f"{remaining // 3600} שעות ו-"
                    f"{(remaining % 3600)//60} דקות**."
                ),
                ephemeral=True
            )

        if last and now - last > 172800:
            streak = 0

        streak = (
            streak + 1
            if streak < 7
            else 1
        )

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

            if (
                role
                and role not in interaction.user.roles
            ):
                try:
                    await interaction.user.add_roles(
                        role,
                        reason="7 Day Daily Reward"
                    )
                except discord.HTTPException:
                    pass

            return await interaction.response.send_message(
                (
                    f"🔥 **יום 7!**\n"
                    f"🏆 קיבלת את הרול "
                    f"**{DAILY_SPECIAL_ROLE_NAME}**!"
                ),
                ephemeral=True
            )

        reward = DAILY_REWARDS[streak]

        new = add_xp(
            user_id,
            reward
        )

        await interaction.response.send_message(
            (
                f"🎁 **Daily יום {streak}**\n"
                f"⭐ קיבלת **{reward} XP**!\n"
                f"📊 XP נוכחי: **{new:,} XP**\n"
                f"🔥 רצף: **{streak}/7**"
            ),
            ephemeral=True
        )


@bot.tree.command(
    name="daily",
    description="שלח את פאנל ה-Daily",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
async def daily_command(interaction):
    if not await staff_check(interaction):
        return

    embed = discord.Embed(
        title="🎁 Foxes Daily",
        description=(
            "קחו Daily כל יום ושמרו על רצף!\n\n"
            "🟢 יום 1 — **10 XP**\n"
            "🟢 יום 2 — **20 XP**\n"
            "🟢 יום 3 — **50 XP**\n"
            "🟢 יום 4 — **100 XP**\n"
            "🟢 יום 5 — **150 XP**\n"
            "🟢 יום 6 — **200 XP**\n"
            "🏆 יום 7 — **רול מיוחד**"
        ),
        color=discord.Color.gold(),
    )

    await interaction.response.send_message(
        embed=embed,
        view=DailyView()
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
        interaction,
        button
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
        required=True,
    )

    async def on_submit(self, interaction):
        channel = get_channel(
            interaction.guild,
            SUGGESTIONS_CHANNEL_NAME
        )

        if not channel:
            return await interaction.response.send_message(
                f"❌ לא נמצא הערוץ `{SUGGESTIONS_CHANNEL_NAME}`.",
                ephemeral=True
            )

        _, suggestion_id = db_run(
            """
            INSERT INTO suggestions(
                user_id,
                content,
                created_at
            )
            VALUES(?,?,?)
            """,
            (
                interaction.user.id,
                str(self.content),
                int(time.time())
            ),
        )

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

        message = await channel.send(
            embed=embed,
            view=SuggestionVoteView(
                suggestion_id
            )
        )

        db_run(
            """
            UPDATE suggestions
            SET message_id=?,channel_id=?
            WHERE id=?
            """,
            (
                message.id,
                channel.id,
                suggestion_id
            )
        )

        await interaction.response.send_message(
            f"✅ ההצעה נשלחה ל-{channel.mention}!",
            ephemeral=True
        )


class SuggestionVoteView(discord.ui.View):

    def __init__(self, suggestion_id):
        super().__init__(timeout=None)

        self.suggestion_id = suggestion_id

        yes = db_one(
            """
            SELECT COUNT(*) c
            FROM suggestion_votes
            WHERE suggestion_id=? AND vote=1
            """,
            (suggestion_id,)
        )["c"]

        no = db_one(
            """
            SELECT COUNT(*) c
            FROM suggestion_votes
            WHERE suggestion_id=? AND vote=-1
            """,
            (suggestion_id,)
        )["c"]

        b1 = discord.ui.Button(
            label=f"בעד {yes}",
            emoji="👍",
            style=discord.ButtonStyle.success,
            custom_id=f"suggestion_yes_{suggestion_id}"
        )

        b2 = discord.ui.Button(
            label=f"נגד {no}",
            emoji="👎",
            style=discord.ButtonStyle.danger,
            custom_id=f"suggestion_no_{suggestion_id}"
        )

        b1.callback = self.yes
        b2.callback = self.no

        self.add_item(b1)
        self.add_item(b2)

    async def yes(self, interaction):
        await self.vote(
            interaction,
            1
        )

    async def no(self, interaction):
        await self.vote(
            interaction,
            -1
        )

    async def vote(
        self,
        interaction,
        vote
    ):
        existing = db_one(
            """
            SELECT vote
            FROM suggestion_votes
            WHERE suggestion_id=? AND user_id=?
            """,
            (
                self.suggestion_id,
                interaction.user.id
            ),
        )

        if existing:
            return await interaction.response.send_message(
                "❌ כבר הצבעת להצעה הזאת.",
                ephemeral=True
            )

        try:
            db_run(
                """
                INSERT INTO suggestion_votes(
                    suggestion_id,
                    user_id,
                    vote
                )
                VALUES(?,?,?)
                """,
                (
                    self.suggestion_id,
                    interaction.user.id,
                    vote
                ),
            )

        except sqlite3.IntegrityError:
            return await interaction.response.send_message(
                "❌ כבר הצבעת להצעה הזאת.",
                ephemeral=True
            )

        yes = db_one(
            """
            SELECT COUNT(*) c
            FROM suggestion_votes
            WHERE suggestion_id=? AND vote=1
            """,
            (self.suggestion_id,)
        )["c"]

        no = db_one(
            """
            SELECT COUNT(*) c
            FROM suggestion_votes
            WHERE suggestion_id=? AND vote=-1
            """,
            (self.suggestion_id,)
        )["c"]

        for item in self.children:
            if (
                item.custom_id
                == f"suggestion_yes_{self.suggestion_id}"
            ):
                item.label = f"בעד {yes}"

            if (
                item.custom_id
                == f"suggestion_no_{self.suggestion_id}"
            ):
                item.label = f"נגד {no}"

        await interaction.response.edit_message(
            view=self
        )


@bot.tree.command(
    name="suggestions",
    description="שלח פאנל הצעות",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
async def suggestions_command(interaction):
    if not await staff_check(interaction):
        return

    channel = get_channel(
        interaction.guild,
        SUGGESTION_PANEL_CHANNEL_NAME
    )

    if not channel:
        return await interaction.response.send_message(
            f"❌ לא נמצא הערוץ `{SUGGESTION_PANEL_CHANNEL_NAME}`.",
            ephemeral=True
        )

    embed = discord.Embed(
        title="💡 הצעות ל-Foxes",
        description=(
            "יש לכם רעיון לשיפור השרת?\n\n"
            "לחצו על **הצע רעיון** ושלחו אותו!"
        ),
        color=discord.Color.blurple()
    )

    await channel.send(
        embed=embed,
        view=SuggestionPanelView()
    )

    await interaction.response.send_message(
        f"✅ פאנל ההצעות נשלח ל-{channel.mention}.",
        ephemeral=True
    )


# =========================================================
# TICKETS
# =========================================================

def create_ticket_record(
    channel_id,
    message_id
):
    db_run(
        """
        INSERT OR REPLACE INTO ticket_claims(
            channel_id,
            message_id,
            staff_id
        )
        VALUES(?,?,NULL)
        """,
        (
            channel_id,
            message_id
        )
    )


def get_ticket_claim(channel_id):
    row = db_one(
        """
        SELECT staff_id
        FROM ticket_claims
        WHERE channel_id=?
        """,
        (channel_id,)
    )

    return (
        row["staff_id"]
        if row
        else None
    )


def claim_ticket(
    channel_id,
    staff_id
):
    count, _ = db_run(
        """
        UPDATE ticket_claims
        SET staff_id=?
        WHERE channel_id=?
        AND staff_id IS NULL
        """,
        (
            staff_id,
            channel_id
        )
    )

    return count > 0


def delete_ticket_record(channel_id):
    db_run(
        """
        DELETE FROM ticket_claims
        WHERE channel_id=?
        """,
        (channel_id,)
    )


class TicketControlView(discord.ui.View):

    def __init__(
        self,
        channel_id,
        claimed_by=None
    ):
        super().__init__(
            timeout=None
        )

        self.channel_id = channel_id

        take = discord.ui.Button(
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
            disabled=claimed_by is not None,
        )

        take.callback = self.take_ticket
        self.add_item(take)

        close = discord.ui.Button(
            label="סגור טיקט",
            emoji="🔒",
            style=discord.ButtonStyle.danger,
            custom_id=f"ticket_close_{channel_id}"
        )

        close.callback = self.close_ticket
        self.add_item(close)

    async def take_ticket(self, interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ רק הצוות יכול לקחת טיפול.",
                ephemeral=True
            )

        existing = get_ticket_claim(
            self.channel_id
        )

        if existing is not None:
            return await interaction.response.send_message(
                f"❌ הטיקט כבר בטיפול של <@{existing}>.",
                ephemeral=True
            )

        if not claim_ticket(
            self.channel_id,
            interaction.user.id
        ):
            return await interaction.response.send_message(
                "❌ מישהו אחר לקח את הטיקט.",
                ephemeral=True
            )

        embed = interaction.message.embeds[0].copy()

        for i, field in enumerate(
            embed.fields
        ):
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

    async def close_ticket(self, interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ רק הצוות יכול לסגור טיקט.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🔒 הטיקט ייסגר בעוד 5 שניות."
        )

        await send_mod_log(
            interaction.guild,
            "🔒 טיקט נסגר",
            (
                f"🎫 ערוץ: {interaction.channel.mention}\n"
                f"👮 נסגר על ידי: "
                f"{interaction.user.mention}"
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
        except discord.HTTPException as e:
            print(
                f"Ticket delete error: {e}"
            )


class TicketTypeSelect(discord.ui.Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label=d["label"],
                description=d["description"],
                emoji=d["emoji"],
                value=k
            )
            for k, d in TICKET_TYPES.items()
        ]

        super().__init__(
            placeholder="🎫 בחר את סוג הטיקט...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select"
        )

    async def callback(self, interaction):
        data = TICKET_TYPES[
            self.values[0]
        ]

        await create_ticket(
            interaction,
            self.values[0],
            data
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
    interaction,
    ticket_type,
    ticket_data
):
    guild = interaction.guild

    if not guild:
        return

    if not interaction.response.is_done():
        await interaction.response.defer(
            ephemeral=True
        )

    async with ticket_lock:
        existing = next(
            (
                c
                for c in guild.text_channels
                if c.topic
                and c.topic.startswith(
                    f"ticket_owner:{interaction.user.id};"
                )
            ),
            None
        )

        if existing:
            return await interaction.followup.send(
                f"❌ כבר יש לך טיקט פתוח: {existing.mention}",
                ephemeral=True
            )

        category = discord.utils.get(
            guild.categories,
            name=TICKET_CATEGORY_NAME
        )

        if not category:
            try:
                category = await guild.create_category(
                    TICKET_CATEGORY_NAME,
                    reason="Ticket System"
                )

            except discord.HTTPException:
                return await interaction.followup.send(
                    "❌ לא הצלחתי ליצור את קטגוריית הטיקטים.",
                    ephemeral=True
                )

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
                ),
        }

        me = guild.me

        if me:
            overwrites[me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )

        for role in staff_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )

        try:
            channel = await guild.create_text_channel(
                f"{ticket_type}-{interaction.user.id}",
                category=category,
                overwrites=overwrites,
                topic=(
                    f"ticket_owner:{interaction.user.id};"
                    f"type:{ticket_type}"
                ),
                reason=(
                    f"Ticket opened: "
                    f"{ticket_data['label']}"
                ),
            )

        except discord.HTTPException as e:
            print(
                f"Ticket channel error: {e}"
            )

            return await interaction.followup.send(
                "❌ לא הצלחתי ליצור את הטיקט. "
                "בדוק שלבוט יש Manage Channels.",
                ephemeral=True
            )

    embed = discord.Embed(
        title=(
            f"{ticket_data['emoji']} "
            f"{ticket_data['label']}"
        ),
        description=(
            f"שלום {interaction.user.mention}!\n\n"
            f"פתחת טיקט בנושא "
            f"**{ticket_data['label']}**.\n\n"
            "📝 כתוב כאן את פרטי הפנייה.\n"
            "👨‍💻 איש צוות יטפל בטיקט.\n\n"
            "🟢 **קח טיפול**\n"
            "🔒 **סגור טיקט**"
        ),
        color=ticket_data["color"],
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

    mentions = staff_mentions(
        guild
    )

    content = (
        f"{mentions}\n{interaction.user.mention}"
        if mentions
        else interaction.user.mention
    )

    allowed = discord.AllowedMentions(
        users=True,
        roles=True,
        everyone=False
    )

    try:
        message = await channel.send(
            content=content,
            embed=embed,
            view=TicketControlView(
                channel.id
            ),
            allowed_mentions=allowed,
        )

        create_ticket_record(
            channel.id,
            message.id
        )

    except discord.HTTPException as e:
        print(
            f"Ticket message error: {e}"
        )

        try:
            await channel.delete(
                reason="Ticket setup failed"
            )
        except discord.HTTPException:
            pass

        return await interaction.followup.send(
            "❌ הטיקט נוצר אבל לא הצלחתי לשלוח את ההודעה.",
            ephemeral=True
        )

    await interaction.followup.send(
        (
            "✅ הטיקט נפתח!\n"
            f"📂 סוג: **{ticket_data['label']}**\n"
            f"🎫 {channel.mention}"
        ),
        ephemeral=True
    )

    await send_mod_log(
        guild,
        "🎫 טיקט חדש",
        (
            f"👤 נפתח על ידי: "
            f"{interaction.user.mention}\n"
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
@app_commands.default_permissions(
    manage_messages=True
)
async def ticket_command(interaction):
    if not await staff_check(interaction):
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
            "❓ שאלה כללית"
        ),
        color=discord.Color.blurple(),
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


# =========================================================
# SAY / POLL / GAMES
# =========================================================

@bot.tree.command(
    name="say",
    description="שלח הודעה דרך הבוט",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    message="מה הבוט יכתוב"
)
async def say_command(
    interaction,
    message: str
):
    if not await staff_check(interaction):
        return

    await interaction.response.send_message(
        "✅ ההודעה נשלחה.",
        ephemeral=True
    )

    await interaction.channel.send(
        message,
        allowed_mentions=discord.AllowedMentions.none()
    )


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
        interaction,
        button
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
        interaction,
        button
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
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    question="שאלת הסקר"
)
async def poll_command(
    interaction,
    question: str
):
    if not await staff_check(interaction):
        return

    embed = discord.Embed(
        title="📊 סקר",
        description=question,
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        view=PollView()
    )


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
        interaction,
        button
    ):
        await interaction.response.send_message(
            f"🎲 המספר שלך הוא "
            f"**{random.randint(1,100)}**!",
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
        interaction,
        button
    ):
        await interaction.response.send_message(
            (
                f"🪙 יצא: **"
                f"{random.choice(['עץ','פלי'])}"
                f"**!"
            ),
            ephemeral=True
        )


@bot.tree.command(
    name="games",
    description="פתח פאנל משחקים",
    guild=GUILD
)
async def games_command(interaction):
    await interaction.response.send_message(
        embed=discord.Embed(
            title="🎮 Foxes Games",
            description="בחרו משחק והתחילו.",
            color=discord.Color.green()
        ),
        view=GamesView(),
    )


# =========================================================
# GIVEAWAYS
# =========================================================

def parse_duration(duration):
    match = re.fullmatch(
        r"(\d+)(s|m|h|d)",
        duration.lower().strip()
    )

    if not match:
        return None

    return int(match.group(1)) * {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }[match.group(2)]


class GiveawayView(discord.ui.View):

    def __init__(self, message_id):
        super().__init__(
            timeout=None
        )

        self.message_id = message_id

        b = discord.ui.Button(
            label="השתתף בהגרלה",
            emoji="🎉",
            style=discord.ButtonStyle.success,
            custom_id=f"giveaway_enter_{message_id}"
        )

        b.callback = self.enter
        self.add_item(b)

    async def enter(self, interaction):
        row = db_one(
            """
            SELECT ended
            FROM giveaways
            WHERE message_id=?
            """,
            (self.message_id,)
        )

        if not row or row["ended"]:
            return await interaction.response.send_message(
                "❌ ההגרלה כבר הסתיימה.",
                ephemeral=True
            )

        try:
            db_run(
                """
                INSERT INTO giveaway_entries(
                    message_id,
                    user_id
                )
                VALUES(?,?)
                """,
                (
                    self.message_id,
                    interaction.user.id
                )
            )

        except sqlite3.IntegrityError:
            return await interaction.response.send_message(
                "❌ אתה כבר משתתף בהגרלה.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🎉 נכנסת להגרלה בהצלחה!",
            ephemeral=True
        )


@bot.tree.command(
    name="giveaway",
    description="צור הגרלה",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    duration="לדוגמה: 10m / 1h / 1d",
    winners="מספר זוכים",
    prize="הפרס"
)
async def giveaway_command(
    interaction,
    duration: str,
    winners: int,
    prize: str
):
    if not await staff_check(interaction):
        return

    seconds = parse_duration(
        duration
    )

    if (
        seconds is None
        or seconds < 10
    ):
        return await interaction.response.send_message(
            "❌ זמן לא תקין. השתמש לדוגמה ב־`10m`, `2h`, `1d`.",
            ephemeral=True
        )

    if not 1 <= winners <= 50:
        return await interaction.response.send_message(
            "❌ מספר הזוכים חייב להיות בין 1 ל־50.",
            ephemeral=True
        )

    end = int(
        time.time() + seconds
    )

    embed = discord.Embed(
        title="🎉 GIVEAWAY",
        description=(
            f"🎁 **פרס:** {prize}\n\n"
            f"🏆 **זוכים:** {winners}\n"
            f"⏰ **מסתיים:** <t:{end}:R>\n\n"
            "לחצו על הכפתור כדי להשתתף!"
        ),
        color=discord.Color.gold()
    )

    await interaction.response.send_message(
        embed=embed
    )

    message = await interaction.original_response()

    db_run(
        """
        INSERT INTO giveaways(
            message_id,
            channel_id,
            guild_id,
            prize,
            winners,
            end_time
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            message.id,
            interaction.channel.id,
            interaction.guild.id,
            prize,
            winners,
            end
        )
    )

    await message.edit(
        view=GiveawayView(
            message.id
        )
    )


async def finish_giveaway(row):
    entries = db_all(
        """
        SELECT user_id
        FROM giveaway_entries
        WHERE message_id=?
        """,
        (row["message_id"],)
    )

    channel = bot.get_channel(
        row["channel_id"]
    )

    if not channel:
        db_run(
            """
            UPDATE giveaways
            SET ended=1
            WHERE message_id=?
            """,
            (row["message_id"],)
        )
        return

    try:
        message = await channel.fetch_message(
            row["message_id"]
        )
    except discord.HTTPException:
        message = None

    db_run(
        """
        UPDATE giveaways
        SET ended=1
        WHERE message_id=?
        """,
        (row["message_id"],)
    )

    if not entries:
        if message:
            await message.edit(
                embed=discord.Embed(
                    title="🎉 Giveaway הסתיימה",
                    description=(
                        f"🎁 פרס: **{row['prize']}**\n\n"
                        "❌ לא היו משתתפים."
                    ),
                    color=discord.Color.red()
                ),
                view=None
            )
        return

    selected = random.sample(
        [r["user_id"] for r in entries],
        min(
            row["winners"],
            len(entries)
        )
    )

    mentions = [
        f"<@{x}>"
        for x in selected
    ]

    if message:
        await message.edit(
            embed=discord.Embed(
                title="🎉 Giveaway הסתיימה!",
                description=(
                    f"🎁 **פרס:** {row['prize']}\n\n"
                    "🏆 **זוכים:**\n"
                    + "\n".join(mentions)
                ),
                color=discord.Color.green()
            ),
            view=None,
        )

    await channel.send(
        "🎉 מזל טוב ל-" +
        ", ".join(mentions) +
        "!",
        allowed_mentions=discord.AllowedMentions(
            users=True
        )
    )


@tasks.loop(seconds=5)
async def giveaway_loop():
    for row in db_all(
        """
        SELECT *
        FROM giveaways
        WHERE ended=0
        AND end_time<=?
        """,
        (int(time.time()),)
    ):
        try:
            await finish_giveaway(row)
        except Exception as e:
            print(
                f"Giveaway error: {e}"
            )


# =========================================================
# DROP
# =========================================================

class DropView(discord.ui.View):

    def __init__(self, message_id):
        super().__init__(
            timeout=None
        )

        self.message_id = message_id

        b = discord.ui.Button(
            label="קבלה",
            emoji="🎁",
            style=discord.ButtonStyle.success,
            custom_id=f"drop_claim_{message_id}"
        )

        b.callback = self.claim
        self.add_item(b)

    async def claim(self, interaction):
        # Atomically select the first claimant.
        # Only one interaction can change ended 0 -> 1.
        count, _ = db_run(
            """
            UPDATE drops
            SET ended=1, winner_id=?
            WHERE message_id=?
            AND ended=0
            """,
            (
                interaction.user.id,
                self.message_id
            )
        )

        if count == 0:
            return await interaction.response.send_message(
                "❌ הדרופ כבר נלקח.",
                ephemeral=True
            )

        row = db_one(
            """
            SELECT xp_reward
            FROM drops
            WHERE message_id=?
            """,
            (self.message_id,)
        )

        if not row:
            return await interaction.response.send_message(
                "❌ לא נמצא מידע על הדרופ.",
                ephemeral=True
            )

        xp_reward = int(row["xp_reward"])

        new = add_xp(
            interaction.user.id,
            xp_reward
        )

        # Disable the claim button on the public message.
        for item in self.children:
            item.disabled = True

        try:
            old_embed = (
                interaction.message.embeds[0]
                if interaction.message.embeds
                else discord.Embed(
                    title="🎁 XP DROP!",
                    color=discord.Color.green()
                )
            )

            embed = old_embed.copy()
            embed.title = "🎁 XP DROP — נתפס!"
            embed.description = (
                f"🏆 **הזוכה:** {interaction.user.mention}\n"
                f"⭐ **הפרס:** {xp_reward:,} XP"
            )
            embed.color = discord.Color.gold()

            await interaction.response.edit_message(
                embed=embed,
                view=self
            )

            await interaction.followup.send(
                (
                    f"🎉 זכית בדרופ!\n"
                    f"⭐ קיבלת **{xp_reward:,} XP**!\n"
                    f"📊 XP נוכחי: **{new:,} XP**"
                ),
                ephemeral=True
            )

        except discord.HTTPException:
            try:
                await interaction.response.send_message(
                    (
                        f"🎉 זכית בדרופ!\n"
                        f"⭐ קיבלת **{xp_reward:,} XP**!\n"
                        f"📊 XP נוכחי: **{new:,} XP**"
                    ),
                    ephemeral=True
                )
            except discord.HTTPException:
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
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    xp_reward="כמה XP הזוכה יקבל"
)
async def drop_command(
    interaction,
    xp_reward: int
):
    if not await staff_check(interaction):
        return

    if xp_reward <= 0:
        return await interaction.response.send_message(
            "❌ כמות ה-XP חייבת להיות גדולה מ־0.",
            ephemeral=True
        )

    embed = discord.Embed(
        title="🎁 XP DROP!",
        description=(
            f"⭐ **{xp_reward:,} XP**\n\n"
            "מי יהיה הראשון שיתפוס?"
        ),
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed,
        view=None
    )

    message = await interaction.original_response()

    db_run(
        """
        INSERT INTO drops(
            message_id,
            channel_id,
            guild_id,
            reward,
            xp_reward,
            ended,
            winner_id
        )
        VALUES(?,?,?,?,?,0,NULL)
        """,
        (
            message.id,
            interaction.channel.id,
            interaction.guild.id,
            f"{xp_reward:,} XP",
            xp_reward
        )
    )

    await message.edit(
        view=DropView(
            message.id
        )
    )


# =========================================================
# LOGS
# =========================================================

@bot.tree.command(
    name="logs",
    description="בדוק את ערוצי הלוגים",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
async def logs_command(interaction):
    if not await staff_check(interaction):
        return

    mod = await ensure_log_channel(
        interaction.guild,
        MOD_LOG_CHANNEL_NAME
    )

    msg = await ensure_log_channel(
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
            mod.mention
            if mod
            else "❌ לא ניתן ליצור"
        ),
        inline=False
    )

    embed.add_field(
        name="🗑️ Message Logs",
        value=(
            msg.mention
            if msg
            else "❌ לא ניתן ליצור"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(
    name="modlogs",
    description="פתח את חדר ה-Mod Logs",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
async def modlogs_command(interaction):
    if not await staff_check(interaction):
        return

    channel = await ensure_log_channel(
        interaction.guild,
        MOD_LOG_CHANNEL_NAME
    )

    if channel:
        await interaction.response.send_message(
            f"🛡️ Mod Logs: {channel.mention}",
            ephemeral=True
        )

    else:
        await interaction.response.send_message(
            "❌ לא ניתן ליצור את חדר ה-Mod Logs. "
            "בדוק Manage Channels.",
            ephemeral=True
        )


# =========================================================
# EXTRA COMMANDS
# =========================================================

@bot.tree.command(
    name="ping",
    description="בדוק את מהירות הבוט",
    guild=GUILD
)
async def ping_command(interaction):
    await interaction.response.send_message(
        f"🏓 Pong! **{round(bot.latency * 1000)}ms**"
    )


@bot.tree.command(
    name="serverinfo",
    description="מידע על השרת",
    guild=GUILD
)
async def serverinfo_command(interaction):
    guild = interaction.guild

    embed = discord.Embed(
        title=f"🦊 {guild.name}",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="👥 חברים",
        value=f"{guild.member_count:,}",
        inline=True
    )

    embed.add_field(
        name="💬 ערוצים",
        value=str(len(guild.channels)),
        inline=True
    )

    embed.add_field(
        name="🏷️ רולים",
        value=str(len(guild.roles)),
        inline=True
    )

    embed.add_field(
        name="👑 בעלים",
        value=(
            guild.owner.mention
            if guild.owner
            else "לא ידוע"
        ),
        inline=False
    )

    embed.add_field(
        name="📅 נוצר",
        value=discord.utils.format_dt(
            guild.created_at,
            "D"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="userinfo",
    description="מידע על משתמש",
    guild=GUILD
)
@app_commands.describe(
    user="המשתמש"
)
async def userinfo_command(
    interaction,
    user: Optional[discord.Member] = None
):
    member = user or interaction.user

    roles = [
        r.mention
        for r in reversed(member.roles[1:])
    ][:15]

    embed = discord.Embed(
        title=f"👤 {member.display_name}",
        color=member.color
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.add_field(
        name="🆔 ID",
        value=str(member.id),
        inline=False
    )

    embed.add_field(
        name="⭐ XP",
        value=f"{get_xp(member.id):,}",
        inline=True
    )

    embed.add_field(
        name="⚠️ אזהרות",
        value=str(
            get_warnings(member.id)
        ),
        inline=True
    )

    embed.add_field(
        name="📅 הצטרף",
        value=(
            discord.utils.format_dt(
                member.joined_at,
                "D"
            )
            if member.joined_at
            else "לא ידוע"
        ),
        inline=False
    )

    embed.add_field(
        name="🏷️ רולים",
        value=(
            " ".join(roles)
            if roles
            else "אין"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


@bot.tree.command(
    name="clear",
    description="מחק הודעות",
    guild=GUILD
)
@app_commands.default_permissions(
    manage_messages=True
)
@app_commands.describe(
    amount="כמה הודעות למחוק"
)
async def clear_command(
    interaction,
    amount: int
):
    if not await staff_check(interaction):
        return

    if not 1 <= amount <= 100:
        return await interaction.response.send_message(
            "❌ אפשר למחוק בין 1 ל־100 הודעות.",
            ephemeral=True
        )

    await interaction.response.defer(
        ephemeral=True
    )

    try:
        deleted = await interaction.channel.purge(
            limit=amount
        )

        await interaction.followup.send(
            f"🧹 נמחקו **{len(deleted)} הודעות**.",
            ephemeral=True
        )

        await send_mod_log(
            interaction.guild,
            "🧹 Clear",
            (
                f"👮 צוות: {interaction.user.mention}\n"
                f"📍 ערוץ: {interaction.channel.mention}\n"
                f"🗑️ נמחקו: **{len(deleted)}**"
            ),
            discord.Color.orange()
        )

    except discord.HTTPException:
        await interaction.followup.send(
            "❌ לא הצלחתי למחוק הודעות.",
            ephemeral=True
        )


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):
    print(
        f"SLASH ERROR: "
        f"{type(error).__name__}: {error}"
    )

    try:
        text = (
            "❌ אירעה שגיאה בפקודה. "
            "בדוק את ה-Railway Logs."
        )

        if interaction.response.is_done():
            await interaction.followup.send(
                text,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                text,
                ephemeral=True
            )

    except Exception:
        pass


# =========================================================
# READY / RESTORE
# =========================================================

synced_once = False


@bot.event
async def on_ready():
    global synced_once

    print(
        f"🦊 Logged in as "
        f"{bot.user} ({bot.user.id})"
    )

    if synced_once:
        return

    for view in [
        XPShopView(),
        SuggestionPanelView(),
        TicketView(),
        RoleSelectionView(),
        DailyView(),
        PollView()
    ]:
        try:
            bot.add_view(view)
        except Exception as e:
            print(
                f"Static view error: {e}"
            )

    # Restore suggestions
    for row in db_all(
        """
        SELECT id,message_id
        FROM suggestions
        WHERE message_id IS NOT NULL
        """
    ):
        try:
            bot.add_view(
                SuggestionVoteView(
                    row["id"]
                ),
                message_id=row["message_id"]
            )
        except Exception as e:
            print(
                f"Suggestion restore error: {e}"
            )

    # Restore tickets
    for row in db_all(
        """
        SELECT channel_id,message_id,staff_id
        FROM ticket_claims
        """
    ):
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

    # Restore giveaways
    for row in db_all(
        """
        SELECT message_id
        FROM giveaways
        WHERE ended=0
        """
    ):
        try:
            bot.add_view(
                GiveawayView(
                    row["message_id"]
                ),
                message_id=row["message_id"]
            )
        except Exception as e:
            print(
                f"Giveaway restore error: {e}"
            )

    # Restore active drops
    for row in db_all(
        """
        SELECT message_id
        FROM drops
        WHERE ended=0
        """
    ):
        try:
            bot.add_view(
                DropView(
                    row["message_id"]
                ),
                message_id=row["message_id"]
            )
        except Exception as e:
            print(
                f"Drop restore error: {e}"
            )

    if not giveaway_loop.is_running():
        giveaway_loop.start()

    # Remove old global slash commands
    try:
        bot.tree.clear_commands(
            guild=None
        )

        await bot.tree.sync()

        print(
            "🧹 Old global commands cleared"
        )

    except Exception as e:
        print(
            f"Global command cleanup error: {e}"
        )

    # Sync Foxes guild commands
    try:
        synced = await bot.tree.sync(
            guild=GUILD
        )

        print(
            f"✅ Synced {len(synced)} guild commands"
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

bot.run(DISCORD_TOKEN)
'''

path = "/mnt/data/bot.py"
with open(path, "w", encoding="utf-8") as f:
    f.write(code)

# Basic syntax validation before giving the file to the user.
import ast
ast.parse(code)

print(path)
print(f"{len(code):,} characters")
print("Syntax OK")
