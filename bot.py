import os
import re
import sqlite3
import asyncio
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands


# =========================================================
# CONFIG
# =========================================================

GUILD_ID = 1552344386526908488

XP_PER_MESSAGE = 50
XP_COOLDOWN = 60

SUGGESTION_INPUT_CHANNEL = "💡・הצעות-לשרת"
SUGGESTION_OUTPUT_CHANNEL = "📋・הצעות-שהוצעו"
XP_SHOP_CHANNEL = "🛒・חנות-xp"

TICKET_CATEGORY_NAME = "🎫・טיקטים"

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

XP_SHOP_ITEMS = [
    {
        "name": "🟢 Active Member",
        "role_name": "Active Member",
        "price": 2500,
    },
    {
        "name": "🔵 Elite Member",
        "role_name": "Elite Member",
        "price": 5000,
    },
    {
        "name": "🟣 Premium",
        "role_name": "Premium",
        "price": 10000,
    },
    {
        "name": "🟠 Legend",
        "role_name": "Legend",
        "price": 20000,
    },
    {
        "name": "🔴 OG Fox",
        "role_name": "OG Fox",
        "price": 35000,
    },
    {
        "name": "👑 Royal Fox",
        "role_name": "Royal Fox",
        "price": 50000,
    },
]


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True


# =========================================================
# BOT
# =========================================================

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

conn.commit()


# =========================================================
# XP FUNCTIONS
# =========================================================

def get_xp(user_id: int) -> int:

    row = cursor.execute(
        "SELECT xp FROM xp WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if row is None:

        cursor.execute(
            "INSERT INTO xp (user_id, xp) VALUES (?, 0)",
            (user_id,),
        )

        conn.commit()

        return 0

    return int(row["xp"])


def add_xp(user_id: int, amount: int) -> int:

    current = get_xp(user_id)

    new_xp = current + amount

    cursor.execute(
        """
        UPDATE xp
        SET xp = ?
        WHERE user_id = ?
        """,
        (new_xp, user_id),
    )

    conn.commit()

    return new_xp


def remove_xp(user_id: int, amount: int) -> bool:

    current = get_xp(user_id)

    if current < amount:
        return False

    cursor.execute(
        """
        UPDATE xp
        SET xp = ?
        WHERE user_id = ?
        """,
        (current - amount, user_id),
    )

    conn.commit()

    return True


def set_xp(user_id: int, amount: int):

    cursor.execute(
        """
        INSERT INTO xp (user_id, xp)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET xp = excluded.xp
        """,
        (user_id, amount),
    )

    conn.commit()


# =========================================================
# WARNING FUNCTIONS
# =========================================================

def get_warnings(user_id: int) -> int:

    row = cursor.execute(
        "SELECT warnings FROM warnings WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if row is None:

        cursor.execute(
            """
            INSERT INTO warnings
            (user_id, warnings)
            VALUES (?, 0)
            """,
            (user_id,),
        )

        conn.commit()

        return 0

    return int(row["warnings"])


def add_warning(user_id: int) -> int:

    amount = get_warnings(user_id) + 1

    cursor.execute(
        """
        UPDATE warnings
        SET warnings = ?
        WHERE user_id = ?
        """,
        (amount, user_id),
    )

    conn.commit()

    return amount


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
# CHANNEL HELPER
# =========================================================

def find_text_channel(
    guild: discord.Guild,
    name: str,
):

    return discord.utils.get(
        guild.text_channels,
        name=name,
    )


# =========================================================
# XP SHOP
# =========================================================

async def get_or_create_shop_role(
    guild: discord.Guild,
    role_name: str,
):

    role = discord.utils.get(
        guild.roles,
        name=role_name,
    )

    if role:
        return role

    return await guild.create_role(
        name=role_name,
        reason="XP Shop role",
    )


def build_xp_shop_embed():

    embed = discord.Embed(
        title="🛒 חנות XP",
        description=(
            "קונים רולים באמצעות XP.\n"
            "בחרו רול מהתפריט למטה.\n\n"
            "הרולים בחנות אינם מקבלים הרשאות ניהול."
        ),
        color=discord.Color.blurple(),
    )

    lines = []

    for item in XP_SHOP_ITEMS:

        lines.append(
            f"{item['name']} — **{item['price']:,} XP**"
        )

    embed.add_field(
        name="🎁 הרולים בחנות",
        value="\n".join(lines),
        inline=False,
    )

    embed.set_footer(
        text="בחרו רול מהתפריט כדי לרכוש אותו"
    )

    return embed


class XPShopSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for item in XP_SHOP_ITEMS:

            options.append(
                discord.SelectOption(
                    label=item["role_name"],
                    description=f"{item['price']:,} XP",
                    value=item["role_name"],
                )
            )

        super().__init__(
            placeholder="בחרו רול לרכישה",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="xp_shop_select",
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ החנות זמינה רק בשרת.",
                ephemeral=True,
            )

            return

        selected_name = self.values[0]

        item = next(
            (
                x for x in XP_SHOP_ITEMS
                if x["role_name"] == selected_name
            ),
            None,
        )

        if item is None:

            await interaction.response.send_message(
                "❌ הרול לא נמצא.",
                ephemeral=True,
            )

            return

        role = await get_or_create_shop_role(
            interaction.guild,
            item["role_name"],
        )

        if role in interaction.user.roles:

            await interaction.response.send_message(
                "❌ כבר יש לך את הרול הזה.",
                ephemeral=True,
            )

            return

        current_xp = get_xp(
            interaction.user.id
        )

        price = item["price"]

        if current_xp < price:

            await interaction.response.send_message(
                f"❌ אין לך מספיק XP.\n\n"
                f"⭐ XP שלך: **{current_xp:,}**\n"
                f"💰 מחיר: **{price:,} XP**\n"
                f"📉 חסר לך: **{price - current_xp:,} XP**",
                ephemeral=True,
            )

            return

        me = interaction.guild.me

        if me is None:

            await interaction.response.send_message(
                "❌ לא הצלחתי לבדוק את תפקיד הבוט.",
                ephemeral=True,
            )

            return

        if role >= me.top_role:

            await interaction.response.send_message(
                "❌ הבוט לא יכול לתת את הרול הזה.\n"
                "שים את הרול של הבוט מעל רולי ה-XP.",
                ephemeral=True,
            )

            return

        removed = remove_xp(
            interaction.user.id,
            price,
        )

        if not removed:

            await interaction.response.send_message(
                "❌ הרכישה נכשלה.",
                ephemeral=True,
            )

            return

        try:

            await interaction.user.add_roles(
                role,
                reason="XP Shop purchase",
            )

        except (discord.Forbidden, discord.HTTPException):

            add_xp(
                interaction.user.id,
                price,
            )

            await interaction.response.send_message(
                "❌ לא הצלחתי לתת את הרול.\n"
                "ה-XP הוחזר.",
                ephemeral=True,
            )

            return

        remaining = get_xp(
            interaction.user.id
        )

        await interaction.response.send_message(
            f"🎉 הרכישה הצליחה!\n\n"
            f"🎁 רול: **{role.name}**\n"
            f"💸 שולם: **{price:,} XP**\n"
            f"⭐ נשאר לך: **{remaining:,} XP**",
            ephemeral=True,
        )


class XPShopView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            XPShopSelect()
        )


# =========================================================
# SUGGESTIONS
# =========================================================

def get_suggestion_votes(
    suggestion_id: int,
):

    rows = cursor.execute(
        """
        SELECT vote, COUNT(*) AS amount
        FROM suggestion_votes
        WHERE suggestion_id = ?
        GROUP BY vote
        """,
        (suggestion_id,),
    ).fetchall()

    likes = 0
    dislikes = 0

    for row in rows:

        if row["vote"] == 1:
            likes = row["amount"]

        elif row["vote"] == -1:
            dislikes = row["amount"]

    return likes, dislikes


def get_user_suggestion_vote(
    suggestion_id: int,
    user_id: int,
):

    row = cursor.execute(
        """
        SELECT vote
        FROM suggestion_votes
        WHERE suggestion_id = ?
        AND user_id = ?
        """,
        (
            suggestion_id,
            user_id,
        ),
    ).fetchone()

    if row is None:
        return None

    return int(row["vote"])


def set_suggestion_vote(
    suggestion_id: int,
    user_id: int,
    vote: int,
):

    current = get_user_suggestion_vote(
        suggestion_id,
        user_id,
    )

    if current == vote:

        cursor.execute(
            """
            DELETE FROM suggestion_votes
            WHERE suggestion_id = ?
            AND user_id = ?
            """,
            (
                suggestion_id,
                user_id,
            ),
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
                vote,
            ),
        )

    conn.commit()


def build_suggestion_embed(
    suggestion_id: int,
    user_id: int,
    content: str,
):

    likes, dislikes = get_suggestion_votes(
        suggestion_id
    )

    embed = discord.Embed(
        title=f"💡 הצעה #{suggestion_id}",
        description=content,
        color=discord.Color.blurple(),
    )

    embed.add_field(
        name="👤 הוצע על ידי",
        value=f"<@{user_id}>",
        inline=False,
    )

    embed.add_field(
        name="👍 בעד",
        value=str(likes),
        inline=True,
    )

    embed.add_field(
        name="👎 נגד",
        value=str(dislikes),
        inline=True,
    )

    return embed


class SuggestionVoteView(
    discord.ui.View
):

    def __init__(
        self,
        suggestion_id: int,
    ):

        super().__init__(
            timeout=None
        )

        self.suggestion_id = suggestion_id

        like = discord.ui.Button(
            label="0",
            emoji="👍",
            style=discord.ButtonStyle.success,
            custom_id=f"suggestion_like_{suggestion_id}",
        )

        dislike = discord.ui.Button(
            label="0",
            emoji="👎",
            style=discord.ButtonStyle.danger,
            custom_id=f"suggestion_dislike_{suggestion_id}",
        )

        like.callback = self.like_callback
        dislike.callback = self.dislike_callback

        self.add_item(like)
        self.add_item(dislike)

        self.update_labels()

    def update_labels(self):

        likes, dislikes = get_suggestion_votes(
            self.suggestion_id
        )

        self.children[0].label = str(likes)
        self.children[1].label = str(dislikes)

    async def refresh(
        self,
        interaction: discord.Interaction,
    ):

        row = cursor.execute(
            """
            SELECT user_id, content
            FROM suggestions
            WHERE id = ?
            """,
            (self.suggestion_id,),
        ).fetchone()

        if row is None:
            return

        self.update_labels()

        embed = build_suggestion_embed(
            self.suggestion_id,
            row["user_id"],
            row["content"],
        )

        try:

            await interaction.message.edit(
                embed=embed,
                view=self,
            )

        except discord.HTTPException:
            pass

    async def like_callback(
        self,
        interaction: discord.Interaction,
    ):

        set_suggestion_vote(
            self.suggestion_id,
            interaction.user.id,
            1,
        )

        await interaction.response.defer()

        await self.refresh(
            interaction
        )

    async def dislike_callback(
        self,
        interaction: discord.Interaction,
    ):

        set_suggestion_vote(
            self.suggestion_id,
            interaction.user.id,
            -1,
        )

        await interaction.response.defer()

        await self.refresh(
            interaction
        )


class SuggestionModal(
    discord.ui.Modal,
    title="💡 הצעה לשרת",
):

    suggestion = discord.ui.TextInput(
        label="מה ההצעה שלך?",
        placeholder="כתוב כאן את ההצעה שלך...",
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=1000,
    )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):

        channel = find_text_channel(
            interaction.guild,
            SUGGESTION_OUTPUT_CHANNEL,
        )

        if channel is None:

            await interaction.response.send_message(
                f"❌ לא נמצא החדר `{SUGGESTION_OUTPUT_CHANNEL}`.",
                ephemeral=True,
            )

            return

        cursor.execute(
            """
            INSERT INTO suggestions
            (user_id, content, created_at)
            VALUES (?, ?, ?)
            """,
            (
                interaction.user.id,
                str(self.suggestion.value),
                int(time.time()),
            ),
        )

        conn.commit()

        suggestion_id = cursor.lastrowid

        embed = build_suggestion_embed(
            suggestion_id,
            interaction.user.id,
            str(self.suggestion.value),
        )

        message = await channel.send(
            embed=embed,
            view=SuggestionVoteView(
                suggestion_id
            ),
        )

        cursor.execute(
            """
            UPDATE suggestions
            SET message_id = ?,
                channel_id = ?
            WHERE id = ?
            """,
            (
                message.id,
                channel.id,
                suggestion_id,
            ),
        )

        conn.commit()

        await interaction.response.send_message(
            f"✅ ההצעה נשלחה!\n"
            f"💡 מספר הצעה: **#{suggestion_id}**",
            ephemeral=True,
        )


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
        custom_id="suggestion_panel_button",
    )
    async def suggestion_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        await interaction.response.send_modal(
            SuggestionModal()
        )


# =========================================================
# TICKETS
# =========================================================

class CloseTicketView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="סגור טיקט",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ רק הצוות יכול לסגור טיקט.",
                ephemeral=True,
            )

            return

        await interaction.response.send_message(
            "🔒 הטיקט יימחק בעוד 5 שניות."
        )

        await asyncio.sleep(5)

        try:

            await interaction.channel.delete(
                reason="Ticket closed"
            )

        except discord.HTTPException:
            pass


class TicketView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="פתח טיקט",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="open_ticket",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):

        guild = interaction.guild

        if guild is None:

            await interaction.response.send_message(
                "❌ לא ניתן לפתוח טיקט כאן.",
                ephemeral=True,
            )

            return

        existing = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{interaction.user.id}",
        )

        if existing:

            await interaction.response.send_message(
                f"❌ כבר יש לך טיקט: {existing.mention}",
                ephemeral=True,
            )

            return

        category = discord.utils.get(
            guild.categories,
            name=TICKET_CATEGORY_NAME,
        )

        if category is None:

            category = await guild.create_category(
                TICKET_CATEGORY_NAME,
                reason="Ticket system",
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
                    embed_links=True,
                ),
        }

        for role in guild.roles:

            if role.name.upper() in STAFF_ROLES:

                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                )

        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.id}",
            category=category,
            overwrites=overwrites,
            reason="Ticket opened",
        )

        embed = discord.Embed(
            title="🎫 טיקט נפתח",
            description=(
                f"שלום {interaction.user.mention}!\n\n"
                "תאר כאן את הבעיה או הבקשה שלך.\n"
                "אחד מאנשי הצוות יעזור לך בהקדם."
            ),
            color=discord.Color.blurple(),
        )

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=CloseTicketView(),
        )

        await interaction.response.send_message(
            f"✅ הטיקט נפתח: {channel.mention}",
            ephemeral=True,
        )


# =========================================================
# XP COOLDOWN
# =========================================================

last_xp_message = {}


# =========================================================
# ON MESSAGE
# =========================================================

@bot.event
async def on_message(
    message: discord.Message
):

    if message.author.bot:
        return

    if message.guild is None:
        return

    # Anti Link

    link_pattern = re.compile(
        r"(https?://\S+|www\.\S+)",
        re.IGNORECASE,
    )

    if link_pattern.search(
        message.content
    ):

        if (
            isinstance(message.author, discord.Member)
            and not is_staff(message.author)
        ):

            try:
                await message.delete()
            except discord.HTTPException:
                pass

            warning_amount = add_warning(
                message.author.id
            )

            try:

                await message.channel.send(
                    f"⚠️ {message.author.mention} "
                    f"קישורים אינם מותרים כאן.\n"
                    f"⚠️ אזהרות: **{warning_amount}**",
                    delete_after=5,
                )

            except discord.HTTPException:
                pass

            return

    # XP

    now = time.time()

    last_time = last_xp_message.get(
        message.author.id,
        0,
    )

    if now - last_time >= XP_COOLDOWN:

        add_xp(
            message.author.id,
            XP_PER_MESSAGE,
        )

        last_xp_message[
            message.author.id
        ] = now

    await bot.process_commands(
        message
    )


# =========================================================
# WELCOME
# =========================================================

@bot.event
async def on_member_join(
    member: discord.Member
):

    channel = discord.utils.get(
        member.guild.text_channels,
        name="welcome",
    )

    if channel is None:
        return

    embed = discord.Embed(
        title="🦊 ברוך הבא ל-Foxes!",
        description=(
            f"ברוך הבא {member.mention}!\n"
            f"אנחנו שמחים שהצטרפת לשרת."
        ),
        color=discord.Color.orange(),
    )

    embed.set_thumbnail(
        url=member.display_avatar.url
    )

    embed.set_footer(
        text=f"Member #{member.guild.member_count}"
    )

    try:
        await channel.send(
            embed=embed
        )
    except discord.HTTPException:
        pass


# =========================================================
# /XP
# =========================================================

@bot.tree.command(
    name="xp",
    description="בדוק כמה XP יש לך או למשתמש אחר",
)
@app_commands.describe(
    user="המשתמש שתרצה לבדוק",
)
async def xp_command(
    interaction: discord.Interaction,
    user: Optional[discord.Member] = None,
):

    target = user or interaction.user

    amount = get_xp(
        target.id
    )

    await interaction.response.send_message(
        f"⭐ ל-{target.mention} יש "
        f"**{amount:,} XP**."
    )


# =========================================================
# /ADDXP
# =========================================================

@bot.tree.command(
    name="addxp",
    description="הוסף XP למשתמש",
)
@app_commands.describe(
    user="המשתמש שיקבל XP",
    amount="כמות ה-XP להוסיף",
)
async def addxp_command(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int,
):

    if not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True,
        )

        return

    if amount <= 0:

        await interaction.response.send_message(
            "❌ הכמות חייבת להיות גדולה מ-0.",
            ephemeral=True,
        )

        return

    new_xp = add_xp(
        user.id,
        amount,
    )

    await interaction.response.send_message(
        f"✅ נוסף ל-{user.mention} "
        f"**{amount:,} XP**.\n"
        f"⭐ XP נוכחי: **{new_xp:,}**"
    )


# =========================================================
# /REMOVEXP
# =========================================================

@bot.tree.command(
    name="removexp",
    description="הסר XP ממשתמש",
)
@app_commands.describe(
    user="המשתמש שממנו יורד XP",
    amount="כמות ה-XP להסיר",
)
async def removexp_command(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int,
):

    if not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True,
        )

        return

    if amount <= 0:

        await interaction.response.send_message(
            "❌ הכמות חייבת להיות גדולה מ-0.",
            ephemeral=True,
        )

        return

    current = get_xp(
        user.id
    )

    if current < amount:

        await interaction.response.send_message(
            f"❌ אין למשתמש מספיק XP.\n"
            f"⭐ XP נוכחי: **{current:,}**",
            ephemeral=True,
        )

        return

    remove_xp(
        user.id,
        amount,
    )

    new_xp = get_xp(
        user.id
    )

    await interaction.response.send_message(
        f"✅ הוסר מ-{user.mention} "
        f"**{amount:,} XP**.\n"
        f"⭐ XP נוכחי: **{new_xp:,}**"
    )


# =========================================================
# /SETXP
# =========================================================

@bot.tree.command(
    name="setxp",
    description="קבע XP למשתמש",
)
@app_commands.describe(
    user="המשתמש",
    amount="כמות ה-XP החדשה",
)
async def setxp_command(
    interaction: discord.Interaction,
    user: discord.Member,
    amount: int,
):

    if not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True,
        )

        return

    if amount < 0:

        await interaction.response.send_message(
            "❌ אי אפשר להגדיר XP שלילי.",
            ephemeral=True,
        )

        return

    set_xp(
        user.id,
        amount,
    )

    await interaction.response.send_message(
        f"✅ ה-XP של {user.mention} "
        f"הוגדר ל-**{amount:,} XP**."
    )


# =========================================================
# /WARNINGS
# =========================================================

@bot.tree.command(
    name="warnings",
    description="בדוק כמה אזהרות יש למשתמש",
)
@app_commands.describe(
    user="המשתמש",
)
async def warnings_command(
    interaction: discord.Interaction,
    user: Optional[discord.Member] = None,
):

    target = user or interaction.user

    amount = get_warnings(
        target.id
    )

    await interaction.response.send_message(
        f"⚠️ ל-{target.mention} יש "
        f"**{amount} אזהרות**."
    )


# =========================================================
# /WARN
# =========================================================

@bot.tree.command(
    name="warn",
    description="תן אזהרה למשתמש",
)
@app_commands.describe(
    user="המשתמש שיקבל אזהרה",
)
async def warn_command(
    interaction: discord.Interaction,
    user: discord.Member,
):

    if not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True,
        )

        return

    amount = add_warning(
        user.id
    )

    await interaction.response.send_message(
        f"⚠️ {user.mention} קיבל אזהרה.\n"
        f"⚠️ סה״כ אזהרות: **{amount}**"
    )


# =========================================================
# /XPSHOP
# =========================================================

@bot.tree.command(
    name="xpshop",
    description="שלח את חנות ה-XP",
)
async def xpshop_command(
    interaction: discord.Interaction,
):

    if not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את החנות.",
            ephemeral=True,
        )

        return

    embed = build_xp_shop_embed()

    await interaction.response.send_message(
        embed=embed,
        view=XPShopView(),
    )


# =========================================================
# /SUGGESTIONS
# =========================================================

@bot.tree.command(
    name="suggestions",
    description="שלח פאנל הצעות",
)
async def suggestions_command(
    interaction: discord.Interaction,
):

    if not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את פאנל ההצעות.",
            ephemeral=True,
        )

        return

    embed = discord.Embed(
        title="💡 הצעות לשרת",
        description=(
            "יש לכם רעיון לשיפור השרת?\n\n"
            "לחצו על הכפתור למטה ושלחו את ההצעה שלכם."
        ),
        color=discord.Color.blurple(),
    )

    await interaction.response.send_message(
        embed=embed,
        view=SuggestionPanelView(),
    )


# =========================================================
# /TICKET
# =========================================================

@bot.tree.command(
    name="ticket",
    description="שלח פאנל פתיחת טיקט",
)
async def ticket_command(
    interaction: discord.Interaction,
):

    if not is_staff(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ רק הצוות יכול לשלוח את פאנל הטיקטים.",
            ephemeral=True,
        )

        return

    embed = discord.Embed(
        title="🎫 מערכת טיקטים",
        description=(
            "צריכים עזרה?\n\n"
            "לחצו על **פתח טיקט** כדי לפתוח חדר פרטי עם הצוות."
        ),
        color=discord.Color.blurple(),
    )

    await interaction.response.send_message(
        embed=embed,
        view=TicketView(),
    )


# =========================================================
# SETUP HOOK
# =========================================================

@bot.event
async def setup_hook():

    # Persistent views

    bot.add_view(
        XPShopView()
    )

    bot.add_view(
        SuggestionPanelView()
    )

    bot.add_view(
        TicketView()
    )

    bot.add_view(
        CloseTicketView()
    )

    # Restore suggestion buttons

    rows = cursor.execute(
        "SELECT id FROM suggestions WHERE message_id IS NOT NULL"
    ).fetchall()

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

    # Sync commands to Foxes

    try:

        synced = await bot.tree.sync(
            guild=GUILD
        )

        print(
            f"✅ Synced {len(synced)} commands to Foxes."
        )

    except Exception as e:

        print(
            f"❌ Command sync error: {e}"
        )


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print(
        f"🦊 Logged in as {bot.user} "
        f"({bot.user.id})"
    )

    print(
        "✅ Foxes bot is online!"
    )


# =========================================================
# RUN
# =========================================================

TOKEN = os.environ.get(
    "DISCORD_TOKEN"
)

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN לא מוגדר ב-Railway"
    )

bot.run(TOKEN)