import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import time
import re
import asyncio
import random
from datetime import timedelta

# =========================
# SETTINGS
# =========================

XP_PER_MESSAGE = 50
XP_COOLDOWN = 60

GUILD_ID = 1552344386526908488
GUILD = discord.Object(id=GUILD_ID)

WELCOME_CHANNEL_NAME = "ברוכים-הבאים-👋"
RULES_CHANNEL_NAME = "📜・חוקים"
SUGGESTIONS_CHANNEL_NAME = "💡・הצעות"

UPDATES_ROLE_NAME = "🔔・עדכונים"
GIVEAWAYS_ROLE_NAME = "🎉・הגרלות"

GAME_START_CHANNEL_NAME = "פתיחת-חדר-משחק"
GAME_CATEGORY_NAME = "חדר משחקים שפתחו"

STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "KING FOX"
}

# =========================
# DAILY SETTINGS
# =========================

DAILY_REWARDS = {
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 50,
    6: 60,
    7: 100
}

DAILY_COOLDOWN = 86400       # 24 שעות
DAILY_RESET_TIME = 172800    # 48 שעות

# =========================
# DATABASE
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS shop_items (
    role_id INTEGER PRIMARY KEY,
    price INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_users (
    user_id INTEGER PRIMARY KEY,
    streak INTEGER DEFAULT 0,
    last_claim INTEGER DEFAULT 0
)
""")

db.commit()

# =========================
# INTENTS
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
# HELPERS
# =========================

def get_role(guild, role_name):
    return discord.utils.get(
        guild.roles,
        name=role_name
    )


def get_channel(guild, channel_name):
    return discord.utils.get(
        guild.text_channels,
        name=channel_name
    )


def is_staff(member):

    if not isinstance(member, discord.Member):
        return False

    return any(
        role.name.upper() in STAFF_ROLES
        for role in member.roles
    )


async def get_game_category(guild):

    category = discord.utils.get(
        guild.categories,
        name=GAME_CATEGORY_NAME
    )

    if category is None:
        category = await guild.create_category(
            GAME_CATEGORY_NAME,
            reason="Foxes Game System"
        )

    return category


async def get_game_start_channel(guild):

    channel = get_channel(
        guild,
        GAME_START_CHANNEL_NAME
    )

    if channel:
        return channel

    category = await get_game_category(guild)

    channel = await guild.create_text_channel(
        GAME_START_CHANNEL_NAME,
        category=category,
        reason="Foxes Game System"
    )

    return channel


def clean_channel_name(name):

    name = name.lower()
    name = re.sub(r"[^a-zA-Z0-9א-ת_-]", "-", name)
    name = re.sub(r"-+", "-", name)
    return name[:40].strip("-")


async def create_private_game_channel(
    guild,
    player1,
    player2
):

    category = await get_game_category(guild)

    channel_name = (
        f"חדר-משחקים-של-"
        f"{clean_channel_name(player1.display_name)}-ו-"
        f"{clean_channel_name(player2.display_name)}"
    )

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=False
        ),

        player1: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        ),

        player2: discord.PermissionOverwrite(
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
        channel_name,
        category=category,
        overwrites=overwrites,
        reason="Private Foxes Game"
    )

    return channel


async def create_public_game_channel(
    guild,
    creator,
    game_name
):

    category = await get_game_category(guild)

    channel_name = (
        f"משחק-{clean_channel_name(game_name)}-"
        f"{clean_channel_name(creator.display_name)}"
    )

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            read_message_history=True
        ),

        creator: discord.PermissionOverwrite(
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
        channel_name,
        category=category,
        overwrites=overwrites,
        reason="Public Foxes Game"
    )

    return channel


async def close_game_channel(channel, delay=10):

    await asyncio.sleep(delay)

    try:
        await channel.delete(
            reason="Foxes game finished"
        )
    except:
        pass


# =========================
# DATABASE FUNCTIONS
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


def add_xp(user_id, amount):

    ensure_user(user_id)

    cursor.execute(
        "UPDATE users SET xp = xp + ? WHERE user_id = ?",
        (amount, user_id)
    )

    db.commit()


def remove_xp(user_id, amount):

    ensure_user(user_id)

    cursor.execute(
        """
        UPDATE users
        SET xp = MAX(0, xp - ?)
        WHERE user_id = ?
        """,
        (amount, user_id)
    )

    db.commit()


def get_warnings(user_id):

    ensure_user(user_id)

    cursor.execute(
        "SELECT warnings FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    return result[0] if result else 0


def add_warning(user_id):

    ensure_user(user_id)

    cursor.execute(
        "UPDATE users SET warnings = warnings + 1 WHERE user_id = ?",
        (user_id,)
    )

    db.commit()

    return get_warnings(user_id)


# =========================
# DAILY DATABASE
# =========================

def get_daily_data(user_id):

    cursor.execute(
        """
        SELECT streak, last_claim
        FROM daily_users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    result = cursor.fetchone()

    if result is None:
        return 0, 0

    return result[0], result[1]


def save_daily_data(user_id, streak, last_claim):

    cursor.execute(
        """
        INSERT INTO daily_users (
            user_id,
            streak,
            last_claim
        )
        VALUES (?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            streak = excluded.streak,
            last_claim = excluded.last_claim
        """,
        (
            user_id,
            streak,
            last_claim
        )
    )

    db.commit()


# =========================
# SHOP DATABASE
# =========================

def get_shop_items():

    cursor.execute(
        "SELECT role_id, price FROM shop_items ORDER BY price ASC"
    )

    return cursor.fetchall()


def add_shop_item(role_id, price):

    cursor.execute(
        "INSERT OR REPLACE INTO shop_items (role_id, price) VALUES (?, ?)",
        (role_id, price)
    )

    db.commit()


def remove_shop_item(role_id):

    cursor.execute(
        "DELETE FROM shop_items WHERE role_id = ?",
        (role_id,)
    )

    db.commit()


def get_shop_price(role_id):

    cursor.execute(
        "SELECT price FROM shop_items WHERE role_id = ?",
        (role_id,)
    )

    result = cursor.fetchone()

    return result[0] if result else None


# =========================
# ROLE SELECTION
# =========================

class RoleSelectionView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(
        self,
        interaction,
        role_name,
        display_name
    ):

        guild = interaction.guild

        role = get_role(
            guild,
            role_name
        )

        if role is None:

            await interaction.response.send_message(
                f"❌ הרול `{role_name}` לא נמצא.",
                ephemeral=True
            )

            return

        me = guild.me

        if me and role >= me.top_role:

            await interaction.response.send_message(
                f"❌ הבוט לא יכול לנהל את הרול **{role.name}**.",
                ephemeral=True
            )

            return

        try:

            if role in interaction.user.roles:

                await interaction.user.remove_roles(
                    role,
                    reason="Role selection"
                )

                await interaction.response.send_message(
                    f"🔕 הרול **{display_name}** הוסר.",
                    ephemeral=True
                )

            else:

                await interaction.user.add_roles(
                    role,
                    reason="Role selection"
                )

                await interaction.response.send_message(
                    f"🔔 קיבלת את הרול **{display_name}**!",
                    ephemeral=True
                )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ לבוט אין הרשאה לנהל את הרול.",
                ephemeral=True
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ אירעה שגיאה.",
                ephemeral=True
            )

    @discord.ui.button(
        label="עדכונים",
        emoji="🔔",
        style=discord.ButtonStyle.primary,
        custom_id="role_updates_toggle"
    )
    async def updates_button(
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
    async def giveaways_button(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            GIVEAWAYS_ROLE_NAME,
            "הגרלות"
        )


# =========================
# WELCOME
# =========================

def create_role_panel_embed(guild):

    rules_channel = get_channel(
        guild,
        RULES_CHANNEL_NAME
    )

    rules_text = (
        rules_channel.mention
        if rules_channel
        else f"#{RULES_CHANNEL_NAME}"
    )

    embed = discord.Embed(
        title="🎛️ פאנל חברים",
        description=(
            "**בחרו את ההתראות שתרצו לקבל:**\n\n"
            "🔔 **עדכונים**\n"
            "קבלת התראות ועדכונים חשובים.\n\n"
            "🎉 **הגרלות**\n"
            "קבלת התראות על הגרלות.\n\n"
            "💡 לחיצה נוספת תסיר את הרול.\n\n"
            f"📜 חוקים: {rules_text}"
        ),
        color=discord.Color.blue()
    )

    embed.set_footer(
        text="Foxes • Role Selection"
    )

    return embed


@bot.event
async def on_member_join(member):

    channel = get_channel(
        member.guild,
        WELCOME_CHANNEL_NAME
    )

    if channel is None:
        return

    embed = discord.Embed(
        title="🦊 ברוכים הבאים ל-Foxes!",
        description=(
            f"ברוכים הבאים {member.mention}!\n\n"
            f"**{member.display_name}** הצטרף עכשיו לשרת.\n\n"
            f"👥 אתם עכשיו **{member.guild.member_count}** חברים!\n\n"
            "📜 עברו על החוקים\n"
            "🎛️ בחרו את ההתראות שלכם"
        ),
        color=discord.Color.blue()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    await channel.send(
        embed=embed
    )

    await channel.send(
        embed=create_role_panel_embed(member.guild),
        view=RoleSelectionView()
    )


# =========================
# SHOP
# =========================

class ShopSelect(discord.ui.Select):

    def __init__(self, guild):

        options = []

        for role_id, price in get_shop_items():

            role = guild.get_role(role_id)

            if role is None:
                continue

            options.append(
                discord.SelectOption(
                    label=role.name[:100],
                    description=f"{price:,} XP",
                    emoji="🎭",
                    value=str(role.id)
                )
            )

        if not options:

            options.append(
                discord.SelectOption(
                    label="אין רולים בחנות",
                    description="הצוות עדיין לא הוסיף רולים",
                    value="none"
                )
            )

        super().__init__(
            placeholder="🛒 בחר רול לקנייה...",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction):

        value = self.values[0]

        if value == "none":

            await interaction.response.send_message(
                "❌ אין כרגע רולים בחנות.",
                ephemeral=True
            )

            return

        role = interaction.guild.get_role(
            int(value)
        )

        if role is None:

            await interaction.response.send_message(
                "❌ הרול לא קיים.",
                ephemeral=True
            )

            return

        price = get_shop_price(role.id)

        if price is None:

            await interaction.response.send_message(
                "❌ הרול כבר לא נמצא בחנות.",
                ephemeral=True
            )

            return

        if role in interaction.user.roles:

            await interaction.response.send_message(
                "❌ כבר יש לך את הרול הזה.",
                ephemeral=True
            )

            return

        xp = get_xp(
            interaction.user.id
        )

        if xp < price:

            await interaction.response.send_message(
                f"❌ אין לך מספיק XP.\n\n"
                f"💰 מחיר: **{price:,} XP**\n"
                f"📊 יש לך: **{xp:,} XP**\n"
                f"❗ חסרים: **{price - xp:,} XP**",
                ephemeral=True
            )

            return

        me = interaction.guild.me

        if me and role >= me.top_role:

            await interaction.response.send_message(
                "❌ הבוט לא יכול לתת את הרול הזה.",
                ephemeral=True
            )

            return

        cursor.execute(
            """
            UPDATE users
            SET xp = xp - ?
            WHERE user_id = ?
            AND xp >= ?
            """,
            (
                price,
                interaction.user.id,
                price
            )
        )

        if cursor.rowcount == 0:

            db.commit()

            await interaction.response.send_message(
                "❌ הרכישה נכשלה.",
                ephemeral=True
            )

            return

        db.commit()

        try:

            await interaction.user.add_roles(
                role,
                reason="XP Shop Purchase"
            )

        except:

            add_xp(
                interaction.user.id,
                price
            )

            await interaction.response.send_message(
                "❌ הבוט לא הצליח לתת את הרול. ה-XP הוחזר.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            f"✅ **הרכישה הצליחה!**\n\n"
            f"🎭 רול: **{role.name}**\n"
            f"💰 מחיר: **{price:,} XP**\n"
            f"📊 XP שנשאר: **{get_xp(interaction.user.id):,} XP**",
            ephemeral=True
        )


class ShopView(discord.ui.View):

    def __init__(self, guild):

        super().__init__(
            timeout=300
        )

        self.add_item(
            ShopSelect(guild)
        )


def create_shop_embed(guild):

    items = get_shop_items()

    description = (
        "🛒 **חנות ה-XP של Foxes**\n\n"
        "בחרו רול מהתפריט למטה כדי לקנות אותו.\n"
        "ה-XP יורד אוטומטית והרול ניתן מיד."
    )

    if not items:

        description += "\n\n❌ אין כרגע רולים למכירה."

    else:

        description += "\n\n**רולים בחנות:**\n"

        for role_id, price in items:

            role = guild.get_role(role_id)

            if role:

                description += (
                    f"🎭 {role.mention} — **{price:,} XP**\n"
                )

    return discord.Embed(
        title="🛒 חנות XP",
        description=description,
        color=discord.Color.gold()
    )


@bot.tree.command(
    name="shop",
    description="פתיחת חנות ה-XP"
)
async def shop_command(interaction):

    await interaction.response.send_message(
        embed=create_shop_embed(interaction.guild),
        view=ShopView(interaction.guild)
    )


@bot.tree.command(
    name="shopadd",
    description="הוספת רול לחנות"
)
@app_commands.describe(
    role="הרול",
    price="מחיר ב-XP"
)
async def shopadd_command(
    interaction,
    role: discord.Role,
    price: app_commands.Range[int, 1, 100000000]
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק מודים ומעלה יכולים להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    if role >= interaction.guild.me.top_role:

        await interaction.response.send_message(
            "❌ הבוט לא יכול לתת את הרול הזה.",
            ephemeral=True
        )

        return

    add_shop_item(
        role.id,
        price
    )

    await interaction.response.send_message(
        f"✅ **{role.name}** נוסף לחנות במחיר **{price:,} XP**.",
        ephemeral=True
    )


@bot.tree.command(
    name="shopremove",
    description="הסרת רול מהחנות"
)
@app_commands.describe(
    role="הרול"
)
async def shopremove_command(
    interaction,
    role: discord.Role
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק מודים ומעלה יכולים להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    remove_shop_item(
        role.id
    )

    await interaction.response.send_message(
        f"✅ **{role.name}** הוסר מהחנות.",
        ephemeral=True
    )


# =========================
# DAILY
# =========================

@bot.tree.command(
    name="daily",
    description="קבל את הפרס היומי שלך"
)
async def daily_command(interaction):

    user_id = interaction.user.id
    now = int(time.time())

    streak, last_claim = get_daily_data(user_id)

    # כבר לקח היום
    if last_claim and now - last_claim < DAILY_COOLDOWN:

        remaining = DAILY_COOLDOWN - (now - last_claim)

        hours = remaining // 3600
        minutes = (remaining % 3600) // 60

        embed = discord.Embed(
            title="🎁 Daily",
            description=(
                "❌ **כבר לקחת את ה־Daily שלך היום.**\n\n"
                f"⏰ תחזור בעוד **{hours} שעות ו־{minutes} דקות**."
            ),
            color=discord.Color.orange()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

        return

    # אם עברו 48 שעות - איפוס רצף
    if last_claim and now - last_claim >= DAILY_RESET_TIME:
        streak = 0

    # היום הבא
    day = (streak % 7) + 1

    reward = DAILY_REWARDS[day]

    add_xp(
        user_id,
        reward
    )

    save_daily_data(
        user_id,
        day,
        now
    )

    daily_text = ""

    for current_day in range(1, 8):

        current_reward = DAILY_REWARDS[current_day]

        if current_day < day:

            daily_text += (
                f"🟢 יום {current_day} — "
                f"**{current_reward} XP** ✓\n"
            )

        elif current_day == day:

            daily_text += (
                f"🟢 יום {current_day} — "
                f"**{current_reward} XP** ← **היום**\n"
            )

        else:

            daily_text += (
                f"⚪ יום {current_day} — "
                f"**{current_reward} XP**\n"
            )

    embed = discord.Embed(
        title="🎁 Daily Rewards",
        description=(
            f"🎉 **קיבלת {reward} XP!**\n\n"
            f"🔥 הרצף שלך: **יום {day}/7**"
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="📅 7 ימים",
        value=daily_text,
        inline=False
    )

    embed.add_field(
        name="📊 ה־XP שלך",
        value=f"**{get_xp(user_id):,} XP**",
        inline=False
    )

    embed.set_footer(
        text="Foxes • Daily"
    )

    # פרטי לחלוטין
    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================
# XP STAFF COMMANDS
# =========================

@bot.tree.command(
    name="addxp",
    description="הוספת XP למשתמש"
)
@app_commands.describe(
    member="המשתמש",
    amount="כמות XP"
)
async def addxp_command(
    interaction,
    member: discord.Member,
    amount: app_commands.Range[int, 1, 1000000]
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק מודים ומעלה יכולים להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    add_xp(
        member.id,
        amount
    )

    await interaction.response.send_message(
        f"✅ נוספו **{amount:,} XP** ל־{member.mention}.\n\n"
        f"📊 ה־XP החדש שלו: **{get_xp(member.id):,} XP**",
        ephemeral=True
    )


@bot.tree.command(
    name="removexp",
    description="הורדת XP ממשתמש"
)
@app_commands.describe(
    member="המשתמש",
    amount="כמות XP"
)
async def removexp_command(
    interaction,
    member: discord.Member,
    amount: app_commands.Range[int, 1, 1000000]
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק מודים ומעלה יכולים להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    before = get_xp(
        member.id
    )

    remove_xp(
        member.id,
        amount
    )

    after = get_xp(
        member.id
    )

    removed = before - after

    await interaction.response.send_message(
        f"✅ הורדו **{removed:,} XP** מ־{member.mention}.\n\n"
        f"📊 ה־XP החדש שלו: **{after:,} XP**",
        ephemeral=True
    )


# =========================
# SUGGESTION
# =========================

@bot.tree.command(
    name="suggestion",
    description="שליחת הצעה לשרת"
)
@app_commands.describe(
    suggestion="ההצעה שלך"
)
async def suggestion_command(
    interaction,
    suggestion: str
):

    channel = get_channel(
        interaction.guild,
        SUGGESTIONS_CHANNEL_NAME
    )

    if channel is None:

        await interaction.response.send_message(
            f"❌ חדר ההצעות `{SUGGESTIONS_CHANNEL_NAME}` לא נמצא.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="💡 הצעה חדשה",
        description=suggestion,
        color=discord.Color.blurple()
    )

    embed.set_author(
        name=interaction.user.display_name,
        icon_url=interaction.user.display_avatar.url
    )

    embed.set_footer(
        text=f"Foxes • Suggestion • ID: {interaction.user.id}"
    )

    message = await channel.send(
        embed=embed
    )

    await message.add_reaction("👍")
    await message.add_reaction("👎")

    await interaction.response.send_message(
        f"✅ ההצעה שלך נשלחה ל־{channel.mention}!",
        ephemeral=True
    )


# =========================
# GAME SYSTEM
# =========================

active_1v1 = {}


# =========================
# 1V1 INVITE
# =========================

class InviteUserView(discord.ui.View):

    def __init__(self, game_type, challenger):

        super().__init__(
            timeout=60
        )

        self.game_type = game_type
        self.challenger = challenger

    @discord.ui.button(
        label="בחר חבר להזמנה",
        emoji="👤",
        style=discord.ButtonStyle.primary
    )
    async def choose_friend(
        self,
        interaction,
        button
    ):

        if interaction.user.id != self.challenger.id:

            await interaction.response.send_message(
                "❌ רק מי שפתח את המשחק יכול לבחור יריב.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "בחר את החבר שאתה רוצה להזמין:",
            view=FriendSelectView(
                self.game_type,
                self.challenger
            ),
            ephemeral=True
        )


class FriendSelect(discord.ui.UserSelect):

    def __init__(
        self,
        game_type,
        challenger
    ):

        self.game_type = game_type
        self.challenger = challenger

        super().__init__(
            placeholder="👤 בחר שחקן...",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction):

        opponent = self.values[0]

        if opponent.id == self.challenger.id:

            await interaction.response.send_message(
                "❌ אי אפשר להזמין את עצמך.",
                ephemeral=True
            )

            return

        if opponent.bot:

            await interaction.response.send_message(
                "❌ אי אפשר להזמין בוט.",
                ephemeral=True
            )

            return

        game_name = {
            "coinflip": "🪙 Coin Flip",
            "rps": "✂️ אבן נייר ומספריים",
            "roulette": "🔫 רולטה רוסית"
        }.get(
            self.game_type,
            "🎮 משחק"
        )

        try:

            channel = await create_private_game_channel(
                interaction.guild,
                self.challenger,
                opponent
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ לבוט אין הרשאה ליצור חדרים.",
                ephemeral=True
            )

            return

        active_1v1[channel.id] = {
            "game": self.game_type,
            "player1": self.challenger.id,
            "player2": opponent.id
        }

        await interaction.response.send_message(
            f"✅ נפתח חדר משחק פרטי: {channel.mention}",
            ephemeral=True
        )

        await channel.send(
            f"{opponent.mention}\n\n"
            f"🎮 **{self.challenger.display_name}** "
            f"הזמין אותך ל־**{game_name}**!\n\n"
            "לחץ על אישור כדי להתחיל.",
            view=GameInviteView(
                self.game_type,
                self.challenger,
                opponent
            )
        )


class FriendSelectView(discord.ui.View):

    def __init__(
        self,
        game_type,
        challenger
    ):

        super().__init__(
            timeout=60
        )

        self.add_item(
            FriendSelect(
                game_type,
                challenger
            )
        )


class GameInviteView(discord.ui.View):

    def __init__(
        self,
        game_type,
        challenger,
        opponent
    ):

        super().__init__(
            timeout=120
        )

        self.game_type = game_type
        self.challenger = challenger
        self.opponent = opponent

    @discord.ui.button(
        label="אישור",
        emoji="✅",
        style=discord.ButtonStyle.success
    )
    async def accept(
        self,
        interaction,
        button
    ):

        if interaction.user.id != self.opponent.id:

            await interaction.response.send_message(
                "❌ רק השחקן שהוזמן יכול לאשר.",
                ephemeral=True
            )

            return

        await interaction.response.edit_message(
            content="✅ המשחק אושר! מתחילים...",
            view=None
        )

        if self.game_type == "coinflip":

            await start_coinflip(
                interaction.channel,
                self.challenger,
                self.opponent
            )

        elif self.game_type == "rps":

            await start_rps(
                interaction.channel,
                self.challenger,
                self.opponent
            )

        elif self.game_type == "roulette":

            await start_roulette(
                interaction.channel,
                self.challenger,
                self.opponent
            )

    @discord.ui.button(
        label="דחה",
        emoji="❌",
        style=discord.ButtonStyle.danger
    )
    async def decline(
        self,
        interaction,
        button
    ):

        if interaction.user.id != self.opponent.id:

            await interaction.response.send_message(
                "❌ רק השחקן שהוזמן יכול לדחות.",
                ephemeral=True
            )

            return

        await interaction.response.edit_message(
            content="❌ ההזמנה נדחתה.",
            view=None
        )

        await asyncio.sleep(5)

        try:
            await interaction.channel.delete()
        except:
            pass


# =========================
# COIN FLIP
# =========================

async def start_coinflip(
    channel,
    player1,
    player2
):

    result = random.choice(
        [player1, player2]
    )

    await channel.send(
        f"🪙 **COIN FLIP**\n\n"
        f"{player1.mention} נגד {player2.mention}\n\n"
        f"🪙 המטבע מסתובב...\n\n"
        f"🏆 המנצח: **{result.mention}**!"
    )

    await asyncio.sleep(8)

    try:
        await channel.delete(
            reason="Coin Flip finished"
        )
    except:
        pass


# =========================
# ROCK PAPER SCISSORS
# =========================

class RPSView(discord.ui.View):

    def __init__(
        self,
        player1,
        player2
    ):

        super().__init__(
            timeout=120
        )

        self.player1 = player1
        self.player2 = player2
        self.choices = {}

    async def make_choice(
        self,
        interaction,
        choice
    ):

        if interaction.user.id not in [
            self.player1.id,
            self.player2.id
        ]:

            await interaction.response.send_message(
                "❌ אתה לא משתתף במשחק.",
                ephemeral=True
            )

            return

        if interaction.user.id in self.choices:

            await interaction.response.send_message(
                "❌ כבר בחרת.",
                ephemeral=True
            )

            return

        self.choices[
            interaction.user.id
        ] = choice

        await interaction.response.send_message(
            "✅ הבחירה נקלטה.",
            ephemeral=True
        )

        if len(self.choices) != 2:
            return

        p1 = self.choices[
            self.player1.id
        ]

        p2 = self.choices[
            self.player2.id
        ]

        if p1 == p2:

            result = "🤝 תיקו!"

        elif (
            (p1 == "rock" and p2 == "scissors")
            or
            (p1 == "paper" and p2 == "rock")
            or
            (p1 == "scissors" and p2 == "paper")
        ):

            result = (
                f"🏆 המנצח: {self.player1.mention}"
            )

        else:

            result = (
                f"🏆 המנצח: {self.player2.mention}"
            )

        await interaction.channel.send(
            f"✂️ **אבן נייר ומספריים**\n\n"
            f"{self.player1.mention} נגד {self.player2.mention}\n\n"
            f"{result}"
        )

        self.stop()

        await asyncio.sleep(8)

        try:
            await interaction.channel.delete(
                reason="RPS finished"
            )
        except:
            pass

    @discord.ui.button(
        label="אבן",
        emoji="🪨",
        style=discord.ButtonStyle.primary
    )
    async def rock(
        self,
        interaction,
        button
    ):

        await self.make_choice(
            interaction,
            "rock"
        )

    @discord.ui.button(
        label="נייר",
        emoji="📄",
        style=discord.ButtonStyle.primary
    )
    async def paper(
        self,
        interaction,
        button
    ):

        await self.make_choice(
            interaction,
            "paper"
        )

    @discord.ui.button(
        label="מספריים",
        emoji="✂️",
        style=discord.ButtonStyle.primary
    )
    async def scissors(
        self,
        interaction,
        button
    ):

        await self.make_choice(
            interaction,
            "scissors"
        )


async def start_rps(
    channel,
    player1,
    player2
):

    await channel.send(
        f"✂️ **אבן נייר ומספריים — 1 נגד 1**\n\n"
        f"{player1.mention} נגד {player2.mention}\n\n"
        "בחרו את הבחירה שלכם:",
        view=RPSView(
            player1,
            player2
        )
    )


# =========================
# RUSSIAN ROULETTE
# =========================

class RouletteView(discord.ui.View):

    def __init__(
        self,
        player1,
        player2
    ):

        super().__init__(
            timeout=120
        )

        self.player1 = player1
        self.player2 = player2

        self.turn = player1
        self.chambers = list(range(1, 9))
        self.bullet = random.randint(1, 8)
        self.current_chamber = 1
        self.finished = False

    @discord.ui.button(
        label="לחץ על ההדק",
        emoji="🔫",
        style=discord.ButtonStyle.danger
    )
    async def pull_trigger(
        self,
        interaction,
        button
    ):

        if self.finished:
            return

        if interaction.user.id != self.turn.id:

            await interaction.response.send_message(
                f"❌ עכשיו התור של {self.turn.mention}.",
                ephemeral=True
            )

            return

        chamber = self.current_chamber

        if chamber == self.bullet:

            self.finished = True

            loser = self.turn

            winner = (
                self.player2
                if loser.id == self.player1.id
                else self.player1
            )

            try:

                await loser.timeout(
                    timedelta(seconds=60),
                    reason="הפסיד ברולטה רוסית"
                )

            except:

                pass

            await interaction.response.edit_message(
                content=(
                    "🔫 **רולטה רוסית — סיום המשחק**\n\n"
                    f"💥 {loser.mention} הפסיד!\n"
                    f"🏆 {winner.mention} ניצח!\n\n"
                    f"⏱️ {loser.mention} קיבל Timeout ל־**60 שניות**."
                ),
                view=None
            )

            await asyncio.sleep(10)

            try:
                await interaction.channel.delete(
                    reason="Russian Roulette finished"
                )
            except:
                pass

            return

        self.current_chamber += 1

        if self.current_chamber > 8:
            self.current_chamber = 1

        self.turn = (
            self.player2
            if self.turn.id == self.player1.id
            else self.player1
        )

        await interaction.response.edit_message(
            content=(
                "🔫 **רולטה רוסית**\n\n"
                f"{self.player1.mention} נגד {self.player2.mention}\n\n"
                f"🎚️ רמה: **קל**\n"
                f"🔴 1 כדור מתוך 8\n"
                f"🎯 תור: {self.turn.mention}\n\n"
                "לחץ על **לחץ על ההדק** כדי להמשיך."
            ),
            view=self
        )


async def start_roulette(
    channel,
    player1,
    player2
):

    embed = discord.Embed(
        title="🔫 רולטה רוסית",
        description=(
            f"{player1.mention} נגד {player2.mention}\n\n"
            "🎚️ **רמה: קל**\n"
            "🔴 **1 כדור מתוך 8**\n\n"
            "כל שחקן לוחץ בתורו.\n"
            "מי שפוגע בכדור — מפסיד.\n"
            "המפסיד מקבל **Timeout ל־60 שניות**.\n\n"
            f"🎯 תור ראשון: {player1.mention}"
        ),
        color=discord.Color.red()
    )

    await channel.send(
        embed=embed,
        view=RouletteView(
            player1,
            player2
        )
    )


# =========================
# PUBLIC DICE
# =========================

class PublicDiceView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=180
        )

        self.players = set()
        self.finished = False

    @discord.ui.button(
        label="הצטרף למשחק",
        emoji="🎮",
        style=discord.ButtonStyle.success
    )
    async def join(
        self,
        interaction,
        button
    ):

        if self.finished:
            return

        if interaction.user.bot:
            return

        if interaction.user.id in self.players:

            await interaction.response.send_message(
                "❌ אתה כבר במשחק.",
                ephemeral=True
            )

            return

        self.players.add(
            interaction.user.id
        )

        await interaction.response.send_message(
            "✅ הצטרפת למשחק!",
            ephemeral=True
        )

        await interaction.message.edit(
            content=(
                "🎲 **שדה הקובייה — משחק פתוח**\n\n"
                f"👥 שחקנים: **{len(self.players)}**\n\n"
                "לחצו על **הצטרף למשחק** כדי להיכנס.\n"
                "כשיש לפחות 2 שחקנים אפשר להתחיל."
            ),
            view=self
        )

    @discord.ui.button(
        label="הטל קובייה",
        emoji="🎲",
        style=discord.ButtonStyle.primary
    )
    async def roll(
        self,
        interaction,
        button
    ):

        if self.finished:
            return

        if interaction.user.id not in self.players:

            await interaction.response.send_message(
                "❌ קודם צריך להצטרף למשחק.",
                ephemeral=True
            )

            return

        if len(self.players) < 2:

            await interaction.response.send_message(
                "❌ צריך לפחות 2 שחקנים.",
                ephemeral=True
            )

            return

        self.finished = True

        results = []

        for user_id in self.players:

            member = interaction.guild.get_member(
                user_id
            )

            if member:

                results.append(
                    (
                        member,
                        random.randint(1, 6)
                    )
                )

        results.sort(
            key=lambda x: x[1],
            reverse=True
        )

        if not results:
            return

        text = "🎲 **תוצאות הקובייה**\n\n"

        for member, value in results:

            text += (
                f"{member.mention} — **{value}**\n"
            )

        highest = results[0][1]

        winners = [
            member
            for member, value in results
            if value == highest
        ]

        if len(winners) == 1:

            text += (
                f"\n🏆 המנצח: {winners[0].mention}"
            )

        else:

            text += (
                "\n🤝 תיקו בין: "
                + ", ".join(
                    member.mention
                    for member in winners
                )
            )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=text,
            view=self
        )

        await asyncio.sleep(10)

        try:
            await interaction.channel.delete(
                reason="Dice finished"
            )
        except:
            pass


# =========================
# PUBLIC GUESS
# =========================

class GuessView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=180
        )

        self.players = {}
        self.target_number = random.randint(
            1,
            100
        )
        self.creator_id = None
        self.finished = False

    @discord.ui.button(
        label="הצטרף והכנס ניחוש",
        emoji="🔢",
        style=discord.ButtonStyle.success
    )
    async def join(
        self,
        interaction,
        button
    ):

        if self.finished:
            return

        if interaction.user.id in self.players:

            await interaction.response.send_message(
                "❌ אתה כבר במשחק.",
                ephemeral=True
            )

            return

        self.players[
            interaction.user.id
        ] = None

        await interaction.response.send_modal(
            GuessModal(
                self
            )
        )

    @discord.ui.button(
        label="סיים משחק",
        emoji="🏁",
        style=discord.ButtonStyle.danger
    )
    async def finish(
        self,
        interaction,
        button
    ):

        if self.finished:
            return

        if interaction.user.id != self.creator_id:

            await interaction.response.send_message(
                "❌ רק מי שפתח את המשחק יכול לסיים אותו.",
                ephemeral=True
            )

            return

        valid = [
            (user_id, guess)
            for user_id, guess in self.players.items()
            if guess is not None
        ]

        if len(valid) < 2:

            await interaction.response.send_message(
                "❌ צריך לפחות 2 שחקנים עם ניחוש.",
                ephemeral=True
            )

            return

        self.finished = True

        number = self.target_number

        closest_distance = min(
            abs(guess - number)
            for _, guess in valid
        )

        winners = [
            user_id
            for user_id, guess in valid
            if abs(guess - number) == closest_distance
        ]

        mentions = []

        for user_id in winners:

            member = interaction.guild.get_member(
                user_id
            )

            if member:
                mentions.append(
                    member.mention
                )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=(
                "🔢 **Guess — תוצאות**\n\n"
                f"🎯 המספר היה **{number}**\n"
                f"🏆 המנצח: {', '.join(mentions)}"
            ),
            view=self
        )

        await asyncio.sleep(10)

        try:
            await interaction.channel.delete(
                reason="Guess finished"
            )
        except:
            pass


class GuessModal(discord.ui.Modal):

    def __init__(self, game):

        super().__init__(
            title="🔢 ניחוש מספר"
        )

        self.game = game

        self.answer = discord.ui.TextInput(
            label="בחר מספר בין 1 ל-100",
            placeholder="לדוגמה: 57",
            required=True,
            min_length=1,
            max_length=3
        )

        self.add_item(
            self.answer
        )

    async def on_submit(
        self,
        interaction
    ):

        try:

            number = int(
                self.answer.value
            )

            if number < 1 or number > 100:
                raise ValueError

        except:

            await interaction.response.send_message(
                "❌ צריך להכניס מספר בין 1 ל-100.",
                ephemeral=True
            )

            return

        self.game.players[
            interaction.user.id
        ] = number

        await interaction.response.send_message(
            f"✅ הניחוש שלך (**{number}**) נקלט.",
            ephemeral=True
        )


# =========================
# GAME PANEL
# =========================

class GamePanelView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="🪙 Coin Flip",
        style=discord.ButtonStyle.primary,
        custom_id="game_coinflip"
    )
    async def coinflip(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            "🪙 **Coin Flip — 1 נגד 1**\n\n"
            "בחר חבר והזמן אותו לחדר משחק פרטי.",
            view=InviteUserView(
                "coinflip",
                interaction.user
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="✂️ אבן נייר ומספריים",
        style=discord.ButtonStyle.primary,
        custom_id="game_rps"
    )
    async def rps(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            "✂️ **אבן נייר ומספריים — 1 נגד 1**\n\n"
            "בחר חבר והזמן אותו לחדר משחק פרטי.",
            view=InviteUserView(
                "rps",
                interaction.user
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="🔫 רולטה רוסית",
        style=discord.ButtonStyle.danger,
        custom_id="game_roulette"
    )
    async def roulette(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            "🔫 **רולטה רוסית — 1 נגד 1**\n\n"
            "🎚️ רמה: **קל**\n"
            "🔴 1 כדור מתוך 8\n"
            "⏱️ המפסיד מקבל Timeout ל־60 שניות.\n\n"
            "בחר חבר כדי לפתוח חדר פרטי.",
            view=InviteUserView(
                "roulette",
                interaction.user
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="🎲 קובייה",
        style=discord.ButtonStyle.success,
        custom_id="game_dice"
    )
    async def dice(
        self,
        interaction,
        button
    ):

        channel = await create_public_game_channel(
            interaction.guild,
            interaction.user,
            "קובייה"
        )

        game = PublicDiceView()

        game.players.add(
            interaction.user.id
        )

        await interaction.response.send_message(
            f"🎲 נפתח משחק ציבורי: {channel.mention}",
            ephemeral=True
        )

        await channel.send(
            "🎲 **קובייה — משחק פתוח לכולם**\n\n"
            f"👑 מי שפתח: {interaction.user.mention}\n\n"
            "👥 כל אחד יכול להצטרף.\n"
            "🎲 כשיש לפחות 2 שחקנים, אחד מהם יכול להטיל קובייה.\n\n"
            "המספר הגבוה ביותר מנצח.",
            view=game
        )

    @discord.ui.button(
        label="🔢 Guess",
        style=discord.ButtonStyle.success,
        custom_id="game_guess"
    )
    async def guess(
        self,
        interaction,
        button
    ):

        channel = await create_public_game_channel(
            interaction.guild,
            interaction.user,
            "ניחוש"
        )

        game = GuessView()

        game.creator_id = interaction.user.id

        game.players[
            interaction.user.id
        ] = None

        await interaction.response.send_message(
            f"🔢 נפתח משחק ציבורי: {channel.mention}",
            ephemeral=True
        )

        await channel.send(
            "🔢 **Guess — משחק פתוח לכולם**\n\n"
            f"👑 מי שפתח: {interaction.user.mention}\n\n"
            "🔢 המספר הוא בין **1 ל־100**.\n"
            "כל שחקן מצטרף ומכניס ניחוש.\n"
            "בסיום, הניחוש הקרוב ביותר למספר הסודי מנצח.\n\n"
            "רק מי שפתח את המשחק יכול לסיים אותו.",
            view=game
        )


@bot.tree.command(
    name="game",
    description="פתיחת פאנל המשחקים"
)
async def game_command(interaction):

    if interaction.channel.name != GAME_START_CHANNEL_NAME:

        await interaction.response.send_message(
            f"❌ את פאנל המשחקים פותחים רק בחדר "
            f"**#{GAME_START_CHANNEL_NAME}**.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎮 Foxes — חדר המתנה",
        description=(
            "**בחר משחק:**\n\n"

            "🪙 **Coin Flip**\n"
            "משחק 1 נגד 1. בחר חבר והזמן אותו לחדר פרטי.\n\n"

            "✂️ **אבן נייר ומספריים**\n"
            "משחק 1 נגד 1. כל שחקן בוחר מהלך.\n\n"

            "🔫 **רולטה רוסית**\n"
            "1 כדור מתוך 8. משחק 1 נגד 1.\n"
            "המפסיד מקבל Timeout ל־60 שניות.\n\n"

            "🎲 **קובייה**\n"
            "משחק פתוח לכולם. כולם יכולים להצטרף.\n\n"

            "🔢 **Guess**\n"
            "משחק פתוח לכולם. נחשו מספר בין 1 ל־100."
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="Foxes • Games"
    )

    await interaction.response.send_message(
        embed=embed,
        view=GamePanelView()
    )


# =========================
# TICKETS
# =========================

class TicketView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="פתיחת טיקט",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="open_ticket"
    )
    async def open_ticket(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            "בחר את סוג הפנייה:",
            view=TicketTypeView(),
            ephemeral=True
        )


class TicketTypeView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=60
        )

    @discord.ui.select(
        placeholder="בחר סוג פנייה...",
        options=[
            discord.SelectOption(
                label="באג",
                description="דיווח על תקלה",
                emoji="🐛",
                value="bug"
            ),
            discord.SelectOption(
                label="התקבלות לצוות",
                description="בקשה להצטרף לצוות",
                emoji="👮",
                value="staff"
            ),
            discord.SelectOption(
                label="דיווח על משתמש",
                description="דיווח על משתמש",
                emoji="🚨",
                value="report"
            )
        ]
    )
    async def ticket_type(
        self,
        interaction,
        select
    ):

        guild = interaction.guild
        user = interaction.user

        existing = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{user.id}"
        )

        if existing:

            await interaction.response.send_message(
                f"❌ כבר יש לך טיקט: {existing.mention}",
                ephemeral=True
            )

            return

        category = discord.utils.get(
            guild.categories,
            name="Tickets"
        )

        if category is None:

            category = await guild.create_category(
                "Tickets"
            )

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            guild.me:
                discord.PermissionOverwrite(
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

        names = {
            "bug": "🐛 באג",
            "staff": "👮 התקבלות לצוות",
            "report": "🚨 דיווח על משתמש"
        }

        ticket_type = names.get(
            select.values[0],
            "פנייה"
        )

        embed = discord.Embed(
            title="🎫 טיקט חדש",
            description=(
                f"שלום {user.mention}\n\n"
                f"**סוג הפנייה:** {ticket_type}\n\n"
                "צוות השרת יטפל בפנייה."
            ),
            color=discord.Color.blue()
        )

        await channel.send(
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ הטיקט נפתח: {channel.mention}",
            ephemeral=True
        )


class TicketControlView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="לקחת טיפול",
        emoji="👤",
        style=discord.ButtonStyle.success,
        custom_id="claim_ticket"
    )
    async def claim_ticket(
        self,
        interaction,
        button
    ):

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ רק צוות יכול לקחת טיפול.",
                ephemeral=True
            )

            return

        button.disabled = True

        await interaction.response.edit_message(
            view=self
        )

        await interaction.followup.send(
            f"👤 **{interaction.user.mention} לקח טיפול בטיקט.**"
        )

    @discord.ui.button(
        label="סגירת טיקט",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction,
        button
    ):

        if not is_staff(interaction.user):

            await interaction.response.send_message(
                "❌ רק צוות יכול לסגור טיקט.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 הטיקט ייסגר בעוד 3 שניות."
        )

        await asyncio.sleep(3)

        try:
            await interaction.channel.delete()
        except:
            pass


# =========================
# COMMANDS
# =========================

@bot.tree.command(
    name="xp",
    description="בדיקת כמות ה-XP שלך"
)
async def xp_command(interaction):

    xp = get_xp(
        interaction.user.id
    )

    await interaction.response.send_message(
        f"📊 יש לך **{xp:,} XP**.",
        ephemeral=True
    )


@bot.tree.command(
    name="warnings",
    description="בדיקת מספר האזהרות שלך"
)
async def warnings_command(interaction):

    warnings = get_warnings(
        interaction.user.id
    )

    await interaction.response.send_message(
        f"⚠️ יש לך **{warnings} אזהרות**.",
        ephemeral=True
    )


@bot.tree.command(
    name="warn",
    description="מתן אזהרה למשתמש"
)
@app_commands.describe(
    member="המשתמש",
    reason="סיבת האזהרה"
)
async def warn_command(
    interaction,
    member: discord.Member,
    reason: str
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק מודים ומעלה יכולים להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    warnings = add_warning(
        member.id
    )

    await interaction.response.send_message(
        f"⚠️ {member.mention} קיבל אזהרה.\n"
        f"סיבה: **{reason}**\n"
        f"סה״כ אזהרות: **{warnings}**"
    )

    try:

        await member.send(
            f"⚠️ קיבלת אזהרה ב־**{interaction.guild.name}**.\n"
            f"סיבה: {reason}"
        )

    except:
        pass


@bot.tree.command(
    name="ticket",
    description="שליחת פאנל טיקטים"
)
async def ticket_command(interaction):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק מודים ומעלה יכולים להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎫 מערכת הטיקטים",
        description=(
            "לחצו על **פתיחת טיקט** ובחרו סוג פנייה."
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


@bot.tree.command(
    name="welcome",
    description="שליחת פאנל הרולים"
)
async def welcome_command(interaction):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק מודים ומעלה יכולים להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        embed=create_role_panel_embed(
            interaction.guild
        ),
        view=RoleSelectionView()
    )


# =========================
# XP + LINK SYSTEM
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

        add_xp(
            user_id,
            XP_PER_MESSAGE
        )

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

        warnings = add_warning(
            user_id
        )

        try:

            await message.author.send(
                f"⚠️ ההודעה שלך נמחקה בגלל קישור.\n"
                f"מספר אזהרות: **{warnings}**"
            )

        except:
            pass

        return

    await bot.process_commands(
        message
    )


# =========================
# HELP
# =========================

@bot.tree.command(
    name="help",
    description="הצגת הפקודות שאתה יכול להשתמש בהן"
)
async def help_command(interaction):

    embed = discord.Embed(
        title="🦊 Foxes Bot — פקודות",
        description="הפקודות הזמינות עבורך:",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🎮 משחקים",
        value=(
            "`/game` — פתיחת חדר המשחקים\n"
            "🪙 Coin Flip — 1v1\n"
            "✂️ אבן נייר ומספריים — 1v1\n"
            "🔫 רולטה רוסית — 1v1\n"
            "🎲 קובייה — פתוח לכולם\n"
            "🔢 Guess — פתוח לכולם"
        ),
        inline=False
    )

    embed.add_field(
        name="🛒 חנות",
        value=(
            "`/shop` — פתיחת החנות"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 XP",
        value=(
            "`/xp` — בדיקת XP\n"
            "`/warnings` — בדיקת אזהרות"
        ),
        inline=False
    )

    embed.add_field(
        name="🎁 Daily",
        value=(
            "`/daily` — קבלת הפרס היומי והרצף שלך"
        ),
        inline=False
    )

    embed.add_field(
        name="💡 הצעות",
        value=(
            "`/suggestion` — שליחת הצעה לשרת"
        ),
        inline=False
    )

    if is_staff(interaction.user):

        embed.add_field(
            name="🛡️ פקודות צוות",
            value=(
                "`/warn` — מתן אזהרה\n"
                "`/addxp` — הוספת XP\n"
                "`/removexp` — הורדת XP\n"
                "`/shopadd` — הוספת רול לחנות\n"
                "`/shopremove` — הסרת רול מהחנות\n"
                "`/ticket` — שליחת פאנל טיקטים\n"
                "`/welcome` — שליחת פאנל רולים"
            ),
            inline=False
        )

    embed.set_footer(
        text="Foxes • Help"
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================
# STARTUP
# =========================

@bot.event
async def setup_hook():

    bot.add_view(
        TicketView()
    )

    bot.add_view(
        TicketControlView()
    )

    bot.add_view(
        RoleSelectionView()
    )

    bot.add_view(
        GamePanelView()
    )

    guild = GUILD

    bot.tree.clear_commands(
        guild=guild
    )

    bot.tree.copy_global_to(
        guild=guild
    )

    synced = await bot.tree.sync(
        guild=guild
    )

    print(
        f"סונכרנו {len(synced)} פקודות Slash לשרת"
    )

    for command in synced:

        print(
            f"/{command.name}"
        )


# =========================
# READY
# =========================

@bot.event
async def on_ready():

    print("--------------------------------")
    print(
        f"🦊 Foxes מחובר בתור {bot.user}"
    )
    print(
        f"שרת יעד: {GUILD_ID}"
    )
    print("--------------------------------")


# =========================
# RUN
# =========================

TOKEN = os.environ.get(
    "DISCORD_TOKEN"
)

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN לא מוגדר ב-Railway"
    )

bot.run(TOKEN)