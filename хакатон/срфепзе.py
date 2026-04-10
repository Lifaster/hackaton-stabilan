import os
import pandas as pd
import matplotlib.pyplot as plt

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

os.makedirs("uploads", exist_ok=True)
os.makedirs("graphs", exist_ok=True)
os.makedirs("reports", exist_ok=True)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)


# =========================
# Чтение стабилан файла
# =========================

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


# =========================
# Анализ Ромберга
# =========================

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


# =========================
# Анализ стабилизации
# =========================

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


# =========================
# Анализ мишени
# =========================

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


# =========================
# Построение графиков
# =========================

def create_graphs(data):

    paths = []

    romberg = data["romberg"]

    if romberg is not None:

        plt.figure()

        plt.bar(romberg.iloc[:,0], romberg["KoefRomb,%"])

        plt.title("Romberg coefficient")
        plt.xticks(rotation=45)

        path = "graphs/romberg.png"
        plt.savefig(path)

        plt.close()

        paths.append(path)

    open_df = data["open"]

    if open_df is not None and "V,мм/сек" in open_df:

        plt.figure()

        plt.bar(range(len(open_df)), open_df["V,мм/сек"])

        plt.title("Stabilization speed")

        path = "graphs/speed.png"
        plt.savefig(path)

        plt.close()

        paths.append(path)

    return paths


# =========================
# Стабилограмма
# =========================

def plot_cop(df):

    if df is None:
        return None

    if "MO(x),мм" not in df or "MO(y),мм" not in df:
        return None

    x = df["MO(x),мм"]
    y = df["MO(y),мм"]

    plt.figure()

    plt.plot(x, y)

    plt.xlabel("X (mm)")
    plt.ylabel("Y (mm)")

    plt.title("Center of Pressure trajectory")

    path = "graphs/cop.png"

    plt.savefig(path)
    plt.close()

    return path


# =========================
# Генерация отчета
# =========================

def generate_report(data):

    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("Stabilometry Report", styles["Title"]))
    elements.append(Spacer(1,20))

    romberg = analyze_romberg(data["romberg"])
    posture = analyze_posture(data["open"])
    target = analyze_target(data["target"])

    for i in range(len(romberg)):

        text = f"""
Пациент: {romberg[i][0]} <br/>
Romberg: {romberg[i][1]} — {romberg[i][2]} <br/>
"""

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

    if cop:
        graphs.append(cop)

    for g in graphs:
        elements.append(Image(g, width=400, height=300))
        elements.append(Spacer(1,20))

    report_path = "reports/report.pdf"

    doc = SimpleDocTemplate(report_path)
    doc.build(elements)

    return report_path


# =========================
# Telegram обработчик
# =========================

@dp.message_handler(content_types=['document'])
async def handle_file(message: types.Message):

    file = await bot.get_file(message.document.file_id)

    downloaded = await bot.download_file(file.file_path)

    path = "uploads/input.xlsx"

    with open(path, "wb") as f:
        f.write(downloaded.read())

    data = load_stabilan(path)

    report = generate_report(data)

    await message.answer_document(open(report, "rb"))


if __name__ == "__main__":

    print("Bot started")

    executor.start_polling(dp)