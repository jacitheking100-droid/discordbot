import discord
from discord.ext import commands
from discord import app_commands
import os
import sqlite3
import time
import re
import asyncio

# =========================
# SETTINGS
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

SUGGESTION_INPUT_CHANNEL = "💡・הצעות-לשרת"
SUGGESTION_OUTPUT_CHANNEL = "📋・הצעות-שהוצעו"

XP_SHOP_CHANNEL = "🛒・חנות-xp"

# =========================
# XP SHOP
# =========================

XP_SHOP_ITEMS = [
    {
        "name": "🟢 Active Member",
        "role_name": "Active Member",
        "price": 2500
    },
    {
        "name": "🔵 Elite Member",
        "role_name": "Elite Member",
        "price": 5000
    },
    {
        "name": "🟣 Premium",
        "role_name": "Premium",
        "price": 10000
    },
    {
        "name": "🟠 Legend",
        "role_name": "Legend",
        "price": 20000
    },
    {
        "name": "🔴 OG Fox",
        "role_name": "OG Fox",
        "price": 35000
    },
    {
        "name": "👑 Royal Fox",
        "role_name": "Royal Fox",
        "price": 50000
    }
]

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


def remove_xp(user_id, amount):

    ensure_user(user_id)

    cursor.execute(
        """
        UPDATE users
        SET xp = xp - ?
        WHERE user_id = ? AND xp >= ?
        """,
        (
            amount,
            user_id,
            amount
        )
    )

    db.commit()

    return cursor.rowcount > 0


def add_warning(user_id):

    ensure_user(user_id)

    cursor.execute(
        "UPDATE users SET warnings = warnings + 1 WHERE user_id = ?",
        (user_id,)
    )

    db.commit()

    return get_warnings(user_id)


# =========================
# STAFF
# =========================

def is_staff(member):

    if not isinstance(member, discord.Member):
        return False

    return any(
        role.name.upper() in STAFF_ROLES
        for role in member.roles
    )


# =========================
# XP SHOP FUNCTIONS
# =========================

async def get_or_create_shop_role(guild, role_name):

    role = discord.utils.get(
        guild.roles,
        name=role_name
    )

    if role:
        return role

    try:

        role = await guild.create_role(
            name=role_name,
            reason="יצירת רול לחנות XP"
        )

        return role

    except discord.Forbidden:

        return None

    except Exception:

        return None


# =========================
# XP SHOP VIEW
# =========================

class XPShopView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.select(
        placeholder="🛒 בחרו רול לקנייה...",
        custom_id="xp_shop_select",
        options=[
            discord.SelectOption(
                label="Active Member",
                description="2,500 XP",
                emoji="🟢",
                value="2500"
            ),
            discord.SelectOption(
                label="Elite Member",
                description="5,000 XP",
                emoji="🔵",
                value="5000"
            ),
            discord.SelectOption(
                label="Premium",
                description="10,000 XP",
                emoji="🟣",
                value="10000"
            ),
            discord.SelectOption(
                label="Legend",
                description="20,000 XP",
                emoji="🟠",
                value="20000"
            ),
            discord.SelectOption(
                label="OG Fox",
                description="35,000 XP",
                emoji="🔴",
                value="35000"
            ),
            discord.SelectOption(
                label="Royal Fox",
                description="50,000 XP",
                emoji="👑",
                value="50000"
            )
        ]
    )
    async def buy_role(
        self,
        interaction: discord.Interaction,
        select: discord.ui.Select
    ):

        selected_price = int(
            select.values[0]
        )

        item = next(
            (
                item
                for item in XP_SHOP_ITEMS
                if item["price"] == selected_price
            ),
            None
        )

        if item is None:

            await interaction.response.send_message(
                "❌ הרול לא נמצא.",
                ephemeral=True
            )

            return

        user = interaction.user
        guild = interaction.guild

        role = discord.utils.get(
            guild.roles,
            name=item["role_name"]
        )

        if role is None:

            role = await get_or_create_shop_role(
                guild,
                item["role_name"]
            )

        if role is None:

            await interaction.response.send_message(
                "❌ הבוט לא הצליח ליצור את הרול.",
                ephemeral=True
            )

            return

        if role in user.roles:

            await interaction.response.send_message(
                f"❌ כבר יש לכם את הרול **{role.name}**.",
                ephemeral=True
            )

            return

        current_xp = get_xp(
            user.id
        )

        if current_xp < item["price"]:

            missing = item["price"] - current_xp

            await interaction.response.send_message(
                f"❌ **אין לכם מספיק XP.**\n\n"
                f"יש לכם: **{current_xp:,} XP**\n"
                f"מחיר: **{item['price']:,} XP**\n"
                f"חסר לכם: **{missing:,} XP**",
                ephemeral=True
            )

            return

        # בדיקה שהבוט יכול לתת את הרול
        if role >= guild.me.top_role:

            await interaction.response.send_message(
                "❌ הבוט לא יכול לתת את הרול הזה. "
                "צריך להעביר את הרול מתחת לרול של הבוט.",
                ephemeral=True
            )

            return

        # הורדת XP
        success = remove_xp(
            user.id,
            item["price"]
        )

        if not success:

            await interaction.response.send_message(
                "❌ אין לכם מספיק XP.",
                ephemeral=True
            )

            return

        try:

            await user.add_roles(
                role,
                reason="רכישה מחנות XP"
            )

        except discord.Forbidden:

            # במקרה שהרול לא ניתן, מחזירים את ה-XP
            add_xp(
                user.id,
                item["price"]
            )

            await interaction.response.send_message(
                "❌ הבוט לא הצליח לתת את הרול.",
                ephemeral=True
            )

            return

        except Exception:

            add_xp(
                user.id,
                item["price"]
            )

            await interaction.response.send_message(
                "❌ אירעה שגיאה במהלך הקנייה.",
                ephemeral=True
            )

            return

        remaining_xp = get_xp(
            user.id
        )

        await interaction.response.send_message(
            f"✅ **הרכישה הצליחה!**\n\n"
            f"קיבלתם את הרול {role.mention}\n"
            f"💰 שולם: **{item['price']:,} XP**\n"
            f"📊 נשאר לכם: **{remaining_xp:,} XP**",
            ephemeral=True
        )


# =========================
# XP SHOP EMBED
# =========================

def build_xp_shop_embed():

    embed = discord.Embed(
        title="🛒 חנות XP — FOXES",
        description=(
            "ברוכים הבאים לחנות ה־XP של **Foxes**!\n\n"
            "כאן תוכלו להשתמש ב־XP שצברתם כדי לקנות רולים מיוחדים.\n\n"
            "👇 **בחרו למטה את הרול שתרצו לקנות.**"
        ),
        color=discord.Color.blue()
    )

    for item in XP_SHOP_ITEMS:

        embed.add_field(
            name=item["name"],
            value=f"💰 **{item['price']:,} XP**",
            inline=True
        )

    embed.add_field(
        name="📌 איך זה עובד?",
        value=(
            "1. בוחרים רול מהתפריט\n"
            "2. הבוט בודק את ה־XP שלכם\n"
            "3. ה־XP יורד אוטומטית\n"
            "4. הרול מתקבל מיד"
        ),
        inline=False
    )

    embed.set_footer(
        text="Foxes • חנות XP"
    )

    return embed


# =========================
# SUGGESTION DATABASE
# =========================

def create_suggestion(user_id, content):

    cursor.execute(
        """
        INSERT INTO suggestions
        (user_id, content, message_id, channel_id, created_at)
        VALUES (?, ?, NULL, NULL, ?)
        """,
        (
            user_id,
            content,
            int(time.time())
        )
    )

    db.commit()

    return cursor.lastrowid


def set_suggestion_message(
    suggestion_id,
    message_id,
    channel_id
):

    cursor.execute(
        """
        UPDATE suggestions
        SET message_id = ?, channel_id = ?
        WHERE id = ?
        """,
        (
            message_id,
            channel_id,
            suggestion_id
        )
    )

    db.commit()


def get_suggestion(suggestion_id):

    cursor.execute(
        """
        SELECT id, user_id, content, message_id, channel_id
        FROM suggestions
        WHERE id = ?
        """,
        (suggestion_id,)
    )

    return cursor.fetchone()


def get_vote_counts(suggestion_id):

    cursor.execute(
        """
        SELECT
            SUM(CASE WHEN vote = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN vote = -1 THEN 1 ELSE 0 END)
        FROM suggestion_votes
        WHERE suggestion_id = ?
        """,
        (suggestion_id,)
    )

    result = cursor.fetchone()

    likes = result[0] or 0
    dislikes = result[1] or 0

    return likes, dislikes


def get_user_vote(
    suggestion_id,
    user_id
):

    cursor.execute(
        """
        SELECT vote
        FROM suggestion_votes
        WHERE suggestion_id = ? AND user_id = ?
        """,
        (
            suggestion_id,
            user_id
        )
    )

    result = cursor.fetchone()

    return result[0] if result else None


def set_vote(
    suggestion_id,
    user_id,
    vote
):

    current_vote = get_user_vote(
        suggestion_id,
        user_id
    )

    if current_vote == vote:

        cursor.execute(
            """
            DELETE FROM suggestion_votes
            WHERE suggestion_id = ? AND user_id = ?
            """,
            (
                suggestion_id,
                user_id
            )
        )

    else:

        cursor.execute(
            """
            INSERT INTO suggestion_votes
            (suggestion_id, user_id, vote)
            VALUES (?, ?, ?)
            ON CONFLICT(suggestion_id, user_id)
            DO UPDATE SET vote = excluded.vote
            """,
            (
                suggestion_id,
                user_id,
                vote
            )
        )

    db.commit()


# =========================
# SUGGESTION EMBED
# =========================

async def build_suggestion_embed(
    suggestion_id,
    guild
):

    suggestion = get_suggestion(
        suggestion_id
    )

    if not suggestion:
        return None

    (
        _,
        user_id,
        content,
        _,
        _
    ) = suggestion

    member = guild.get_member(user_id)

    if member:

        author_name = member.display_name
        author_mention = member.mention
        avatar_url = member.display_avatar.url

    else:

        author_name = "משתמש"
        author_mention = f"<@{user_id}>"
        avatar_url = None

    likes, dislikes = get_vote_counts(
        suggestion_id
    )

    embed = discord.Embed(
        title="💡 הצעה חדשה",
        description=content,
        color=discord.Color.blue()
    )

    embed.add_field(
        name="👤 הוצע על ידי",
        value=(
            f"{author_mention}\n"
            f"`{author_name}`"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 הצבעות",
        value=(
            f"👍 **{likes}** לייקים\n"
            f"👎 **{dislikes}** דיסלייקים"
        ),
        inline=False
    )

    embed.set_footer(
        text=f"Foxes • הצעה #{suggestion_id}"
    )

    if avatar_url:

        embed.set_thumbnail(
            url=avatar_url
        )

    return embed


# =========================
# SUGGESTION VOTE VIEW
# =========================

class SuggestionVoteView(
    discord.ui.View
):

    def __init__(
        self,
        suggestion_id
    ):

        super().__init__(
            timeout=None
        )

        self.suggestion_id = suggestion_id

        self.like_button.custom_id = (
            f"suggestion_like_{suggestion_id}"
        )

        self.dislike_button.custom_id = (
            f"suggestion_dislike_{suggestion_id}"
        )

    @discord.ui.button(
        label="לייק",
        emoji="👍",
        style=discord.ButtonStyle.success
    )
    async def like_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        suggestion = get_suggestion(
            self.suggestion_id
        )

        if not suggestion:

            await interaction.response.send_message(
                "❌ ההצעה לא נמצאה.",
                ephemeral=True
            )

            return

        set_vote(
            self.suggestion_id,
            interaction.user.id,
            1
        )

        embed = await build_suggestion_embed(
            self.suggestion_id,
            interaction.guild
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    @discord.ui.button(
        label="דיסלייק",
        emoji="👎",
        style=discord.ButtonStyle.danger
    )
    async def dislike_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        suggestion = get_suggestion(
            self.suggestion_id
        )

        if not suggestion:

            await interaction.response.send_message(
                "❌ ההצעה לא נמצאה.",
                ephemeral=True
            )

            return

        set_vote(
            self.suggestion_id,
            interaction.user.id,
            -1
        )

        embed = await build_suggestion_embed(
            self.suggestion_id,
            interaction.guild
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )


# =========================
# SUGGESTION MODAL
# =========================

class SuggestionModal(
    discord.ui.Modal
):

    def __init__(self):

        super().__init__(
            title="💡 הצעה לשרת"
        )

        self.suggestion = discord.ui.TextInput(
            label="מה ההצעה שלך?",
            placeholder="כתוב כאן את ההצעה שלך לשרת...",
            style=discord.TextStyle.paragraph,
            min_length=3,
            max_length=1000,
            required=True
        )

        self.add_item(
            self.suggestion
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild

        channel = discord.utils.get(
            guild.text_channels,
            name=SUGGESTION_OUTPUT_CHANNEL
        )

        if channel is None:

            await interaction.response.send_message(
                f"❌ לא נמצא החדר `{SUGGESTION_OUTPUT_CHANNEL}`.",
                ephemeral=True
            )

            return

        suggestion_id = create_suggestion(
            interaction.user.id,
            self.suggestion.value
        )

        embed = await build_suggestion_embed(
            suggestion_id,
            guild
        )

        message = await channel.send(
            embed=embed,
            view=SuggestionVoteView(
                suggestion_id
            )
        )

        set_suggestion_message(
            suggestion_id,
            message.id,
            channel.id
        )

        await interaction.response.send_message(
            "✅ ההצעה שלך נשלחה בהצלחה!",
            ephemeral=True
        )


# =========================
# SUGGESTION PANEL
# =========================

class SuggestionPanelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="הצעה לשרת",
        emoji="💡",
        style=discord.ButtonStyle.primary,
        custom_id="open_suggestion"
    )
    async def open_suggestion(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            SuggestionModal()
        )


# =========================
# TICKET VIEWS
# =========================

class TicketView(
    discord.ui.View
):

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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "בחר את סוג הפנייה שלך:",
            view=TicketTypeView(),
            ephemeral=True
        )


class TicketTypeView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=60
        )

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
        interaction: discord.Interaction,
        select: discord.ui.Select
    ):

        guild = interaction.guild
        user = interaction.user

        existing = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{user.id}"
        )

        if existing:

            await interaction.response.send_message(
                f"❌ כבר יש לך טיקט פתוח: {existing.mention}",
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
                "צוות השרת יטפל בפנייה בהקדם האפשרי."
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
            f"✅ הטיקט נפתח: {channel.mention}",
            ephemeral=True
        )


class TicketControlView(
    discord.ui.View
):

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
        interaction: discord.Interaction,
        button: discord.ui.Button
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
# SLASH COMMANDS
# =========================

@bot.tree.command(
    name="xp",
    description="בדיקת כמות ה-XP שלך"
)
async def xp_command(
    interaction: discord.Interaction
):

    xp = get_xp(
        interaction.user.id
    )

    embed = discord.Embed(
        title="📊 ה-XP שלך",
        description=f"יש לך כרגע **{xp:,} XP**.",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================
# XP SHOP COMMAND
# =========================

@bot.tree.command(
    name="xpshop",
    description="שליחת חנות ה-XP"
)
async def xpshop_command(
    interaction: discord.Interaction
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק צוות יכול לשלוח את חנות ה-XP.",
            ephemeral=True
        )

        return

    embed = build_xp_shop_embed()

    # מנסים לשלוח לחדר החנות
    channel = discord.utils.get(
        interaction.guild.text_channels,
        name=XP_SHOP_CHANNEL
    )

    if channel is None:

        try:

            channel = await interaction.guild.create_text_channel(
                XP_SHOP_CHANNEL,
                reason="יצירת חדר לחנות XP"
            )

        except:

            await interaction.response.send_message(
                "❌ לא הצלחתי ליצור את חדר חנות ה-XP.",
                ephemeral=True
            )

            return

    await channel.send(
        embed=embed,
        view=XPShopView()
    )

    await interaction.response.send_message(
        f"✅ חנות ה-XP נשלחה ל־{channel.mention}.",
        ephemeral=True
    )


# =========================
# WARNINGS
# =========================

@bot.tree.command(
    name="warnings",
    description="בדיקת מספר האזהרות שלך"
)
async def warnings_command(
    interaction: discord.Interaction
):

    warnings = get_warnings(
        interaction.user.id
    )

    embed = discord.Embed(
        title="⚠️ האזהרות שלך",
        description=f"יש לך כרגע **{warnings} אזהרות**.",
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================
# WARN
# =========================

@bot.tree.command(
    name="warn",
    description="מתן אזהרה למשתמש"
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

    warnings = add_warning(
        member.id
    )

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


# =========================
# TICKET COMMAND
# =========================

@bot.tree.command(
    name="ticket",
    description="שליחת פאנל פתיחת טיקט"
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
            "לחצו על **פתיחת טיקט** ובחרו את סוג הפנייה.\n\n"
            "🐛 **באג**\n"
            "דיווח על תקלה.\n\n"
            "👮 **התקבלות לצוות**\n"
            "בקשה להצטרף לצוות.\n\n"
            "🚨 **דיווח על משתמש**\n"
            "דיווח על הפרת חוקי השרת."
        ),
        color=discord.Color.blue()
    )

    embed.set_footer(
        text="מערכת הטיקטים • Foxy bot"
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


# =========================
# SUGGESTIONS COMMAND
# =========================

@bot.tree.command(
    name="suggestions",
    description="שליחת פאנל הצעות לשרת"
)
async def suggestions_command(
    interaction: discord.Interaction
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק צוות יכול לשלוח את פאנל ההצעות.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="💡 הצעות לשרת",
        description=(
            "יש לכם רעיון שיכול לשפר את **Foxes**?\n\n"
            "לחצו על הכפתור למטה וכתבו את ההצעה שלכם.\n\n"
            "ההצעה תישלח לחדר ההצעות, "
            "ושאר חברי השרת יוכלו להצביע עליה.\n\n"
            "👍 **לייק** — בעד ההצעה\n"
            "👎 **דיסלייק** — נגד ההצעה"
        ),
        color=discord.Color.blue()
    )

    embed.set_footer(
        text="Foxes • מערכת ההצעות"
    )

    await interaction.response.send_message(
        embed=embed,
        view=SuggestionPanelView()
    )


# =========================
# XP + ANTI LINK SYSTEM
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    user_id = message.author.id
    now = time.time()

    # XP
    if (
        user_id not in last_xp
        or now - last_xp[user_id] >= XP_COOLDOWN
    ):

        add_xp(
            user_id,
            XP_PER_MESSAGE
        )

        last_xp[user_id] = now

    # =========================
    # ANTI LINK
    # =========================

    link_pattern = r"(https?://\S+|www\.\S+)"

    # צוות יכול לשלוח קישורים
    if (
        re.search(
            link_pattern,
            message.content,
            re.IGNORECASE
        )
        and not is_staff(message.author)
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
                f"""⚠️ **אזהרה**

הודעה שלך נמחקה מכיוון שהיא הכילה קישור.

מספר האזהרות שלך: **{warnings}**"""
            )

        except:
            pass

        return

    await bot.process_commands(
        message
    )


# =========================
# WELCOME SYSTEM
# =========================

@bot.event
async def on_member_join(
    member
):

    channel = discord.utils.find(
        lambda c: c.name.lower() in [
            "welcome",
            "👋・ברוכים-הבאים",
            "ברוכים-באים"
        ],
        member.guild.text_channels
    )

    if channel is None:
        return

    embed = discord.Embed(
        title="🦊 ברוכים הבאים ל־Foxes!",
        description=(
            f"👋 ברוך הבא, {member.mention}!\n\n"
            f"אנחנו שמחים שהצטרפת ל־**Foxes**.\n\n"
            f"👥 אתה החבר ה־**{member.guild.member_count}** בשרת!\n\n"
            "📜 אל תשכח לעבור על חוקי השרת\n"
            "🦊 תהנה ותכיר את הקהילה!"
        ),
        color=discord.Color.blue()
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.set_footer(
        text=f"ברוך הבא, {member.name} • Foxes"
    )

    await channel.send(
        embed=embed
    )


# =========================
# STARTUP
# =========================

@bot.event
async def setup_hook():

    # טוען את מערכת הטיקטים
    bot.add_view(
        TicketView()
    )

    bot.add_view(
        TicketControlView()
    )

    # טוען את מערכת ההצעות
    bot.add_view(
        SuggestionPanelView()
    )

    # טוען את חנות ה-XP
    bot.add_view(
        XPShopView()
    )

    # טוען מחדש את כפתורי ההצבעות
    cursor.execute(
        """
        SELECT id
        FROM suggestions
        WHERE message_id IS NOT NULL
        """
    )

    suggestions = cursor.fetchall()

    for row in suggestions:

        bot.add_view(
            SuggestionVoteView(
                row[0]
            )
        )

    # מוחק פקודות ישנות מהשרת
    bot.tree.clear_commands(
        guild=GUILD
    )

    # מוסיף את הפקודות הנוכחיות לשרת
    bot.tree.copy_global_to(
        guild=GUILD
    )

    # סנכרון ישיר לשרת
    synced = await bot.tree.sync(
        guild=GUILD
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
        f"הבוט מחובר בתור {bot.user}"
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