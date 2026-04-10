from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from aiogram import Bot, Dispatcher, types, enums
from keyboards import *
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from aiogram.client.default import DefaultBotProperties
import json
from datetime import datetime, timedelta
import time
import os
import asyncio


TOKEN = "8630711137:AAGN2CHa95MvjnEjTF2HeiyPSeO05h0FBx4"
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

State = {}
# Примеры
#State = {'{id}': {'{task.name}': '{data}'}}
#State = {'12334': {'task_add': 'data'}}

pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuLGCSerif.ttf'))


# работа с файлом json (ака датабаза)
def get_file(a=None, b=None):
    with open('base.json', 'r', encoding='cp1251') as f:
        text = json.load(f)

    if a == None:
        return text

    elif a == 'numCh':
        return len(text[b].keys())

    elif a == 'chat':
        return text[b]


def edit_file(a):
    with open('base.json', 'w', encoding='cp1251') as f:
        json.dump(a, f)
######


def load_stabilan(file):

    xls = pd.ExcelFile(file)

    data = {}

    sheets = xls.sheet_names

    def safe_read(name):
        return pd.read_excel(xls, name) if name in sheets else None

    data["romberg"] = safe_read("Допусковый контроль")
    data["open"] = safe_read("Ог")
    data["closed"] = safe_read("зг")
    data["target_signal"] = safe_read("Мишень стаб.сигнал")
    data["target"] = safe_read("Мишень")

    return data


# тут базовые пояснение к разным хуйням (см. имя функции после _)
def analyze_romberg(df):

    results = []

    if df is None:
        return results

    for _, row in df.iterrows():

        romb = row.get("KoefRomb,%", None)
        name = row.iloc[0]

        if romb is None:
            continue

        if romb < 150:
            status = "норма"
        elif romb < 250:
            status = "умеренная зависимость от зрения"
        else:
            status = "сильная зависимость от зрения"

        results.append((name, romb, status))

    return results


def analyze_posture(df):

    results = []

    if df is None:
        return results

    for _, row in df.iterrows():

        speed = row.get("V,мм/сек", None)
        radius = row.get("R,мм", None)
        area = row.get("EllS,кв.мм", None)

        notes = []

        if speed and speed > 20:
            notes.append("повышенная скорость стабилизации")

        if radius and radius > 10:
            notes.append("увеличенная амплитуда колебаний")

        if area and area > 200:
            notes.append("большая площадь стабилограммы")

        results.append({
            "speed": speed,
            "radius": radius,
            "area": area,
            "notes": notes
        })

    return results


def analyze_target(df):

    results = []

    if df is None:
        return results

    for _, row in df.iterrows():

        score = row.get("Очки", None)

        if score is None:
            continue

        if score > 90:
            status = "очень хороший контроль"
        elif score > 70:
            status = "нормальный контроль"
        else:
            status = "слабый контроль"

        results.append((score, status))

    return results
########


def plot_heatmap(df):

    if "MO(x),мм" not in df.columns:
        return None

    x = df["MO(x),мм"]
    y = df["MO(y),мм"]

    plt.figure()

    plt.hexbin(
        x,
        y,
        gridsize=30
    )

    plt.xlabel("X")
    plt.ylabel("Y")

    plt.title("Pressure heatmap")

    path = "heatmap.png"

    plt.savefig(path)

    plt.close()

    return path


# создание графиков
def create_graphs(data):

    paths = []

    romberg = data["romberg"]

    if romberg is not None:
        plt.figure()

        values = romberg["KoefRomb,%"]
        names = romberg.iloc[:, 0]

        plt.bar(names, values)

        # линия нормы
        plt.axhline(
            y=150,
            linestyle="--",
            linewidth=2,
            label="Норма"
        )

        # сетка
        plt.grid(
            axis="y",
            linestyle="--",
            alpha=0.6
        )

        plt.title("Romberg coefficient")
        plt.ylabel("KoefRomb")
        plt.xticks(rotation=45)

        plt.legend()

        plt.savefig("romberg.png")

        plt.close()

        paths.append("romberg.png")

    open_df = data["open"]

    if open_df is not None and "V,мм/сек" in open_df:
        plt.figure()

        values = open_df["V,мм/сек"]

        plt.bar(range(len(values)), values)

        plt.axhline(
            y=20,
            linestyle="--",
            linewidth=2,
            label="Норма"
        )

        plt.grid(axis="y", linestyle="--", alpha=0.6)

        plt.title("Stabilization speed")
        plt.ylabel("mm/sec")

        plt.legend()

        plt.savefig("speed.png")
        plt.close()
        paths.append("speed.png")

    return paths
##########


# Стабилограмма
def plot_cop(df):

    if df is None:
        return None

    if "MO(x),мм" not in df.columns or "MO(y),мм" not in df.columns:
        return None

    x = df["MO(x),мм"]
    y = df["MO(y),мм"]

    plt.figure()

    plt.plot(x, y)

    plt.xlabel("X (mm)")
    plt.ylabel("Y (mm)")

    plt.title("Center of Pressure trajectory")

    path = "cop.png"

    plt.savefig(path)
    plt.close()

    return path
########


# Общая функция всего анализа
def generate_report(data):
    styles = getSampleStyleSheet()

    styles['BodyText'].fontName = 'DejaVuSans'
    styles['Title'].fontName = 'DejaVuSans'

    elements = []

    elements.append(Paragraph("Stabilometry Report", styles["Title"]))
    elements.append(Spacer(1,20))

    romberg = analyze_romberg(data["romberg"])
    posture = analyze_posture(data["open"])
    target = analyze_target(data["target"])

    for i in range(len(romberg)):

        text = f"""Пациент: {romberg[i][0]} <br/>Romberg: {romberg[i][1]} — {romberg[i][2]} <br/>"""

        if i < len(posture):

            p = posture[i]

            text += f"""
Скорость стабилизации: {p['speed']} <br/>
Радиус: {p['radius']} <br/>
Площадь: {p['area']} <br/>
"""

        if i < len(target):

            t = target[i]

            text += f"""
Тест мишени: {t[0]} баллов ({t[1]}) <br/>
"""

        elements.append(Paragraph(text, styles["BodyText"]))
        elements.append(Spacer(1,20))

    graphs = create_graphs(data)

    cop = plot_cop(data["open"])
    heatmap = plot_heatmap(data["open"])

    if cop:
        graphs.append(cop)

    if heatmap:
        graphs.append(heatmap)

    for g in graphs:
        elements.append(Image(g, width=400, height=300))
        elements.append(Spacer(1,20))

    report_path = "report.pdf"

    doc = SimpleDocTemplate(report_path)
    doc.build(elements)

    return report_path



@dp.message(Command("start"))
async def start(message: types.Message):
    await menu(message)


@dp.message(Command("menu"))
async def menu(message: types.Message):
    kb = menuKeyboard

    await bot.send_message(message.chat.id, "Привет👋, с помощью кнопок ниже выбери нужное действие⬇", reply_markup=kb)


async def handle_file(message: types.Message):

    file = await bot.get_file(message.document.file_id)
    path = file.file_path
    downloaded = await bot.download_file(path)

    with open("data.xlsx", "wb") as f:
        f.write(downloaded.read())

    df = pd.read_excel("data.xlsx")

    # график
    plt.figure()

    plt.bar(df["Допусковый_контроль"], df["KoefRomb,%"])

    plt.xticks(rotation=45)
    plt.ylabel("KoefRomb")

    plt.savefig("graph.png")

    await message.answer_photo(open("graph.png","rb"))


async def stab_anal(message: types.Message):
    file = await bot.get_file(message.document.file_id)

    downloaded = await bot.download_file(file.file_path)

    with open(f"stab_{message.from_user.id}.xlsx", "wb") as f:
        f.write(downloaded.read())

    data = load_stabilan(f"stab_{message.from_user.id}.xlsx")

    report = generate_report(data)

    await message.answer_document(FSInputFile(report))


@dp.message()
async def on_mes(message: types.Message):
    global State

    if State.get(str(message.from_user.id), None):

        if list(State[str(message.from_user.id)].keys())[0].startswith('stab'):
            await stab_anal(message)


@dp.callback_query()
async def callback(callback_query):
    global State
    data = callback_query.data

    if data == 'stabilan':
        await callback_query.message.answer("Отправь мне табличку exel📗")
        State[str(callback_query.from_user.id)] = {'stab_document_exel': None}


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

