import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import asyncio
import time
import os
from typing import Optional


# =========================================================
# CONFIG
# =========================================================

GUILD_ID = 1552344386526908488
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

XP_PER_MESSAGE = 50
XP_COOLDOWN = 60

# Tickets
TICKET_CATEGORY_NAME = "🎫・טיקטים"

# Boost
BOOST_CHANNEL_NAME = "boost"

# Suggestions
SUGGESTION_PANEL_CHANNEL_NAME = "הצעות"
SUGGESTIONS_CHANNEL_NAME = "📋・הצעות-שהוצעו"

# Staff roles
STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "KING FOX",
}

# XP Shop
XP_ROLES = {
    2500: "Active Member",
    5000: "Elite Member",
    10000: "Premium",
    20000: "Legend",
    35000: "OG Fox",
    50000: "Royal Fox",
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
    check_same_thread=False,
)

conn.row_factory = sqlite3.Row
cursor = conn.cursor()


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


conn.commit()


# =========================================================
# XP FUNCTIONS
# =========================================================

def get_xp(user_id: int) -> int:

    row = cursor.execute(
        "SELECT xp FROM xp WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    return int(row["xp"]) if row else 0


def set_xp(user_id: int, amount: int):

    cursor.execute("""
        INSERT INTO xp (user_id, xp)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET xp = excluded.xp
    """, (user_id, amount))

    conn.commit()


def add_xp(user_id: int, amount: int) -> int:

    new_xp = get_xp(user_id) + amount

    set_xp(
        user_id,
        new_xp
    )

    return new_xp


def remove_xp(user_id: int, amount: int) -> int:

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
# WARNING FUNCTIONS
# =========================================================

def get_warnings(user_id: int) -> int:

    row = cursor.execute(
        "SELECT warnings FROM warnings WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    return int(row["warnings"]) if row else 0


def add_warning(user_id: int) -> int:

    new_amount = get_warnings(user_id) + 1

    cursor.execute("""
        INSERT INTO warnings (user_id, warnings)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET warnings = excluded.warnings
    """, (
        user_id,
        new_amount
    ))

    conn.commit()

    return new_amount


# =========================================================
# STAFF
# =========================================================

def is_staff(member: discord.Member) -> bool:

    if member.guild_permissions.administrator:
        return True

    return any(
        role.name.upper() in STAFF_ROLES
        for role in member.roles
    )


# =========================================================
# XP PER MESSAGE
# =========================================================

xp_cooldowns = {}


@bot.event
async def on_message(
    message: discord.Message
):

    if message.author.bot:
        return

    now = time.time()

    last = xp_cooldowns.get(
        message.author.id,
        0
    )

    if now - last >= XP_COOLDOWN:

        add_xp(
            message.author.id,
            XP_PER_MESSAGE
        )

        xp_cooldowns[
            message.author.id
        ] = now

    await bot.process_commands(message)


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
# /ADDXP
# =========================================================

@bot.tree.command(
    name="addxp",
    description="הוסף XP למשתמש",
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

    if not isinstance(
        interaction.user,
        discord.Member
    ):
        await interaction.response.send_message(
            "❌ לא ניתן להשתמש בפקודה כאן.",
            ephemeral=True
        )
        return

    if not is_staff(
        interaction.user
    ):
        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
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


# =========================================================
# /REMOVEXP
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

    if not isinstance(
        interaction.user,
        discord.Member
    ) or not is_staff(
        interaction.user
    ):
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


# =========================================================
# /SETXP
# =========================================================

@bot.tree.command(
    name="setxp",
    description="קבע XP למשתמש",
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

    if not isinstance(
        interaction.user,
        discord.Member
    ) or not is_staff(
        interaction.user
    ):
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


# =========================================================
# /WARN
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

    if not isinstance(
        interaction.user,
        discord.Member
    ) or not is_staff(
        interaction.user
    ):
        await interaction.response.send_message(
            "❌ אין לך הרשאה.",
            ephemeral=True
        )
        return

    amount = add_warning(
        user.id
    )

    embed = discord.Embed(
        title="⚠️ אזהרה חדשה",
        description=(
            f"👤 משתמש: {user.mention}\n"
            f"📝 סיבה: {reason}\n"
            f"⚠️ אזהרות: **{amount}**"
        ),
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /WARNINGS
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
# XP SHOP
# =========================================================

class XPShopView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

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
            description="הדרגות הזמינות בשרת:",
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
        title="🛒 חנות XP",
        description=(
            "צבור XP וקבל דרגות מיוחדות!\n\n"
            "לחץ על הכפתור כדי לראות את החנות."
        ),
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        view=XPShopView()
    )


# =========================================================
# SUGGESTIONS
# =========================================================

class SuggestionPanelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

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

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ לא ניתן לשלוח הצעה כאן.",
                ephemeral=True
            )
            return

        # חיפוש הערוץ שבו ההצעות יופיעו
        suggestions_channel = discord.utils.get(
            interaction.guild.text_channels,
            name=SUGGESTIONS_CHANNEL_NAME
        )

        if suggestions_channel is None:

            await interaction.response.send_message(
                f"❌ לא נמצא ערוץ בשם "
                f"`{SUGGESTIONS_CHANNEL_NAME}`.",
                ephemeral=True
            )
            return

        # שמירת ההצעה
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

        # יצירת Embed
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

        embed.set_footer(
            text="Foxes • מערכת הצעות"
        )

        # שליחה לערוץ ההצעות
        message = await suggestions_channel.send(
            embed=embed,
            view=SuggestionVoteView(
                suggestion_id
            )
        )

        # שמירת message/channel ID
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
            f"✅ ההצעה שלך נשלחה ל-{suggestions_channel.mention}!",
            ephemeral=True
        )


# =========================================================
# SUGGESTION VOTE VIEW
# =========================================================

class SuggestionVoteView(
    discord.ui.View
):

    def __init__(
        self,
        suggestion_id: int
    ):

        super().__init__(
            timeout=None
        )

        self.suggestion_id = suggestion_id

        yes_button = discord.ui.Button(
            label="בעד",
            emoji="👍",
            style=discord.ButtonStyle.success,
            custom_id=f"suggestion_yes_{suggestion_id}"
        )

        no_button = discord.ui.Button(
            label="נגד",
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

        # ספירת הצבעות
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

        # עדכון הכפתורים
        for item in self.children:

            if isinstance(
                item,
                discord.ui.Button
            ):

                if item.custom_id == f"suggestion_yes_{self.suggestion_id}":
                    item.label = f"בעד {yes_count}"

                elif item.custom_id == f"suggestion_no_{self.suggestion_id}":
                    item.label = f"נגד {no_count}"

        try:

            await interaction.message.edit(
                view=self
            )

        except Exception as e:

            print(
                f"Suggestion vote edit error: {e}"
            )

        await interaction.response.send_message(
            "✅ ההצבעה שלך נקלטה!",
            ephemeral=True
        )


# =========================================================
# /SUGGESTIONS
# =========================================================

@bot.tree.command(
    name="suggestions",
    description="שלח פאנל הצעות",
    guild=GUILD
)
async def suggestions_command(
    interaction: discord.Interaction
):

    if not isinstance(
        interaction.user,
        discord.Member
    ) or not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לפתוח את פאנל ההצעות.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="💡 הצעות ל-Foxes",
        description=(
            "יש לכם רעיון לשיפור השרת?\n\n"
            "לחצו על **הצע רעיון** ושלחו אותו!\n\n"
            "📌 ההצעה תישלח אוטומטית לערוץ ההצעות."
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="Foxes • מערכת הצעות"
    )

    await interaction.response.send_message(
        embed=embed,
        view=SuggestionPanelView()
    )


# =========================================================
# TICKET DATABASE
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
        "description": "שאלות בנוגע לרכישות או מכירות",
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
# TICKET CONTROL VIEW
# =========================================================

class TicketControlView(
    discord.ui.View
):

    def __init__(
        self,
        channel_id: int,
        claimed_by: Optional[int] = None
    ):

        super().__init__(
            timeout=None
        )

        self.channel_id = channel_id
        self.claimed_by = claimed_by

        # -----------------------------------------
        # TAKE BUTTON
        # -----------------------------------------

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

        # -----------------------------------------
        # CLOSE BUTTON
        # -----------------------------------------

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

    # =====================================================
    # TAKE TICKET
    # =====================================================

    async def take_ticket(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ רק הצוות יכול לקחת טיפול בטיקט.",
                ephemeral=True
            )
            return

        channel_id = interaction.channel.id

        existing = get_ticket_claim(
            channel_id
        )

        if existing is not None:

            await interaction.response.send_message(
                f"❌ הטיקט כבר בטיפול של <@{existing}>.",
                ephemeral=True
            )
            return

        success = claim_ticket(
            channel_id,
            interaction.user.id
        )

        if not success:

            existing = get_ticket_claim(
                channel_id
            )

            await interaction.response.send_message(
                (
                    f"❌ הטיקט כבר בטיפול של <@{existing}>."
                    if existing
                    else "❌ לא ניתן לקחת את הטיקט כרגע."
                ),
                ephemeral=True
            )

            return

        if interaction.message.embeds:

            embed = interaction.message.embeds[0].copy()

        else:

            embed = discord.Embed(
                title="🎫 טיקט",
                color=discord.Color.blurple()
            )

        # הסרת field קודם
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
                channel_id,
                interaction.user.id
            )
        )

        await interaction.channel.send(
            f"👨‍💻 {interaction.user.mention} "
            f"לקח את הטיקט לטיפול."
        )

    # =====================================================
    # CLOSE TICKET
    # =====================================================

    async def close_ticket(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ רק הצוות יכול לסגור טיקט.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 הטיקט ייסגר בעוד 5 שניות."
        )

        await asyncio.sleep(5)

        try:

            await interaction.channel.delete(
                reason="Ticket closed"
            )

            delete_ticket_record(
                self.channel_id
            )

        except Exception as e:

            print(
                f"Ticket delete error: {e}"
            )


# =========================================================
# TICKET SELECT MENU
# =========================================================

class TicketTypeSelect(
    discord.ui.Select
):

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
            placeholder="בחר את סוג הטיקט...",
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

        data = TICKET_TYPES[
            ticket_type
        ]

        await create_ticket(
            interaction,
            ticket_type,
            data
        )


class TicketView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            TicketTypeSelect()
        )


# =========================================================
# CREATE TICKET
# =========================================================

async def create_ticket(
    interaction: discord.Interaction,
    ticket_type: str,
    ticket_data: dict
):

    guild = interaction.guild

    if guild is None:

        await interaction.response.send_message(
            "❌ לא ניתן לפתוח טיקט כאן.",
            ephemeral=True
        )

        return

    # בדיקה אם כבר יש טיקט
    existing = None

    for channel in guild.text_channels:

        if channel.topic == f"ticket_owner:{interaction.user.id}":

            existing = channel
            break

    if existing:

        await interaction.response.send_message(
            f"❌ כבר יש לך טיקט: {existing.mention}",
            ephemeral=True
        )

        return

    # חיפוש קטגוריה
    category = discord.utils.get(
        guild.categories,
        name=TICKET_CATEGORY_NAME
    )

    if category is None:

        category = await guild.create_category(
            TICKET_CATEGORY_NAME,
            reason="Ticket system"
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
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
    }

    # הרשאות צוות
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

    # שם הטיקט
    safe_name = ticket_type.lower()

    channel = await guild.create_text_channel(
        f"{safe_name}-{interaction.user.id}",
        category=category,
        overwrites=overwrites,
        topic=f"ticket_owner:{interaction.user.id}",
        reason=f"Ticket opened: {ticket_data['label']}"
    )

    # Embed
    embed = discord.Embed(
        title=(
            f"{ticket_data['emoji']} "
            f"{ticket_data['label']}"
        ),
        description=(
            f"שלום {interaction.user.mention}!\n\n"
            f"פתחת טיקט בנושא **{ticket_data['label']}**.\n\n"
            "📝 כתוב כאן את הפרטים של הפנייה שלך.\n"
            "👨‍💻 איש צוות יטפל בטיקט בהקדם.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🟢 **קח טיפול**\n"
            "איש צוות יכול לקחת את הטיקט.\n\n"
            "🔒 **סגור טיקט**\n"
            "סוגר את הטיקט."
        ),
        color=ticket_data["color"]
    )

    embed.add_field(
        name="📂 סוג הפנייה",
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

    # שליחת הודעת הטיקט
    message = await channel.send(
        content=interaction.user.mention,
        embed=embed,
        view=TicketControlView(
            channel.id
        )
    )

    # שמירת הטיקט
    create_ticket_record(
        channel.id,
        message.id
    )

    await interaction.response.send_message(
        (
            f"✅ הטיקט נפתח בהצלחה!\n"
            f"📂 סוג: **{ticket_data['label']}**\n"
            f"🎫 {channel.mention}"
        ),
        ephemeral=True
    )


# =========================================================
# /TICKET
# =========================================================

@bot.tree.command(
    name="ticket",
    description="שלח פאנל טיקטים",
    guild=GUILD
)
async def ticket_command(
    interaction: discord.Interaction
):

    if not isinstance(
        interaction.user,
        discord.Member
    ) or not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את פאנל הטיקטים.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎫 מערכת התמיכה של Foxes",
        description=(
            "יש לכם שאלה, בעיה או בקשה?\n\n"
            "בחרו את סוג הפנייה שלכם מהתפריט למטה.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🛠️ תמיכה\n"
            "🚨 דיווח על משתמש\n"
            "🐛 דיווח על באג\n"
            "👮 פנייה לצוות\n"
            "💰 רכישה / מכירה\n"
            "❓ שאלה כללית\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🦊 **Foxes Support**"
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="Foxes • Support System"
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView()
    )


# =========================================================
# SERVER BOOST
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
            1000
        )

        channel = discord.utils.get(
            after.guild.text_channels,
            name=BOOST_CHANNEL_NAME
        )

        if channel is None:

            channel = discord.utils.get(
                after.guild.text_channels,
                name="server-boost"
            )

        if channel is None:

            print(
                f"Boost by {after} detected. "
                f"+1000 XP"
            )

            return

        embed = discord.Embed(
            title="🚀 BOOST חדש לשרת!",
            description=(
                f"🎉 {after.mention} "
                "**עשה Server Boost ל-Foxes!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "🦊 תודה ענקית על התמיכה בשרת!\n\n"
                "⭐ **פרס Boost**\n"
                "💎 +**1,000 XP**\n"
                f"📊 ה-XP שלך עכשיו: **{new_xp:,}**\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "❤️ תודה שעזרת לחזק את Foxes!"
            ),
            color=discord.Color.fuchsia()
        )

        embed.set_thumbnail(
            url=after.display_avatar.url
        )

        embed.set_footer(
            text="Foxes • תודה על התמיכה!"
        )

        try:

            await channel.send(
                content=after.mention,
                embed=embed
            )

            print(
                f"Boost announcement sent for {after}"
            )

        except Exception as e:

            print(
                f"Boost announcement error: {e}"
            )


# =========================================================
# SLASH COMMAND ERRORS
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
                "❌ אירעה שגיאה בפקודה.",
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

    # =====================================================
    # PERSISTENT VIEWS
    # =====================================================

    try:

        bot.add_view(
            XPShopView()
        )

        bot.add_view(
            SuggestionPanelView()
        )

        bot.add_view(
            TicketView()
        )

        print(
            "✅ Persistent views loaded"
        )

    except Exception as e:

        print(
            f"View loading error: {e}"
        )

    # =====================================================
    # RESTORE SUGGESTIONS
    # =====================================================

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

        print(
            f"💡 Restored {len(rows)} suggestion views"
        )

    except Exception as e:

        print(
            f"Suggestion database error: {e}"
        )

    # =====================================================
    # RESTORE TICKETS
    # =====================================================

    try:

        rows = cursor.execute("""
            SELECT channel_id, message_id, staff_id
            FROM ticket_claims
        """).fetchall()

        restored = 0

        for row in rows:

            try:

                bot.add_view(
                    TicketControlView(
                        row["channel_id"],
                        row["staff_id"]
                    ),
                    message_id=row["message_id"]
                )

                restored += 1

            except Exception as e:

                print(
                    f"Ticket restore error: {e}"
                )

        print(
            f"🎫 Restored {restored} ticket views"
        )

    except Exception as e:

        print(
            f"Ticket database error: {e}"
        )

    # =====================================================
    # SYNC SLASH COMMANDS
    # =====================================================

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