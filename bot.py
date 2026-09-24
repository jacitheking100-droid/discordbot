import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import time
import asyncio

# =========================================================
# SETTINGS
# =========================================================

XP_PER_MESSAGE = 50
XP_COOLDOWN = 60

GUILD_ID = 1552344386526908488
GUILD = discord.Object(id=GUILD_ID)

WELCOME_CHANNEL_NAME = "ברוכים-הבאים-👋"
RULES_CHANNEL_NAME = "📜・חוקים"

SUGGESTIONS_PANEL_CHANNEL_NAME = "💡・הצעות-לשרת"
SUGGESTIONS_POSTED_CHANNEL_NAME = "📋・הצעות-שהוצעו"

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

# =========================================================
# DAILY
# =========================================================

DAILY_REWARDS = {
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 50,
    6: 60,
    7: 100
}

DAILY_COOLDOWN = 86400
DAILY_RESET_TIME = 172800

# =========================================================
# SHOP
# =========================================================

SHOP_ROLE_PRICES = {
    "Active Member": 2500,
    "Elite Member": 5000,
    "Premium": 7000,
    "Legend": 13000,
    "OP Fox": 20000,
    "Royal Fox": 50000
}

# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(
    "bot_data.db",
    check_same_thread=False
)

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

# =========================================================
# BOT
# =========================================================

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =========================================================
# XP FUNCTIONS
# =========================================================

def ensure_user(user_id):
    cursor.execute(
        """
        INSERT OR IGNORE INTO users
        (user_id, xp, warnings)
        VALUES (?, 0, 0)
        """,
        (user_id,)
    )

    db.commit()


def get_xp(user_id):
    ensure_user(user_id)

    cursor.execute(
        """
        SELECT xp
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    result = cursor.fetchone()

    return result[0] if result else 0


def add_xp(user_id, amount):
    ensure_user(user_id)

    cursor.execute(
        """
        UPDATE users
        SET xp = xp + ?
        WHERE user_id = ?
        """,
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


# =========================================================
# WARNINGS
# =========================================================

def get_warnings(user_id):
    ensure_user(user_id)

    cursor.execute(
        """
        SELECT warnings
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    result = cursor.fetchone()

    return result[0] if result else 0


def add_warning(user_id):
    ensure_user(user_id)

    cursor.execute(
        """
        UPDATE users
        SET warnings = warnings + 1
        WHERE user_id = ?
        """,
        (user_id,)
    )

    db.commit()


# =========================================================
# STAFF
# =========================================================

def is_staff(member):
    if not isinstance(member, discord.Member):
        return False

    if member.guild_permissions.administrator:
        return True

    return any(
        role.name.upper() in STAFF_ROLES
        for role in member.roles
    )


# =========================================================
# SHOP DATABASE
# =========================================================

def get_shop_items():
    cursor.execute(
        """
        SELECT role_id, price
        FROM shop_items
        ORDER BY price ASC
        """
    )

    return cursor.fetchall()


def add_shop_item(role_id, price):
    cursor.execute(
        """
        INSERT OR REPLACE INTO shop_items
        (role_id, price)
        VALUES (?, ?)
        """,
        (role_id, price)
    )

    db.commit()


def get_shop_price(role_id):
    cursor.execute(
        """
        SELECT price
        FROM shop_items
        WHERE role_id = ?
        """,
        (role_id,)
    )

    result = cursor.fetchone()

    return result[0] if result else None


def remove_shop_item(role_id):
    cursor.execute(
        """
        DELETE FROM shop_items
        WHERE role_id = ?
        """,
        (role_id,)
    )

    db.commit()


def setup_default_shop(guild):
    for role_name, price in SHOP_ROLE_PRICES.items():

        role = discord.utils.get(
            guild.roles,
            name=role_name
        )

        if role:
            add_shop_item(
                role.id,
                price
            )


# =========================================================
# SHOP EMBED
# =========================================================

def create_shop_embed(guild, user_id):

    xp = get_xp(user_id)

    embed = discord.Embed(
        title="🛒 חנות ה־XP של Foxes",
        description=(
            f"📊 **ה־XP שלך:** `{xp:,} XP`\n\n"
            "בחר רול מהרשימה למטה כדי לקנות אותו."
        ),
        color=discord.Color.orange()
    )

    items = get_shop_items()

    if not items:

        embed.add_field(
            name="החנות ריקה",
            value="לא נמצאו רולים בחנות.",
            inline=False
        )

    else:

        for role_id, price in items:

            role = guild.get_role(role_id)

            if not role:
                continue

            embed.add_field(
                name=f"🎖️ {role.name}",
                value=f"💰 **{price:,} XP**",
                inline=False
            )

    return embed


# =========================================================
# SHOP SELECT
# =========================================================

class ShopSelect(discord.ui.Select):

    def __init__(self, guild):

        options = []

        for role_id, price in get_shop_items():

            role = guild.get_role(role_id)

            if not role:
                continue

            options.append(
                discord.SelectOption(
                    label=role.name[:100],
                    description=f"{price:,} XP",
                    value=str(role.id)
                )
            )

        if not options:

            options = [
                discord.SelectOption(
                    label="החנות ריקה",
                    description="אין כרגע רולים לקנייה",
                    value="none"
                )
            ]

        super().__init__(
            placeholder="🛒 בחר רול לקנייה",
            options=options
        )

    async def callback(self, interaction):

        if self.values[0] == "none":

            await interaction.response.send_message(
                "❌ החנות ריקה כרגע.",
                ephemeral=True
            )

            return

        role_id = int(self.values[0])

        role = interaction.guild.get_role(role_id)

        if not role:

            await interaction.response.send_message(
                "❌ הרול לא נמצא.",
                ephemeral=True
            )

            return

        price = get_shop_price(role.id)

        if price is None:

            await interaction.response.send_message(
                "❌ הרול לא נמצא בחנות.",
                ephemeral=True
            )

            return

        if role in interaction.user.roles:

            await interaction.response.send_message(
                f"❌ כבר יש לך את הרול {role.mention}.",
                ephemeral=True
            )

            return

        xp = get_xp(
            interaction.user.id
        )

        if xp < price:

            missing = price - xp

            await interaction.response.send_message(
                f"❌ אין לך מספיק XP.\n\n"
                f"🎖️ רול: **{role.name}**\n"
                f"💰 מחיר: **{price:,} XP**\n"
                f"📊 יש לך: **{xp:,} XP**\n"
                f"❗ חסרים לך: **{missing:,} XP**",
                ephemeral=True
            )

            return

        if role >= interaction.guild.me.top_role:

            await interaction.response.send_message(
                "❌ הבוט לא יכול לתת את הרול הזה.\n"
                "תעלה את הרול של הבוט מעל הרול הזה.",
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

        db.commit()

        if cursor.rowcount == 0:

            await interaction.response.send_message(
                "❌ ה־XP השתנה בזמן הרכישה. נסה שוב.",
                ephemeral=True
            )

            return

        try:

            await interaction.user.add_roles(
                role,
                reason="רכישה מחנות XP"
            )

        except discord.Forbidden:

            add_xp(
                interaction.user.id,
                price
            )

            await interaction.response.send_message(
                "❌ הבוט לא הצליח לתת את הרול.\n"
                "ה־XP שלך הוחזר.",
                ephemeral=True
            )

            return

        except discord.HTTPException:

            add_xp(
                interaction.user.id,
                price
            )

            await interaction.response.send_message(
                "❌ הייתה שגיאה במתן הרול.\n"
                "ה־XP שלך הוחזר.",
                ephemeral=True
            )

            return

        remaining = get_xp(
            interaction.user.id
        )

        await interaction.response.send_message(
            f"🎉 **הרכישה הצליחה!**\n\n"
            f"🎖️ קיבלת: {role.mention}\n"
            f"💰 שילמת: **{price:,} XP**\n"
            f"📊 נשאר לך: **{remaining:,} XP**",
            ephemeral=True
        )


class ShopView(discord.ui.View):

    def __init__(self, guild):
        super().__init__(timeout=None)
        self.add_item(
            ShopSelect(guild)
        )


# =========================================================
# /SHOP
# =========================================================

@bot.tree.command(
    name="shop",
    description="פתיחת חנות ה-XP"
)
async def shop_command(interaction):

    setup_default_shop(
        interaction.guild
    )

    await interaction.response.send_message(
        embed=create_shop_embed(
            interaction.guild,
            interaction.user.id
        ),
        view=ShopView(
            interaction.guild
        )
    )


# =========================================================
# /XP
# =========================================================

@bot.tree.command(
    name="xp",
    description="בדיקת ה-XP שלך"
)
async def xp_command(interaction):

    xp = get_xp(
        interaction.user.id
    )

    await interaction.response.send_message(
        f"📊 יש לך **{xp:,} XP**.",
        ephemeral=True
    )


# =========================================================
# /ADDXP
# =========================================================

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
            "❌ רק צוות יכול להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    add_xp(
        member.id,
        amount
    )

    new_xp = get_xp(
        member.id
    )

    await interaction.response.send_message(
        f"✅ נוספו **{amount:,} XP** ל־{member.mention}.\n\n"
        f"📊 ה־XP החדש שלו: **{new_xp:,} XP**",
        ephemeral=True
    )


# =========================================================
# /REMOVEXP
# =========================================================

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
            "❌ רק צוות יכול להשתמש בפקודה הזאת.",
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

    await interaction.response.send_message(
        f"✅ הורדו **{amount:,} XP** מ־{member.mention}.\n\n"
        f"📊 לפני: **{before:,} XP**\n"
        f"📊 אחרי: **{after:,} XP**",
        ephemeral=True
    )


# =========================================================
# /DAILY
# =========================================================

@bot.tree.command(
    name="daily",
    description="קבלת פרס יומי"
)
async def daily_command(interaction):

    user_id = interaction.user.id
    now = int(time.time())

    cursor.execute(
        """
        SELECT streak, last_claim
        FROM daily_users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    result = cursor.fetchone()

    if result:

        streak, last_claim = result

    else:

        streak = 0
        last_claim = 0

    if last_claim:

        elapsed = now - last_claim

        if elapsed < DAILY_COOLDOWN:

            remaining = DAILY_COOLDOWN - elapsed

            hours = remaining // 3600
            minutes = (remaining % 3600) // 60

            await interaction.response.send_message(
                f"⏳ כבר לקחת את ה־Daily שלך.\n\n"
                f"נסה שוב בעוד **{hours} שעות ו־{minutes} דקות**.",
                ephemeral=True
            )

            return

        if elapsed > DAILY_RESET_TIME:
            streak = 0

    streak += 1

    if streak > 7:
        streak = 1

    reward = DAILY_REWARDS[streak]

    add_xp(
        user_id,
        reward
    )

    cursor.execute(
        """
        INSERT OR REPLACE INTO daily_users
        (user_id, streak, last_claim)
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            streak,
            now
        )
    )

    db.commit()

    current_xp = get_xp(
        user_id
    )

    embed = discord.Embed(
        title="🎁 Daily",
        description=(
            f"🎉 **קיבלת את הפרס היומי!**\n\n"
            f"🔥 רצף: **{streak}/7**\n"
            f"💰 פרס: **{reward} XP**\n"
            f"📊 ה־XP שלך עכשיו: **{current_xp:,} XP**"
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="פרסי 7 הימים",
        value=(
            "🟢 יום 1 — **10 XP**\n"
            "🟢 יום 2 — **20 XP**\n"
            "🟢 יום 3 — **30 XP**\n"
            "🟢 יום 4 — **40 XP**\n"
            "🟢 יום 5 — **50 XP**\n"
            "🟢 יום 6 — **60 XP**\n"
            "🟢 יום 7 — **100 XP**"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /SAY
# =========================================================

@bot.tree.command(
    name="say",
    description="הבוט שולח הודעה במקומך"
)
@app_commands.describe(
    message="מה שהבוט יגיד"
)
async def say_command(
    interaction,
    message: str
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק צוות יכול להשתמש בפקודה הזאת.",
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
# /WARN
# =========================================================

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
    reason: str = "לא צוינה סיבה"
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק צוות יכול להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    if member.bot:

        await interaction.response.send_message(
            "❌ אי אפשר לתת אזהרה לבוט.",
            ephemeral=True
        )

        return

    add_warning(
        member.id
    )

    warnings = get_warnings(
        member.id
    )

    embed = discord.Embed(
        title="⚠️ אזהרה",
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
        name="כמות אזהרות",
        value=str(warnings),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )

    try:

        await member.send(
            f"⚠️ קיבלת אזהרה בשרת **{interaction.guild.name}**.\n"
            f"סיבה: **{reason}**\n"
            f"סה״כ אזהרות: **{warnings}**"
        )

    except discord.Forbidden:
        pass


# =========================================================
# /WARNINGS
# =========================================================

@bot.tree.command(
    name="warnings",
    description="בדיקת אזהרות"
)
@app_commands.describe(
    member="המשתמש"
)
async def warnings_command(
    interaction,
    member: discord.Member = None
):

    if member is None:
        member = interaction.user

    warnings = get_warnings(
        member.id
    )

    await interaction.response.send_message(
        f"⚠️ ל־{member.mention} יש **{warnings} אזהרות**.",
        ephemeral=True
    )


# =========================================================
# /CLEARWARNINGS
# =========================================================

@bot.tree.command(
    name="clearwarnings",
    description="איפוס אזהרות למשתמש"
)
@app_commands.describe(
    member="המשתמש"
)
async def clearwarnings_command(
    interaction,
    member: discord.Member
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק צוות יכול להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    cursor.execute(
        """
        UPDATE users
        SET warnings = 0
        WHERE user_id = ?
        """,
        (member.id,)
    )

    db.commit()

    await interaction.response.send_message(
        f"✅ האזהרות של {member.mention} אופסו.",
        ephemeral=True
    )


# =========================================================
# SUGGESTIONS
# =========================================================

class SuggestionModal(
    discord.ui.Modal,
    title="💡 הצעה לשרת"
):

    suggestion = discord.ui.TextInput(
        label="מה ההצעה שלך?",
        placeholder="כתוב כאן את ההצעה...",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction):

        channel = discord.utils.get(
            interaction.guild.text_channels,
            name=SUGGESTIONS_POSTED_CHANNEL_NAME
        )

        if not channel:

            await interaction.response.send_message(
                "❌ ערוץ ההצעות לא נמצא.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title="💡 הצעה חדשה",
            description=str(self.suggestion),
            color=discord.Color.blurple()
        )

        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        message = await channel.send(
            embed=embed
        )

        await message.add_reaction("👍")
        await message.add_reaction("👎")

        await interaction.response.send_message(
            "✅ ההצעה שלך נשלחה בהצלחה!",
            ephemeral=True
        )


class SuggestionPanelView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="שליחת הצעה",
        emoji="💡",
        style=discord.ButtonStyle.primary,
        custom_id="foxes_suggestion_button"
    )
    async def suggestion_button(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            SuggestionModal()
        )


@bot.tree.command(
    name="suggestionpanel",
    description="שליחת פאנל הצעות"
)
async def suggestionpanel_command(interaction):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק צוות יכול להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="💡 הצעות לשרת",
        description=(
            "יש לכם רעיון לשיפור השרת?\n\n"
            "לחצו על הכפתור למטה ושלחו את ההצעה שלכם."
        ),
        color=discord.Color.blurple()
    )

    await interaction.channel.send(
        embed=embed,
        view=SuggestionPanelView()
    )

    await interaction.response.send_message(
        "✅ פאנל ההצעות נשלח.",
        ephemeral=True
    )


# =========================================================
# ROLE PANEL
# =========================================================

class RoleSelectionView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="עדכונים",
        emoji="🔔",
        style=discord.ButtonStyle.primary,
        custom_id="foxes_updates_role"
    )
    async def updates_button(
        self,
        interaction,
        button
    ):

        role = discord.utils.get(
            interaction.guild.roles,
            name=UPDATES_ROLE_NAME
        )

        if not role:

            await interaction.response.send_message(
                "❌ הרול לא נמצא.",
                ephemeral=True
            )

            return

        if role in interaction.user.roles:

            await interaction.user.remove_roles(role)

            await interaction.response.send_message(
                "🔕 הורדתי לך את רול העדכונים.",
                ephemeral=True
            )

        else:

            await interaction.user.add_roles(role)

            await interaction.response.send_message(
                "🔔 קיבלת את רול העדכונים.",
                ephemeral=True
            )

    @discord.ui.button(
        label="הגרלות",
        emoji="🎉",
        style=discord.ButtonStyle.success,
        custom_id="foxes_giveaways_role"
    )
    async def giveaways_button(
        self,
        interaction,
        button
    ):

        role = discord.utils.get(
            interaction.guild.roles,
            name=GIVEAWAYS_ROLE_NAME
        )

        if not role:

            await interaction.response.send_message(
                "❌ הרול לא נמצא.",
                ephemeral=True
            )

            return

        if role in interaction.user.roles:

            await interaction.user.remove_roles(role)

            await interaction.response.send_message(
                "🔕 הורדתי לך את רול ההגרלות.",
                ephemeral=True
            )

        else:

            await interaction.user.add_roles(role)

            await interaction.response.send_message(
                "🎉 קיבלת את רול ההגרלות.",
                ephemeral=True
            )


# =========================================================
# TICKETS
# =========================================================

class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="פתיחת טיקט",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="foxes_open_ticket"
    )
    async def open_ticket(
        self,
        interaction,
        button
    ):

        guild = interaction.guild

        existing = discord.utils.find(
            lambda c: c.name == f"ticket-{interaction.user.id}",
            guild.text_channels
        )

        if existing:

            await interaction.response.send_message(
                f"❌ כבר יש לך טיקט: {existing.mention}",
                ephemeral=True
            )

            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),

            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True
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
            name=f"ticket-{interaction.user.id}",
            overwrites=overwrites,
            reason="פתיחת טיקט"
        )

        embed = discord.Embed(
            title="🎫 טיקט",
            description=(
                f"שלום {interaction.user.mention}!\n\n"
                "צוות Foxes יטפל בבקשה שלך בהקדם.\n"
                "כדי לסגור את הטיקט לחץ על הכפתור."
            ),
            color=discord.Color.blurple()
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
        super().__init__(timeout=None)

    @discord.ui.button(
        label="סגירת טיקט",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="foxes_close_ticket"
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

        await interaction.channel.delete(
            reason="סגירת טיקט"
        )


# =========================================================
# WELCOME
# =========================================================

@bot.event
async def on_member_join(member):

    channel = discord.utils.get(
        member.guild.text_channels,
        name=WELCOME_CHANNEL_NAME
    )

    if not channel:
        return

    embed = discord.Embed(
        title="🦊 ברוכים הבאים ל־Foxes!",
        description=(
            f"שלום {member.mention}!\n\n"
            "ברוך הבא לשרת **Foxes**.\n"
            f"אתה החבר ה־**{member.guild.member_count}** שלנו!"
        ),
        color=discord.Color.orange()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.set_footer(
        text="Foxes • הקהילה שלנו"
    )

    await channel.send(
        embed=embed
    )


# =========================================================
# MESSAGE XP + AUTO GREETINGS
# =========================================================

message_cooldowns = {}


@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild is None:
        return

    content = message.content.strip().lower()

    # =====================================================
    # AUTO GREETINGS
    # =====================================================

    if "בוקר טוב" in content:

        await message.channel.send(
            f"🦊 בוקר טוב {message.author.mention}!\n"
            "מאחל לך יום מעולה, מלא באנרגיות ובהצלחות! ☀️"
        )

    elif "צהריים טובים" in content:

        await message.channel.send(
            f"🦊 צהריים טובים {message.author.mention}!\n"
            "שיהיה לך המשך יום מדהים ומהנה! ☀️"
        )

    elif "ערב טוב" in content:

        await message.channel.send(
            f"🦊 ערב טוב {message.author.mention}!\n"
            "שיהיה לך ערב רגוע, כיפי ומוצלח! 🌇"
        )

    elif "לילה טוב" in content:

        await message.channel.send(
            f"🦊 לילה טוב {message.author.mention}!\n"
            "שינה טובה וחלומות נעימים! 🌙"
        )

    # =====================================================
    # XP FROM MESSAGES
    # =====================================================

    now = time.time()

    user_id = message.author.id

    last_message = message_cooldowns.get(
        user_id,
        0
    )

    if now - last_message >= XP_COOLDOWN:

        add_xp(
            user_id,
            XP_PER_MESSAGE
        )

        message_cooldowns[user_id] = now

    await bot.process_commands(
        message
    )


# =========================================================
# SETUP HOOK
# =========================================================

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
        SuggestionPanelView()
    )

    bot.tree.clear_commands(
        guild=GUILD
    )

    bot.tree.copy_global_to(
        guild=GUILD
    )

    synced = await bot.tree.sync(
        guild=GUILD
    )

    print(
        f"סונכרנו {len(synced)} פקודות Slash לשרת"
    )

    for command in synced:
        print(f"/{command.name}")


# =========================================================
# ON READY
# =========================================================

@bot.event
async def on_ready():

    guild = bot.get_guild(
        GUILD_ID
    )

    if guild:

        setup_default_shop(
            guild
        )

        print(
            "🛒 החנות נטענה אוטומטית."
        )

    print("--------------------------------")
    print(
        f"🦊 Foxes מחובר בתור {bot.user}"
    )
    print(
        f"שרת יעד: {GUILD_ID}"
    )
    print("--------------------------------")


# =========================================================
# RUN BOT
# =========================================================

TOKEN = os.getenv(
    "DISCORD_TOKEN"
)

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN לא נמצא ב-Environment Variables"
    )

bot.run(TOKEN)