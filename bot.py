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

WELCOME_CHANNEL_NAME = "ברוכים-הבאים-👋"
RULES_CHANNEL_NAME = "📜・חוקים"

UPDATES_ROLE_NAME = "🔔・עדכונים"
GIVEAWAYS_ROLE_NAME = "🎉・הגרלות"

STAFF_ROLES = {
    "MOD",
    "SERVER STAFF",
    "ADMIN",
    "HEAD ADMIN",
    "KING FOX"
}

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


def add_warning(user_id):

    ensure_user(user_id)

    cursor.execute(
        "UPDATE users SET warnings = warnings + 1 WHERE user_id = ?",
        (user_id,)
    )

    db.commit()

    return get_warnings(user_id)


# =========================
# ROLE SELECTION
# =========================

class RoleSelectionView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(
        self,
        interaction: discord.Interaction,
        role_name: str,
        display_name: str
    ):

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ לא ניתן להשתמש בזה כאן.",
                ephemeral=True
            )
            return

        role = get_role(guild, role_name)

        if role is None:
            await interaction.response.send_message(
                f"❌ הרול `{role_name}` לא נמצא בשרת.",
                ephemeral=True
            )
            return

        me = guild.me

        if me and role >= me.top_role:
            await interaction.response.send_message(
                f"❌ הבוט לא יכול לנהל את הרול **{role.name}**.\n"
                f"שים את הרול של הבוט מעל הרול הזה.",
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
                    f"🔕 הרול **{display_name}** הוסר ממך.",
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
                "❌ לבוט אין הרשאה לנהל את הרול הזה.",
                ephemeral=True
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ אירעה שגיאה בזמן שינוי הרול.",
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
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            GIVEAWAYS_ROLE_NAME,
            "הגרלות"
        )


# =========================
# WELCOME PANEL
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
            "קבלת התראות ועדכונים חשובים מהשרת.\n\n"
            "🎉 **הגרלות**\n"
            "קבלת התראות כאשר מתחילות הגרלות חדשות.\n\n"
            "💡 ניתן לבחור את שניהם או רק אחד מהם.\n"
            "לחיצה נוספת על כפתור שכבר בחרתם תסיר את הרול.\n\n"
            f"📜 לפני שמתחילים, עברו על החוקים: {rules_text}"
        ),
        color=discord.Color.blue()
    )

    embed.set_footer(
        text="Foxes • Role Selection"
    )

    return embed


async def send_role_panel(guild):

    channel = get_channel(
        guild,
        WELCOME_CHANNEL_NAME
    )

    if channel is None:
        print(
            f"[WELCOME] החדר '{WELCOME_CHANNEL_NAME}' לא נמצא."
        )
        return

    try:

        await channel.send(
            embed=create_role_panel_embed(guild),
            view=RoleSelectionView()
        )

        print("[WELCOME] פאנל הרולים נשלח.")

    except discord.Forbidden:

        print(
            "[WELCOME] אין לבוט הרשאה לשלוח הודעה בחדר."
        )

    except discord.HTTPException as e:

        print(
            f"[WELCOME] שגיאה בשליחת פאנל: {e}"
        )


# =========================
# WELCOME SYSTEM
# =========================

@bot.event
async def on_member_join(member):

    print(
        f"[WELCOME] משתמש נכנס: {member} ({member.id})"
    )

    # Anti-raid basic log
    print(
        f"[WELCOME] מספר חברים בשרת: {member.guild.member_count}"
    )

    channel = get_channel(
        member.guild,
        WELCOME_CHANNEL_NAME
    )

    if channel is None:

        print(
            f"[WELCOME] ERROR: החדר '{WELCOME_CHANNEL_NAME}' לא נמצא."
        )

        return

    embed = discord.Embed(
        title="🦊 ברוכים הבאים ל-Foxes!",
        description=(
            f"ברוכים הבאים {member.mention}!\n\n"
            f"**{member.display_name}** הצטרף עכשיו לשרת.\n\n"
            f"👥 אתם עכשיו **{member.guild.member_count}** חברים בשרת!\n\n"
            "📜 עברו על החוקים\n"
            "🎛️ בחרו את ההתראות שתרצו לקבל\n\n"
            "תהנו בשרת ובהצלחה!"
        ),
        color=discord.Color.blue()
    )

    try:

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

    except Exception:
        pass

    embed.set_footer(
        text="Foxes • Welcome"
    )

    try:

        await channel.send(
            embed=embed
        )

        print(
            f"[WELCOME] Welcome נשלח עבור {member}"
        )

        await channel.send(
            embed=create_role_panel_embed(member.guild),
            view=RoleSelectionView()
        )

        print(
            "[WELCOME] פאנל הרולים נשלח."
        )

    except discord.Forbidden:

        print(
            "[WELCOME] ERROR: אין לבוט הרשאת Send Messages / Embed Links."
        )

    except discord.HTTPException as e:

        print(
            f"[WELCOME] ERROR: {e}"
        )


# =========================
# TICKET VIEWS
# =========================

class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

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


class TicketTypeView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=60)

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


class TicketControlView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

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
async def xp_command(interaction: discord.Interaction):

    xp = get_xp(interaction.user.id)

    embed = discord.Embed(
        title="📊 ה-XP שלך",
        description=f"יש לך כרגע **{xp} XP**.",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


@bot.tree.command(
    name="warnings",
    description="בדיקת מספר האזהרות שלך"
)
async def warnings_command(interaction: discord.Interaction):

    warnings = get_warnings(interaction.user.id)

    embed = discord.Embed(
        title="⚠️ האזהרות שלך",
        description=f"יש לך כרגע **{warnings} אזהרות**.",
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


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

    warnings = add_warning(member.id)

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
# WELCOME PANEL COMMAND
# =========================

@bot.tree.command(
    name="welcome",
    description="שליחת פאנל הרולים של השרת"
)
async def welcome_command(
    interaction: discord.Interaction
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ רק צוות יכול לשלוח את הפאנל.",
            ephemeral=True
        )

        return

    await interaction.response.send_message(
        embed=create_role_panel_embed(interaction.guild),
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

        warnings = add_warning(user_id)

        try:

            await message.author.send(
                f"""⚠️ **אזהרה**

הודעה שלך נמחקה מכיוון שהיא הכילה קישור.

מספר האזהרות שלך: **{warnings}**"""
            )

        except:
            pass

        return

    await bot.process_commands(message)


# =========================
# STARTUP
# =========================

@bot.event
async def setup_hook():

    # Persistent views
    bot.add_view(TicketView())
    bot.add_view(TicketControlView())
    bot.add_view(RoleSelectionView())

    # ניקוי פקודות ישנות מהשרת
    bot.tree.clear_commands(
        guild=GUILD
    )

    # הוספת הפקודות הנוכחיות
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