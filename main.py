import os

import disnake
from disnake.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Укажите ID ролей, которым разрешено редактировать расписание
ALLOWED_ROLES = {828641723353137224, 731187000673173594}
OFFICER_ROLE_ID = 731187000673173594 # ID роли офицера

# Разрешенные дни недели
VALID_DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

# Загрузка токена бота
load_dotenv("token.env")

# Подключение к базе данных
conn = sqlite3.connect("schedule.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT UNIQUE,
    organizer_id INTEGER,
    start_time TEXT,
    gamemode TEXT
)
""")
conn.commit()

bot = commands.Bot(command_prefix=None, intents=disnake.Intents.default())
CHANNEL_ID = None  # Замените на ID канала, где будет отображаться расписание
schedule_message_id = None  # ID сообщения с расписанием


async def update_schedule(channel):
    global schedule_message_id
    cursor.execute("SELECT day, organizer_id, start_time, gamemode FROM schedule ORDER BY id")
    events = cursor.fetchall()

    event_dict = {day: "Свободно" for day in VALID_DAYS}

    for day, organizer_id, start_time, gamemode in events:
        event_dict[day] = f"**Кто занял:** <@{organizer_id}>\n**Время:** {start_time}\n**Гейммод:** {gamemode}"

    current_date = datetime.utcnow() + timedelta(hours=3)  # UTC+3
    current_week_of_month = (current_date.day - 1) // 7 + 1
    current_month = current_date.strftime("%B")

    embed = disnake.Embed(title=f"📅 Расписание на {current_week_of_month}-ю неделю {current_month}",
                          color=disnake.Color.dark_purple())
    embed.set_footer(text="For Alium by alexeyyt4/Футаба")

    for day in VALID_DAYS:
        embed.add_field(name=f"**{day}**", value=event_dict[day], inline=False)

    if schedule_message_id:
        try:
            message = await channel.fetch_message(schedule_message_id)
            await message.edit(embed=embed)
        except:
            sent_message = await channel.send(embed=embed)
            schedule_message_id = sent_message.id
    else:
        sent_message = await channel.send(embed=embed)
        schedule_message_id = sent_message.id


@bot.event
async def on_ready():
    print(f"Logging as {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)
    await update_schedule(channel)


@bot.slash_command(description="Добавить или обновить событие в расписании")
async def add_event(inter: disnake.ApplicationCommandInteraction, day: str = commands.Param(description="День недели"), start_time: str = commands.Param(description="Время начала события"), gamemode: str = commands.Param(description="Гейммод")):
    if not any(role.id in ALLOWED_ROLES for role in inter.author.roles):
        await inter.response.send_message("У вас нет прав для редактирования расписания.", ephemeral=True)
        return

    if day.capitalize() not in VALID_DAYS:
        await inter.response.send_message(
            "Некорректный день недели. Используйте: Понедельник, Вторник, Среда, Четверг, Пятница, Суббота, Воскресенье.",
            ephemeral=True)
        return

    cursor.execute("REPLACE INTO schedule (day, organizer_id, start_time, gamemode) VALUES (?, ?, ?, ?)",
                   (day.capitalize(), inter.author.id, start_time, gamemode))
    conn.commit()

    await inter.response.send_message(f"Событие обновлено на {day.capitalize()} в {start_time}. Гейммод: {gamemode}")
    channel = bot.get_channel(CHANNEL_ID)
    await update_schedule(channel)


@bot.slash_command(description="Отменить бронирование дня")
async def cancel_event(inter: disnake.ApplicationCommandInteraction, day: str = commands.Param(description="День недели")):
    if not any(role.id in ALLOWED_ROLES for role in inter.author.roles):
        await inter.response.send_message("У вас нет прав для редактирования расписания.", ephemeral=True)
        return

    if day.capitalize() not in VALID_DAYS:
        await inter.response.send_message(
            "Некорректный день недели. Используйте: Понедельник, Вторник, Среда, Четверг, Пятница, Суббота, Воскресенье.",
            ephemeral=True)
        return

    cursor.execute("SELECT organizer_id FROM schedule WHERE day = ?", (day.capitalize(),))
    row = cursor.fetchone()
    if row:
        organizer_id = row[0]
        if organizer_id != inter.author.id and not any(role.id == OFFICER_ROLE_ID for role in inter.author.roles):
            await inter.response.send_message("Вы не можете отменить бронирование, сделанное другим организатором.",
                                              ephemeral=True)
            return

        cursor.execute("DELETE FROM schedule WHERE day = ?", (day.capitalize(),))
        conn.commit()
        await inter.response.send_message(f"Бронирование на {day.capitalize()} отменено.")
        channel = bot.get_channel(CHANNEL_ID)
        await update_schedule(channel)
    else:
        await inter.response.send_message("На этот день нет бронирования.", ephemeral=True)


@tasks.loop(hours=1)
async def clear_schedule():
    now = datetime.utcnow() + timedelta(hours=3)  # UTC+3
    if now.weekday() == 0 and now.hour == 0:
        cursor.execute("DELETE FROM schedule")
        conn.commit()
        channel = bot.get_channel(CHANNEL_ID)
        await update_schedule(channel)


@clear_schedule.before_loop
async def before_clearing():
    await bot.wait_until_ready()


clear_schedule.start()

bot.run(os.getenv("BOT_TOKEN"))