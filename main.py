import disnake
from disnake.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta

# Укажите ID ролей, которым разрешено редактировать расписание
ALLOWED_ROLES = {1169723413443661984}  # Замените на свои

# Разрешенные дни недели
VALID_DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

# Подключение к базе данных
conn = sqlite3.connect("schedule.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT UNIQUE,
    organizer TEXT,
    start_time TEXT,
    gamemode TEXT
)
""")
conn.commit()

bot = commands.Bot(intents=disnake.Intents.default())


# Команда для добавления события в расписание
@bot.slash_command(description="Добавить событие в расписание")
async def add_event(inter: disnake.ApplicationCommandInteraction, day: str, start_time: str, gamemode: str):
    if not any(role.id in ALLOWED_ROLES for role in inter.author.roles):
        await inter.response.send_message("У вас нет прав для редактирования расписания.", ephemeral=True)
        return

    if day.capitalize() not in VALID_DAYS:
        await inter.response.send_message(
            "Некорректный день недели. Используйте: Понедельник, Вторник, Среда, Четверг, Пятница, Суббота, Воскресенье.",
            ephemeral=True)
        return

    cursor.execute("SELECT * FROM schedule WHERE day = ?", (day.capitalize(),))
    existing_event = cursor.fetchone()

    if existing_event:
        await inter.response.send_message(f"День {day.capitalize()} уже занят.", ephemeral=True)
        return

    cursor.execute("INSERT INTO schedule (day, organizer, start_time, gamemode) VALUES (?, ?, ?, ?)",
                   (day.capitalize(), inter.author.display_name, start_time, gamemode))
    conn.commit()
    await inter.response.send_message(f"Событие добавлено на {day.capitalize()} в {start_time}. Гейммод: {gamemode}")


# Команда для просмотра расписания в Embed-формате
@bot.slash_command(description="Показать расписание на неделю")
async def show_schedule(inter: disnake.ApplicationCommandInteraction):
    if not any(role.id in ALLOWED_ROLES for role in inter.author.roles):
        await inter.response.send_message("У вас нет прав для редактирования расписания.", ephemeral=True)
        return

    cursor.execute("SELECT day, organizer, start_time, gamemode FROM schedule ORDER BY id")
    events = cursor.fetchall()

    event_dict = {day: "Свободно" for day in VALID_DAYS}  # Заполняем все дни как "Свободно"

    for day, organizer, start_time, gamemode in events:
        event_dict[day] = f"**Кто занял:** {organizer}\n**Время:** {start_time}\n**Гейммод:** {gamemode}"

    # Текущая неделя и месяц
    current_date = datetime.utcnow() + timedelta(hours=3)  # UTC+3
    current_week_of_month = (current_date.day - 1) // 7 + 1  # Вычисление недели месяца
    current_month = (datetime.utcnow() + timedelta(hours=3)).strftime("%B")  # Текущий месяц

    embed = disnake.Embed(title=f"📅 Расписание на {current_week_of_month}-ю неделю {current_month}",
                          color=disnake.Color.dark_purple())
    embed.set_footer(text="For Alium by Futaba")

    for day in VALID_DAYS:
        embed.add_field(name=f"**{day}**", value=event_dict[day], inline=False)

    await inter.response.send_message(embed=embed)


# Очистка расписания по понедельникам в полночь
@tasks.loop(hours=1)
async def clear_schedule():
    now = datetime.utcnow() + timedelta(hours=3)  # UTC+3
    if now.weekday() == 0 and now.hour == 0:  # Понедельник, 00:00
        cursor.execute("DELETE FROM schedule")
        conn.commit()


@clear_schedule.before_loop
async def before_clearing():
    await bot.wait_until_ready()


clear_schedule.start()


bot.run("")
