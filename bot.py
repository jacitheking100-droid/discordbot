# =========================
# ADD XP
# =========================

@bot.tree.command(
    name="addxp",
    description="הוסף XP למשתמש"
)
@app_commands.describe(
    member="המשתמש שיקבל את ה-XP",
    amount="כמות ה-XP להוסיף"
)
async def addxp_command(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    if amount <= 0:

        await interaction.response.send_message(
            "❌ כמות ה-XP חייבת להיות גדולה מ-0.",
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

    embed = discord.Embed(
        title="✅ XP נוסף",
        description=(
            f"👤 משתמש: {member.mention}\n"
            f"➕ נוסף: **{amount:,} XP**\n"
            f"⭐ XP נוכחי: **{new_xp:,}**"
        ),
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================
# REMOVE XP
# =========================

@bot.tree.command(
    name="removexp",
    description="הסר XP ממשתמש"
)
@app_commands.describe(
    member="המשתמש שממנו יורד XP",
    amount="כמות ה-XP להסיר"
)
async def removexp_command(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    if amount <= 0:

        await interaction.response.send_message(
            "❌ כמות ה-XP חייבת להיות גדולה מ-0.",
            ephemeral=True
        )

        return

    current_xp = get_xp(
        member.id
    )

    if current_xp < amount:

        await interaction.response.send_message(
            f"❌ אין ל-{member.mention} מספיק XP.\n"
            f"⭐ יש לו כרגע: **{current_xp:,} XP**",
            ephemeral=True
        )

        return

    remove_xp(
        member.id,
        amount
    )

    new_xp = get_xp(
        member.id
    )

    embed = discord.Embed(
        title="➖ XP הוסר",
        description=(
            f"👤 משתמש: {member.mention}\n"
            f"➖ הוסר: **{amount:,} XP**\n"
            f"⭐ XP נוכחי: **{new_xp:,}**"
        ),
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================
# SET XP
# =========================

@bot.tree.command(
    name="setxp",
    description="קבע כמות XP למשתמש"
)
@app_commands.describe(
    member="המשתמש שאת ה-XP שלו משנים",
    amount="כמות ה-XP החדשה"
)
async def setxp_command(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if not is_staff(interaction.user):

        await interaction.response.send_message(
            "❌ אין לך הרשאה להשתמש בפקודה הזאת.",
            ephemeral=True
        )

        return

    if amount < 0:

        await interaction.response.send_message(
            "❌ אי אפשר להגדיר XP שלילי.",
            ephemeral=True
        )

        return

    ensure_user(
        member.id
    )

    cursor.execute(
        """
        UPDATE users
        SET xp = ?
        WHERE user_id = ?
        """,
        (
            amount,
            member.id
        )
    )

    db.commit()

    embed = discord.Embed(
        title="⭐ XP עודכן",
        description=(
            f"👤 משתמש: {member.mention}\n"
            f"📊 XP חדש: **{amount:,}**"
        ),
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed
    )