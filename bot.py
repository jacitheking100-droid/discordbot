 import discord
from discord.ext import commands
import re
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

LINK_REGEX = re.compile(
    r"(https?://\S+|www\.\S+|discord\.gg/\S+|discord\.com/invite/\S+)",
    re.IGNORECASE
)

TICKET_CATEGORY = "Tickets"
STAFF_ROLE = "Staff"


@bot.event
async def on_ready():
    print(f"הבוט מחובר בתור {bot.user}")
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if LINK_REGEX.search(message.content):
        try:
            await message.delete()

            try:
                await message.author.send(
                    "🚫 **קישור נחסם**\n\n"
                    "הודעתך נמחקה מכיוון ששליחת קישורים "
                    "אינה מותרת בשרת.\n\n"
                    "שלח את ההודעה מחדש ללא קישור."
                )
            except discord.Forbidden:
                pass

        except discord.Forbidden:
            print("אין לבוט הרשאה למחוק הודעות.")

    await bot.process_commands(message)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="פתח טיקט",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="open_ticket"
    )
    async def open_ticket(self, interaction, button):

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
            category = await guild.create_category(TICKET_CATEGORY)

        staff = discord.utils.get(
            guild.roles,
            name=STAFF_ROLE
        )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        if staff:
            overwrites[staff] = discord.PermissionOverwrite(
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
                "צוות השרת יטפל בפנייה שלך בהקדם.\n\n"
                "**כדי לקבל מענה מהיר:**\n"
                "• הסבר מה הבעיה\n"
                "• צרף מידע רלוונטי\n"
                "• המתן בסבלנות למענה הצוות"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text="הפקח פוקסי • מערכת התמיכה"
        )

        await channel.send(
            content=(
                user.mention
                + (f" {staff.mention}" if staff else "")
            ),
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
    async def close_ticket(self, interaction, button):

        await interaction.response.send_message(
            "🔒 הטיקט ייסגר בעוד 5 שניות..."
        )

        await asyncio.sleep(5)
        await interaction.channel.delete()


@bot.command()
@commands.has_permissions(administrator=True)
async def ticket(ctx):

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


@ticket.error
async def ticket_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ אין לך הרשאה להשתמש בפקודה הזאת.")


bot.run(os.environ["DISCORD_TOKEN"])
