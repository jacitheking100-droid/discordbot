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

TICKET_CATEGORY_NAME = "🎫・טיקטים"
BOOST_CHANNEL_NAME = "boost"

STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "KING FOX",
}

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
# XP
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
    set_xp(user_id, new_xp)
    return new_xp


def remove_xp(user_id: int, amount: int) -> int:
    new_xp = max(0, get_xp(user_id) - amount)
    set_xp(user_id, new_xp)
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
    new_amount = get_warnings(user_id) + 1

    cursor.execute("""
        INSERT INTO warnings (user_id, warnings)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET warnings = excluded.warnings
    """, (user_id, new_amount))

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
async def on_message(message: discord.Message):

    if message.author.bot:
        return

    now = time.time()
    last = xp_cooldowns.get(message.author.id, 0)

    if now - last >= XP_COOLDOWN:
        add_xp(message.author.id, XP_PER_MESSAGE)
        xp_cooldowns[message.author.id] = now

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
    amount = get_xp(target.id)

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

    try:

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ לא ניתן להשתמש בפקודה כאן.",
                ephemeral=True
            )
            return

        if not is_staff(interaction.user):
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

        new_xp = add_xp(user.id, amount)

        await interaction.response.send_message(
            f"✅ נוסף ל-{user.mention} **{amount:,} XP**.\n"
            f"⭐ XP נוכחי: **{new_xp:,}**"
        )

    except Exception as e:

        print(
            f"ADDXP ERROR: {type(e).__name__}: {e}"
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ אירעה שגיאה.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ אירעה שגיאה.",
                    ephemeral=True
                )
        except:
            pass


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

    if not is_staff(interaction.user):
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

    new_xp = remove_xp(user.id, amount)

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

    if not is_staff(interaction.user):
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

    set_xp(user.id, amount)

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

    if not is_staff(interaction.user):
        await interaction.response.send_message(
            "❌ אין לך הרשאה.",
            ephemeral=True
        )
        return

    amount = add_warning(user.id)

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
    amount = get_warnings(target.id)

    await interaction.response.send_message(
        f"⚠️ ל-{target.mention} יש **{amount} אזהרות**."
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

        channel = interaction.channel

        if channel is None:
            await interaction.response.send_message(
                "❌ לא ניתן לשלוח הצעה כאן.",
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

        message = await channel.send(
            embed=embed,
            view=SuggestionVoteView(suggestion_id)
        )

        cursor.execute("""
            UPDATE suggestions
            SET message_id = ?, channel_id = ?
            WHERE id = ?
        """, (
            message.id,
            channel.id,
            suggestion_id
        ))

        conn.commit()

        await interaction.response.send_message(
            "✅ ההצעה נשלחה!",
            ephemeral=True
        )


class SuggestionVoteView(discord.ui.View):

    def __init__(self, suggestion_id: int):
        super().__init__(timeout=None)
        self.suggestion_id = suggestion_id

    @discord.ui.button(
        label="בעד",
        emoji="👍",
        style=discord.ButtonStyle.success,
        custom_id="suggestion_yes"
    )
    async def yes(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.vote(interaction, 1)

    @discord.ui.button(
        label="נגד",
        emoji="👎",
        style=discord.ButtonStyle.danger,
        custom_id="suggestion_no"
    )
    async def no(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.vote(interaction, -1)

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

        await interaction.response.send_message(
            "✅ ההצבעה שלך נקלטה!",
            ephemeral=True
        )


@bot.tree.command(
    name="suggestions",
    description="שלח פאנל הצעות",
    guild=GUILD
)
async def suggestions_command(
    interaction: discord.Interaction
):

    if not is_staff(interaction.user):
        await interaction.response.send_message(
            "❌ רק הצוות יכול לפתוח את פאנל ההצעות.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="💡 הצעות ל-Foxes",
        description=(
            "יש לכם רעיון לשיפור השרת?\n\n"
            "לחצו על **הצע רעיון** ושלחו אותו!"
        ),
        color=discord.Color.blurple()
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
    """, (channel_id,)).fetchone()

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
# TICKET CONTROL
# =========================================================

class TicketControlView(discord.ui.View):

    def __init__(
        self,
        channel_id: int,
        claimed_by: Optional[int] = None
    ):

        super().__init__(timeout=None)

        self.channel_id = channel_id
        self.claimed_by = claimed_by

        take_button = discord.ui.Button(
            label="קח טיפול" if claimed_by is None else "בטיפול",
            emoji="🟢" if claimed_by is None else "⚪",
            style=(
                discord.ButtonStyle.success
                if claimed_by is None
                else discord.ButtonStyle.secondary
            ),
            custom_id=f"ticket_take_{channel_id}",
            disabled=claimed_by is not None
        )

        take_button.callback = self.take_ticket
        self.add_item(take_button)

        close_button = discord.ui.Button(
            label="סגור טיקט",
            emoji="🔒",
            style=discord.ButtonStyle.danger,
            custom_id=f"ticket_close_{channel_id}"
        )

        close_button.callback = self.close_ticket
        self.add_item(close_button)

    async def take_ticket(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ רק הצוות יכול לקחת טיפול בטיקט.",
                ephemeral=True
            )
            return

        channel_id = interaction.channel.id

        existing = get_ticket_claim(channel_id)

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

            existing = get_ticket_claim(channel_id)

            await interaction.response.send_message(
                f"❌ הטיקט כבר בטיפול של <@{existing}>."
                if existing
                else "❌ לא ניתן לקחת את הטיקט כרגע.",
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
                channel_id,
                interaction.user.id
            )
        )

        await interaction.channel.send(
            f"👨‍💻 {interaction.user.mention} "
            f"לקח את הטיקט לטיפול."
        )

    async def close_ticket(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):
            return

        if not is_staff(interaction.user):

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
# TICKET OPEN VIEW
# =========================================================

class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="פתח טיקט",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="open_ticket"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ לא ניתן לפתוח טיקט כאן.",
                ephemeral=True
            )
            return

        existing = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{interaction.user.id}"
        )

        if existing:
            await interaction.response.send_message(
                f"❌ כבר יש לך טיקט: {existing.mention}",
                ephemeral=True
            )
            return

        category = discord.utils.get(
            guild.categories,
            name=TICKET_CATEGORY_NAME
        )

        if category is None:
            category = await guild.create_category(
                TICKET_CATEGORY_NAME,
                reason="Ticket system"
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
                )
        }

        for role in guild.roles:

            if role.name.upper() in STAFF_ROLES:

                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True
                )

        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.id}",
            category=category,
            overwrites=overwrites,
            reason="Ticket opened"
        )

        embed = discord.Embed(
            title="🎫 טיקט נפתח",
            description=(
                f"שלום {interaction.user.mention}!\n\n"
                "תאר כאן את הבעיה או הבקשה שלך.\n"
                "אחד מאנשי הצוות יעזור לך בהקדם.\n\n"
                "🟢 **קח טיפול**\n"
                "איש צוות יכול לקחת את הטיקט לטיפול."
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="Foxes • מערכת טיקטים"
        )

        message = await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=TicketControlView(channel.id)
        )

        create_ticket_record(
            channel.id,
            message.id
        )

        await interaction.response.send_message(
            f"✅ הטיקט נפתח: {channel.mention}",
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

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את פאנל הטיקטים.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎫 מערכת התמיכה של Foxes",
        description=(
            "יש לכם שאלה, בעיה או בקשה?\n\n"
            "פתחו טיקט ואחד מאנשי הצוות יעזור לכם.\n\n"
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

    except:
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

    # Persistent views
    try:

        bot.add_view(XPShopView())
        bot.add_view(SuggestionPanelView())
        bot.add_view(TicketView())

        print("✅ Persistent views loaded")

    except Exception as e:

        print(
            f"View loading error: {e}"
        )

    # Restore suggestions
    try:

        rows = cursor.execute("""
            SELECT id
            FROM suggestions
            WHERE message_id IS NOT NULL
        """).fetchall()

        for row in rows:

            try:

                bot.add_view(
                    SuggestionVoteView(row["id"])
                )

            except Exception as e:

                print(
                    f"Suggestion restore error: {e}"
                )

    except Exception as e:

        print(
            f"Suggestion database error: {e}"
        )

    # Restore tickets
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

        print(
            f"🎫 Restored {len(rows)} ticket views"
        )

    except Exception as e:

        print(
            f"Ticket database error: {e}"
        )

    # Sync slash commands
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

bot.run(DISCORD_TOKEN)