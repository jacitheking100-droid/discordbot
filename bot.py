import discord
from discord.ext import commands
import re
import os
import asyncio
import sqlite3
import time

PREFIX = "!"

TICKET_CATEGORY = "Tickets"
STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "FOXY KING"
}

XP_PER_MESSAGE = 5
XP_COOLDOWN = 60

LINK_REGEX = re.compile(
    r"(https?://\S+|www\.\S+|discord\.gg/\S+|discord\.com/invite/\S+)",
    re.IGNORECASE
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)

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

db.commit()


def get_user(user_id):
    cursor.execute(
        "SELECT xp, warnings FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    if result is None:
        cursor.execute(
            "INSERT INTO users (user_id, xp, warnings) VALUES (?, 0, 0)",
            (user_id,)
        )
        db.commit()
        return 0, 0

    return result


def add_xp(user_id, amount):
    get_user(user_id)

    cursor.execute(
        "UPDATE users SET xp = xp + ? WHERE user_id = ?",
        (amount, user_id)
    )

    db.commit()


def add_warning(user_id):
    get_user(user_id)

    cursor.execute(
        "UPDATE users SET warnings = warnings + 1 WHERE user_id = ?",
        (user_id,)
    )

    db.commit()

    cursor.execute(
        "SELECT warnings FROM users WHERE user_id = ?",
        (user_id,)
    )

    return cursor.fetchone()[0]


# =========================
# STAFF CHECK
# =========================

def is_staff(member):
    return any(
        role.name.upper() in STAFF_ROLES
        for role in member.roles
    )


# =========================
# XP COOLDOWN
# =========================

xp_cooldowns = {}


# =========================
# BOT READY
# =========================

@bot.event
async def on_ready():
    print(f"הבוט מחובר בתור {bot.user}")

    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())


# =========================
# MESSAGE SYSTEM
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    # =====================
    # XP
    # =====================

    now = time.time()

    last_message = xp_cooldowns.get(
        message.author.id,
        0
    )

    if now - last_message >= XP_COOLDOWN:

        add_xp(
            message.author.id,
            XP_PER_MESSAGE
        )

        xp_cooldowns[message.author.id] = now

    # =====================
    # LINK BLOCK
    # =====================

    if LINK_REGEX.search(message.content):

        # Staff can send links
        if not is_staff(message.author):

            try:
                await message.delete()

                warnings = add_warning(
                    message.author.id
                )

                try:
                    await message.author.send(
                        "🚫 **קישור נחסם**\n\n"
                        "הודעתך נמחקה מכיוון "
                        "ששליחת קישורים אינה מותרת בשרת.\n\n"
                        f"⚠️ אזהרות: **{warnings}**"
                    )

                except discord.Forbidden:
                    pass

                print(
                    f"{message.author} "
                    f"קיבל אזהרה אוטומטית."
                )

            except discord.Forbidden:
                print(
                    "אין לבוט הרשאה למחוק הודעות."
                )

    await bot.process_commands(message)


# =========================
# TICKET SYSTEM
# =========================

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
        user = interaction.user

        existing = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{user.id}"
        )

        if existing:

            await interaction.response.send_message(
                f"יש לך כבר טיקט פתוח: {existing.mention}",
                ephemeral=True
            )

            return

        category = discord.utils.get(
            guild.categories,
            name=TICKET_CATEGORY
        )

        if category is None:

            category = await guild.create_category(
                TICKET_CATEGORY
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
                )
        }

        # Staff roles
        for role in guild.roles:

            if role.name.upper() in STAFF_ROLES:

                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel = await guild.create_text_channel(
            f"ticket-{user.id}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(
            f"🎫 הטיקט שלך נפתח: {channel.mention}",
            ephemeral=True
        )

        embed = discord.Embed(
            title="🎫 מרכז התמיכה",
            description=(
                f"שלום {user.mention}!\n\n"
                "הטיקט שלך נפתח בהצלחה.\n"
                "צוות השרת יגיע אליך בהקדם.\n\n"
                "**כדי לקבל מענה מהיר:**\n"
                "• הסבר את הבעיה\n"
                "• צרף מידע רלוונטי\n"
                "• המתן למענה הצוות"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="הפקח פוקסי • מערכת התמיכה"
        )

        await channel.send(
            content=user.mention,
            embed=embed,
            view=CloseTicketView()
        )


class CloseTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="סגור טיקט",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_message(
            "🔒 הטיקט ייסגר בעוד 5 שניות..."
        )

        await asyncio.sleep(5)

        await interaction.channel.delete()


# =========================
# TICKET COMMAND
# =========================

@bot.command()
async def ticket(ctx):

    if not is_staff(ctx.author):

        await ctx.send(
            "❌ רק צוות השרת יכול להשתמש בפקודה הזאת."
        )

        return

    embed = discord.Embed(
        title="🎫 מרכז התמיכה",
        description=(
            "צריכים עזרה?\n\n"
            "לחצו על **פתח טיקט** כדי לפתוח "
            "חדר פרטי עם צוות השרת.\n\n"
            "אנא הסבירו את הבעיה בצורה ברורה."
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="הפקח פוקסי • מערכת הטיקטים"
    )

    await ctx.send(
        embed=embed,
        view=TicketView()
    )


# =========================
# XP COMMAND
# =========================

@bot.command()
async def xp(
    ctx,
    member: discord.Member = None
):

    member = member or ctx.author

    user_xp, warnings = get_user(
        member.id
    )

    embed = discord.Embed(
        title="⭐ מערכת XP",
        description=(
            f"**{member.display_name}**\n\n"
            f"⭐ XP: **{user_xp}**\n"
            f"⚠️ אזהרות: **{warnings}**"
        ),
        color=discord.Color.gold()
    )

    await ctx.send(embed=embed)


# =========================
# WARN COMMAND
# =========================

@bot.command()
async def warn(
    ctx,
    member: discord.Member,
    *,
    reason="לא נמסרה סיבה"
):

    if not is_staff(ctx.author):

        await ctx.send(
            "❌ רק MOD ומעלה יכולים לתת אזהרות."
        )

        return

    warnings = add_warning(
        member.id
    )

    embed = discord.Embed(
        title="⚠️ אזהרה",
        description=(
            f"{member.mention} קיבל אזהרה.\n\n"
            f"**סיבה:** {reason}\n"
            f"**מספר אזהרות:** {warnings}"
        ),
        color=discord.Color.orange()
    )

    await ctx.send(embed=embed)

    try:

        await member.send(
            "⚠️ **קיבלת אזהרה בשרת.**\n\n"
            f"סיבה: {reason}\n"
            f"אזהרות: {warnings}"
        )

    except discord.Forbidden:
        pass


# =========================
# ERROR HANDLING
# =========================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            "❌ חסר מידע בפקודה."
        )

    elif isinstance(
        error,
        commands.MemberNotFound
    ):

        await ctx.send(
            "❌ לא מצאתי את המשתמש."
        )

    elif isinstance(
        error,
        commands.CommandNotFound
    ):

        return

    else:

        print(
            f"Command error: {error}"
        )


# =========================
# START BOT
# =========================

bot.run(
    os.environ["DISCORD_TOKEN"]
)