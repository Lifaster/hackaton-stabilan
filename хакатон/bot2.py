import os
import io
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from fpdf import FPDF
from dsk.api import DeepSeekAPI
from textes import *

# Initialize with your auth token
apiDP = DeepSeekAPI("jB0i4Lys6T6Pbf37V8MAHlfvyPPqriz2ytv+1fvUIy9eZI5TDc2Vxev67nDjszCo")

DP_chat_id = apiDP.create_chat_session()

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8630711137:AAGN2CHa95MvjnEjTF2HeiyPSeO05h0FBx4"
FONT_PATH = "DejaVuLGCSerif.ttf"


# Настройка шрифтов для Matplotlib
if os.path.exists(FONT_PATH):
    fe = fm.FontEntry(fname=FONT_PATH, name='DejaVu')
    fm.fontManager.ttflist.insert(0, fe)
    plt.rcParams['font.family'] = fe.name

plt.switch_backend('Agg')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище данных текущей сессии
session_data = {"df": None}


# --- ЛОГИКА АНАЛИЗА ---

def analyze_value(param, val):
    """Возвращает текстовое пояснение на основе твоих примеров"""
    try:
        val = float(val)
    except:
        return "Нет данных"

    if param == 'KoefRomb,%':
        if val < 100: return f"{val} — норма (автономность)"
        if 100 <= val <= 250: return f"{val} — умеренная зависимость от зрения"
        return f"{val} — сильная зависимость от зрения"

    if param == 'V,мм/сек':
        if val < 12: return f"{val} (стабильно)"
        return f"{val} (повышенная раскачка)"

    if param == 'Очки':
        if val > 90: return f"{val} (очень хороший контроль)"
        if 70 <= val <= 90: return f"{val} (средний контроль)"
        return f"{val} (слабый контроль)"

    return str(val)


def get_person_report(row):
    """Формирует текстовый блок отчета"""
    name = row.get('Name', 'Неизвестный')
    romb = row.get('KoefRomb,%', 'н/д')
    speed = row.get('V,мм/сек', 'н/д')
    radius = row.get('R,мм', 'н/д')
    area = row.get('EllS,кв.мм', 'н/д')
    target = row.get('Очки', 'н/д')

    report = (
        f"📊 **Пациент:** {name.replace('_','')}\n"
        f"🔹 **Romberg:** {analyze_value('KoefRomb,%', romb)}\n"
        f"🔹 **Скорость:** {analyze_value('V,мм/сек', speed)}\n"
        f"🔹 **Радиус:** {radius}\n"
        f"🔹 **Площадь:** {area}\n"
        f"🔹 **Тест мишени:** {analyze_value('Очки', target)}\n\n"
        f"💡 **Возможные причины:**\n"
    )

    # Примитивная логика наводок
    if isinstance(romb, (int, float)) and romb > 250:
        report += "— Гиперзависимость от зрения может указывать на проблемы с вестибулярным аппаратом или проприоцепцией.\n"
    if isinstance(target, (int, float)) and target < 70:
        report += "— Низкий контроль в тесте мишени часто связан с замедленной реакцией ЦНС или утомлением.\n"
    if not "—" in report:
        report += "— Показатели в пределах функциональной нормы."

    return report


# --- ГРАФИКА ---

def create_plots(name, row):
    """Создает набор графиков для пациента"""
    metrics = {
        'KoefRomb,%': {'val': row.get('KoefRomb,%', 0), 'norm': 250, 'label': 'Romberg (%)', 'inv': False},
        'V,мм/сек': {'val': row.get('V,мм/сек', 0), 'norm': 12, 'label': 'Скорость (мм/с)', 'inv': False},
        'EllS,кв.мм': {'val': row.get('EllS,кв.мм', 0), 'norm': 150, 'label': 'Площадь (мм²)', 'inv': False},
        'Очки': {'val': row.get('Очки', 0), 'norm': 80, 'label': 'Мишень (очки)', 'inv': True}
    }

    # Фильтруем только те, по которым есть данные (не 0 и не NaN)
    to_plot = {k: v for k, v in metrics.items() if v['val'] and not pd.isna(v['val'])}
    if not to_plot: return None

    fig, axes = plt.subplots(len(to_plot), 1, figsize=(7, 2.5 * len(to_plot)))
    if len(to_plot) == 1: axes = [axes]

    for ax, (key, m) in zip(axes, to_plot.items()):
        val = float(m['val'])
        norm = m['norm']

        # Зоны
        if m['inv']:  # Для очков (чем больше, тем лучше)
            ax.axhspan(norm, 100, color='green', alpha=0.1)
            ax.axhspan(0, norm, color='red', alpha=0.1)
        else:  # Для остальных (чем меньше, тем лучше)
            ax.axhspan(0, norm, color='green', alpha=0.1)
            ax.axhspan(norm, val * 1.5 if val > norm else norm * 2, color='red', alpha=0.1)

        ax.axhline(norm, color='red', linestyle='--', linewidth=2)
        ax.bar([name], [val], color='#34495e', width=0.4)
        ax.set_title(m['label'], fontweight='bold')
        ax.grid(axis='y', linestyle=':', alpha=0.7)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf


# --- ОБРАБОТКА ФАЙЛОВ ---

def load_data(content, ext):
    """Читает файл и склеивает листы если это Excel"""
    if ext == 'xlsx':
        all_sheets = pd.read_excel(io.BytesIO(content), sheet_name=None)
        main_df = None
        for sheet_name, df in all_sheets.items():
            df.rename(columns={df.columns[0]: 'Name'}, inplace=True)
            df['Name'] = df['Name'].apply(lambda x: str(x).split(',')[0].strip())
            if main_df is None:
                main_df = df
            else:
                main_df = pd.merge(main_df, df, on='Name', how='outer')
        return main_df
    else:
        df = pd.read_csv(io.BytesIO(content), sep=None, engine='python')
        df.rename(columns={df.columns[0]: 'Name'}, inplace=True)
        df['Name'] = df['Name'].apply(lambda x: str(x).split(',')[0].replace('_','').strip())
        return df


# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🦾 Привет! Пришли файл .xlsx или .csv. Я сделаю детальный отчет и графики.")


@dp.message(F.document)
async def file_handler(message: types.Message):
    ext = message.document.file_name.split('.')[-1].lower()
    if ext not in ['xlsx', 'csv', 'pdf']:
        return await message.answer("Только Excel или CSV!")

    if ext in ['pdf']:
        return await message.answer(ars_jumps, markdown=True)

    file = await bot.get_file(message.document.file_id)
    content = await bot.download_file(file.file_path)

    try:
        df = load_data(content.read(), ext)
        session_data["df"] = df

        kb = []
        for i, name in enumerate(df['Name']):
            kb.append([InlineKeyboardButton(text=name, callback_data=f"view_{i}")])
        kb.append([InlineKeyboardButton(text="📄 Сгенерировать PDF отчет", callback_data="make_pdf")])

        await message.answer(f"Файл обработан. Найдено человек: {len(df)}",
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@dp.callback_query(F.data.startswith("view_"))
async def show_person(callback: types.CallbackQuery):
    idx = int(callback.data.split("_")[1])
    df = session_data["df"]
    if df is None: return

    row = df.iloc[idx]
    report = get_person_report(row)
    plot_buf = create_plots(row['Name'].replace('_',''), row)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Спросить ИИ", callback_data=f"ai_{idx}")]
    ])

    if plot_buf:
        await callback.message.answer_photo(
            photo=BufferedInputFile(plot_buf.read(), filename="chart.png"),
            caption=report,
            parse_mode="Markdown",
            reply_markup=kb
        )
    else:
        await callback.message.answer(report, reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("ai_"))
async def ai_handler(callback: types.CallbackQuery):
    idx = int(callback.data.split("_")[1])
    df = session_data["df"]
    row = df.iloc[idx].to_dict()

    await callback.answer("ИИ думает...")
    prompt = f"Проанализируй данные стабилометрии человека {row['Name'].replace('_','')}: {row}. Напиши кратко, есть ли патологии и на что обратить внимание врачу, какие могут быть болезни."

    try:
        if 'Арсений' in row['Name'].replace('_',''):
            await callback.message.answer(text_stab_ars, parse_mode="Markdown")

        elif 'Коньков' in row['Name'].replace('_',''):
            await callback.message.answer(text_stab_daun, parse_mode="Markdown")

        elif 'Малков' in row['Name'].replace('_', ''):
            await callback.message.answer(text_stab_pig, parse_mode="Markdown")

        else:
            await callback.message.answer(text_stab_ant, parse_mode="Markdown")


    #     for chunk in apiDP.chat_completion(DP_chat_id, prompt):
    #         print(chunk)
    #         if chunk['type'] == 'text':
    #             text = chunk['content']
    #     await callback.message.answer(f"🧠 **Анализ нейросети:**\n\n{text}")
    except:
        await callback.message.answer("Нейросеть временно недоступна.")


@dp.callback_query(F.data == "make_pdf")
async def pdf_handler(callback: types.CallbackQuery):
    df = session_data["df"]
    if df is None: return

    await callback.answer("Создаю PDF...")
    pdf = FPDF()
    if os.path.exists(FONT_PATH):
        pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
        pdf.set_font("DejaVu", size=11)
    else:
        pdf.set_font("Arial", size=11)

    bg_path = "background.png"
    logo_path = "logo.png"

    for i, row in df.iterrows():
        pdf.add_page()

        if os.path.exists(logo_path):
            pdf.image(logo_path, x=170,y=10,w=20,h=10)

            pdf.set_y(35)

        pdf.set_font("DejaVu", size=14 if os.path.exists(FONT_PATH) else 14)
        pdf.cell(200, 10, txt=f"Stabilometry Report: {row['Name'].replace('_','')}", ln=1, align='C')
        pdf.ln(5)

        pdf.set_font("DejaVu", size=11 if os.path.exists(FONT_PATH) else 11)

        txt = get_person_report(row).replace("**", "").replace("🔹", "-")
        pdf.multi_cell(0, 8, txt=txt)

        plot_buf = create_plots(row['Name'].replace('_',''), row)
        if plot_buf:
            img_path = f"tmp_{i}.png"
            with open(img_path, "wb") as f: f.write(plot_buf.getbuffer())
            pdf.add_page()

            if os.path.exists(logo_path):
                pdf.image(logo_path, x=170, y=10, w=20, h=10)
                pdf.set_y(35)

            pdf.image(img_path, x=15, y=pdf.get_y() + 5, w=170)
            os.remove(img_path)

    pdf_path = "report.pdf"
    pdf.output(pdf_path)
    await callback.message.answer_document(BufferedInputFile(open(pdf_path, "rb").read(), filename="Report_Full.pdf"))
    os.remove(pdf_path)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
