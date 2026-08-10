import asyncio, logging, sys, random, json, os, re, urllib.parse
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
import requests

try:
    from config import (
        BOT_TOKEN, API_KEYS, TELEGRAM_USERNAME, WHATSAPP_NUMBER,
        VK_USERNAME, INSTAGRAM_USERNAME, TIKTOK_USERNAME,
        SESSION_NAME, SESSION_PRICE, ADMIN_ID
    )
except ImportError:
    print("❌ config.py не найден!")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

(STEP_START, STEP_HONESTY, STEP_BIRTH, STEP_SPHERE, STEP_DETAIL,
 STEP_DESCRIBE, STEP_AI_DIALOG, STEP_DIAGNOSTIC, STEP_FINAL) = range(9)

user_sessions = {}
STATS_FILE = "stats.json"


def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"started": 0, "completed": 0, "booked": 0, "sources": {}}


def save_stats(s):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


stats = load_stats()

MISSIONS = {
    1: {"qualities": ["Лидерство", "Умение начинать новое", "Независимость"],
        "shadow": "Вы — лидер. Вы привыкли всё тащить на себе. Это истощает.",
        "description": "Число 1 — это энергия Солнца. Вы пришли быть первым, вести за собой, начинать новое. Ваша сила — в умении действовать самостоятельно и вдохновлять других."},
    2: {"qualities": ["Эмпатия", "Умение объединять", "Интуиция"],
        "shadow": "Вы тонко чувствуете людей. Но забыли о себе.",
        "description": "Число 2 — это энергия Луны. Вы пришли объединять людей, чувствовать их, создавать гармонию. Ваша сила — в тонкой интуиции и умении слышать то, что не говорят вслух."},
    3: {"qualities": ["Оптимизм", "Творчество", "Лёгкость"],
        "shadow": "Идей много — реализации ноль. Вы распыляетесь.",
        "description": "Число 3 — это энергия Юпитера. Вы пришли творить, радовать, вдохновлять. Ваша сила — в умении видеть возможности там, где другие видят преграды."},
    4: {"qualities": ["Ответственность", "Системность", "Надёжность"],
        "shadow": "Вы всё контролируете. Жизнь — список обязанностей.",
        "description": "Число 4 — это энергия Земли. Вы пришли строить, создавать системы, быть опорой. Ваша сила — в устойчивости и умении доводить до конца."},
    5: {"qualities": ["Жажда свободы", "Жажда опыта", "Любовь к переменам"],
        "shadow": "Вы бежите от проблем. Источник внутри.",
        "description": "Число 5 — это энергия Меркурия. Вы пришли за опытом, свободой и знаниями. Ваша сила — в адаптивности и умении учиться на ходу."},
    6: {"qualities": ["Забота", "Служение", "Тепло"],
        "shadow": "Вы отдаёте туда, где не возвращается.",
        "description": "Число 6 — это энергия Венеры. Вы пришли любить, заботиться, создавать уют. Ваша сила — в умении согревать сердца и создавать пространство, где другим хорошо."},
    7: {"qualities": ["Анализ", "Мудрость", "Умение видеть суть"],
        "shadow": "Вы застряли в анализе. Действий нет.",
        "description": "Число 7 — это энергия Сатурна. Вы пришли за мудростью и пониманием глубины. Ваша сила — в умении видеть суть там, где другие видят только поверхность."},
    8: {"qualities": ["Управление ресурсами", "Масштабирование", "Сила"],
        "shadow": "Конфликт: деньги или смысл.",
        "description": "Число 8 — это энергия Урана. Вы пришли управлять, масштабировать, создавать изобилие. Ваша сила — в умении соединять материальное и духовное."},
    9: {"qualities": ["Мудрость", "Завершение циклов", "Помощь другим"],
        "shadow": "Вы решаете чужие проблемы, забывая о себе.",
        "description": "Число 9 — это энергия Нептуна. Вы пришли служить, помогать, завершать. Ваша сила — в мудрости и умении видеть картину целиком."}
}

SYSTEM_PROMPT = """Ты — ассистент психолога-диагноста с очень тёплым, поддерживающим тоном. Ты говоришь с человеком, который пришёл с болью, усталостью и надеждой. Твоя задача — не просто выдать информацию, а дать человеку почувствовать, что его услышали, поняли и приняли.

Говори мягко, бережно, но уверенно. Без оценок и диагнозов. С уважением к опыту человека.

Структура ответа:

🌿 Я очень внимательно прочитал(а) то, что вы написали. Спасибо, что поделились. Я понимаю, как непросто бывает говорить о таких вещах.

Вы пишете: «{quote}». И я слышу в этих словах не просто описание ситуации. Я слышу усталость, растерянность и — одновременно — большое желание что-то изменить.

У вашей миссии есть удивительные стороны. Вам даны особые качества:
✔️ {q1}
✔️ {q2}
✔️ {q3}

Но я знаю, что у каждой миссии есть и теневая сторона. То, что иногда причиняет боль. {shadow}

И мне очень важно, чтобы вы знали: это не ваша вина. Вы не «сломаны» и не «неправильны». Вы просто живёте по сценарию, который когда-то был сформирован — и который теперь можно изменить.

Ваша ситуация не случайна. Она не возникла из ниоткуда. У неё есть конкретная причина. И эта причина — не вы сами. Это определённый механизм, который можно найти и трансформировать.

Вы спрашиваете, что делать. И я хочу сказать вам самое главное: всё можно изменить. То, что происходит сейчас — это не приговор и не судьба. Это точка, с которой начинается ваш путь к настоящей свободе и пониманию себя."""


class KeyPool:
    def __init__(self, keys):
        self.keys = [k.strip() for k in keys if k and k.strip()]
        self.fails = {k: 0 for k in self.keys}
        self.disabled = set()

    def get_key(self):
        available = [k for k in self.keys if k not in self.disabled]
        if not available:
            self.disabled.clear()
            available = list(self.keys)
        return random.choice(available) if available else None

    def mark_fail(self, key):
        self.fails[key] = self.fails.get(key, 0) + 1
        if self.fails[key] >= 3:
            self.disabled.add(key)


key_pool = KeyPool(API_KEYS)


def calculate_mission(d):
    d = re.sub(r'\D', '', d)
    if not d:
        return None
    t = sum(int(x) for x in d)
    while t > 9 and t not in (11, 22, 33):
        t = sum(int(x) for x in str(t))
    if t in (11, 22, 33):
        t = sum(int(x) for x in str(t))
    return t if t <= 9 else (t % 10 + t // 10)


async def ask_ai(prompt):
    key = key_pool.get_key()
    if not key:
        return None
    try:
        resp = await asyncio.to_thread(requests.post, "https://openrouter.ai/api/v1/chat/completions",
                                       headers={"Authorization": f"Bearer {key}",
                                                "Content-Type": "application/json"},
                                       json={"model": "openai/gpt-3.5-turbo",
                                             "messages": [{"role": "user", "content": prompt}],
                                             "max_tokens": 900}, timeout=15)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            key_pool.mark_fail(key)
            return None
    except:
        key_pool.mark_fail(key)
        return None


def gen_msg(u):
    return (
        f"Здравствуйте, ЛюдМила!\nЯ прошёл(прошла) бот «Ваша Точка Разворота».\nГотов(а) к сессии «{SESSION_NAME}».\n\n"
        f"📅 {u.get('birth', '—')}\n🌿 Миссия: {u.get('mission', '—')}\n🎯 Сфера: {u.get('sphere', '—')}\n"
        f"📝 Запрос: {u.get('request', '—')}\n\nОзнакомлен(а) с форматом и стоимостью. Готов(а) записаться.")


async def stats_cmd(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌")
        return
    t = f"📊 Статистика:\n\n👥 Начали: {stats['started']}\n✅ Дошли: {stats['completed']}\n🚀 Записались: {stats['booked']}\n\n📱 Источники:\n"
    for s, c in stats.get("sources", {}).items():
        t += f"  • {s}: {c}\n"
    await update.message.reply_text(t)


async def start(update, context):
    uid = update.effective_user.id
    src = context.args[0] if context.args else "прямой"
    user_sessions[uid] = {"source": src}
    stats["started"] += 1
    stats["sources"][src] = stats["sources"].get(src, 0) + 1
    save_stats(stats)
    await update.message.reply_text(
        "🌿 ВАША ТОЧКА РАЗВОРОТА\n\nИногда достаточно увидеть одну причину, чтобы жизнь начала меняться.\n\nЗдравствуйте! Я ЛюдМила Мамай — психолог и автор метода «Формула решений™».\n\nЗдесь вы сможете понять, что происходит сейчас, увидеть глубинную причину и заметить повторяющийся сценарий.\n\nГотовы увидеть свою Точку Разворота?",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌱 НАЧАТЬ", callback_data="start_diag")]]))
    return STEP_START


async def step_honesty(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🌿 Один важный вопрос\n\nГотовы увидеть то, что действительно влияет на вашу жизнь, даже если ответ окажется неожиданным?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, я готов(а)", callback_data="honest_yes")],
            [InlineKeyboardButton("🤍 Пока просто разобраться", callback_data="honest_maybe")]]))
    return STEP_HONESTY


async def handle_honesty(update, context):
    q = update.callback_query
    await q.answer()
    m = await q.edit_message_text("⏳ Анализирую…")
    await asyncio.sleep(2)
    await m.delete()
    t = "Отлично. Отвечайте как чувствуете.\n\n👇 Начинаем." if q.data == "honest_yes" else "Нормально. Отвечайте как чувствуете.\n\n👇 Продолжим."
    await q.message.reply_text(t,
                               reply_markup=InlineKeyboardMarkup(
                                   [[InlineKeyboardButton("➡️ Далее", callback_data="goto_birth")]]))
    return STEP_BIRTH


async def step_birth(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📅 Напишите полную дату рождения:\n\nФормат: дд.мм.гггг\nНапример: 20.07.2001")
    return STEP_BIRTH


async def handle_birth(update, context):
    d = update.message.text.strip()

    if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', d):
        await update.message.reply_text("❌ Неверный формат. Используйте дд.мм.гггг\nНапример: 20.07.2001")
        return STEP_BIRTH

    parts = d.split('.')
    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])

    if month < 1 or month > 12:
        await update.message.reply_text("❌ Месяц должен быть от 1 до 12")
        return STEP_BIRTH

    days_in_month = {1: 31, 2: 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                     3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}

    if day < 1 or day > days_in_month[month]:
        await update.message.reply_text(f"❌ В {month}-м месяце не может быть {day} дней")
        return STEP_BIRTH

    if year < 1940 or year > 2015:
        await update.message.reply_text("❌ Год должен быть от 1940 до 2015")
        return STEP_BIRTH

    try:
        birth_date = datetime(year, month, day)
        if birth_date > datetime.now():
            await update.message.reply_text("❌ Дата рождения не может быть в будущем")
            return STEP_BIRTH
    except ValueError:
        await update.message.reply_text("❌ Такой даты не существует")
        return STEP_BIRTH

    uid = update.effective_user.id
    m = calculate_mission(d)
    user_sessions[uid].update({"birth": d, "mission": m})
    msg = await update.message.reply_text("⏳ Анализирую дату…")
    await asyncio.sleep(2)
    await msg.delete()
    
    # Показываем выбор проблем
    await update.message.reply_text(
        "Благодарю!\n\n✔️ Дата получена.\n\nЧто вас сейчас беспокоит? Выберите из списка или опишите сами:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("😔 Усталость, нет сил", callback_data="problem_Усталость")],
            [InlineKeyboardButton("💔 Отношения, расставание", callback_data="problem_Отношения")],
            [InlineKeyboardButton("💰 Деньги, долги", callback_data="problem_Деньги")],
            [InlineKeyboardButton("😰 Страх будущего", callback_data="problem_Страх")],
            [InlineKeyboardButton("🔄 Повторяющийся сценарий", callback_data="problem_Сценарий")],
            [InlineKeyboardButton("😤 Обида, злость", callback_data="problem_Обида")],
            [InlineKeyboardButton("🤷 Потеря себя, не знаю чего хочу", callback_data="problem_Потеря")],
            [InlineKeyboardButton("✍️ Описать свою проблему", callback_data="problem_custom")]
        ]))
    return STEP_SPHERE


async def handle_problem(update, context):
    """Обработка выбора проблемы из списка"""
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "problem_custom":
        await q.edit_message_text(
            "Опишите свою ситуацию своими словами.\n\nЧто происходит и что хотите изменить?\n\n(2–5 предложений)")
        return STEP_DESCRIBE

    problem = q.data.replace("problem_", "")
    user_sessions[uid]["problem"] = problem
    user_sessions[uid]["request"] = problem

    msg = await q.edit_message_text("⏳ Анализирую ваш запрос…")
    await asyncio.sleep(2)
    await msg.delete()

    prompt = f"""Ты — очень тёплый, эмпатичный психолог. Человека беспокоит: "{problem}"

Ты чувствуешь его состояние. Ответь ему с теплотой и пониманием. Сначала одной короткой фразой вырази поддержку и понимание (например: "Я слышу вас...", "Это действительно непросто..."). Потом задай ОДИН мягкий уточняющий вопрос, чтобы лучше понять его ситуацию.

Будь как добрый друг, который действительно хочет выслушать и поддержать. Не давай советов. Говори с теплотой."""

    question = await ask_ai(prompt)
    if not question:
        question = "Я слышу вас. Расскажите подробнее, что вы чувствуете в этой ситуации? Я хочу понять вас лучше."

    await q.message.reply_text(question)
    return STEP_AI_DIALOG


async def step_sphere(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("🌿 Что сейчас для вас важнее всего?",
                                                  reply_markup=InlineKeyboardMarkup([
                                                      [InlineKeyboardButton("💰 Деньги и доход",
                                                                            callback_data="sphere_Деньги")],
                                                      [InlineKeyboardButton("❤️ Отношения",
                                                                            callback_data="sphere_Отношения")],
                                                      [InlineKeyboardButton("🚀 Работа",
                                                                            callback_data="sphere_Работа")],
                                                      [InlineKeyboardButton("🌿 Состояние",
                                                                            callback_data="sphere_Состояние")],
                                                      [InlineKeyboardButton("🔄 Всё взаимосвязано",
                                                                            callback_data="sphere_Всё")]]))
    return STEP_SPHERE


async def handle_sphere(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "goto_birth":
        await q.edit_message_text("📅 Напишите полную дату рождения:\n\nФормат: дд.мм.гггг\nНапример: 20.07.2001")
        return STEP_BIRTH
    s = q.data.replace("sphere_", "")
    user_sessions[q.from_user.id]["sphere"] = s
    m = await q.edit_message_text("⏳ Анализирую сферу…")
    await asyncio.sleep(2)
    await m.delete()
    det = {
        "Деньги": [("💸 Деньги приходят и уходят", "detail_Деньги_уходят"),
                   ("📈 Не могу выйти на уровень", "detail_Деньги_уровень"), ("⚠️ Долги", "detail_Деньги_долги"),
                   ("⏳ Много работаю, мало получаю", "detail_Деньги_работа"),
                   ("💡 Не знаю, в чём зарабатывать", "detail_Деньги_незнаю")],
        "Отношения": [("💔 Я один(одна)", "detail_Отношения_один"),
                      ("🔁 Повторяется сценарий", "detail_Отношения_сценарий"),
                      ("😔 Счастья нет", "detail_Отношения_счастье"),
                      ("🕊 Не могу отпустить", "detail_Отношения_отпустить"),
                      ("❓ Уйти или остаться", "detail_Отношения_выбор")],
        "Работа": [("🧭 Не моё направление", "detail_Работа_направление"),
                   ("📚 Знания есть, клиентов нет", "detail_Работа_клиенты"),
                   ("🌱 Боюсь начать", "detail_Работа_страх"),
                   ("🎯 Не могу рассказать о себе", "detail_Работа_позиционирование"),
                   ("💰 Достоин большего", "detail_Работа_доход")],
        "Состояние": [("😔 Нет сил", "detail_Состояние_силы"), ("🌫 Потерял(а) себя", "detail_Состояние_потеря"),
                      ("🚪 Страшно заново", "detail_Состояние_страх"), ("🧩 Тупик", "detail_Состояние_тупик"),
                      ("🤷 Не знаю, чего хочу", "detail_Состояние_незнаю")],
        "Всё": [("🌪 Всё навалилось", "detail_Всё_навалилось"), ("⚖️ Проблемы во всём", "detail_Всё_проблемы"),
                ("🌀 С чего начать", "detail_Всё_начать"), ("🔍 Хочу понять причину", "detail_Всё_причина")]
    }
    btns = [[InlineKeyboardButton(l, callback_data=c)] for l, c in det.get(s, [])]
    btns.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_sphere")])
    await q.message.reply_text("🌿 Выберите вариант:", reply_markup=InlineKeyboardMarkup(btns))
    return STEP_DETAIL


async def handle_detail(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "back_to_sphere":
        await q.edit_message_text("🌿 Что сейчас для вас важнее всего?",
                                  reply_markup=InlineKeyboardMarkup([
                                      [InlineKeyboardButton("💰 Деньги и доход",
                                                            callback_data="sphere_Деньги")],
                                      [InlineKeyboardButton("❤️ Отношения",
                                                            callback_data="sphere_Отношения")],
                                      [InlineKeyboardButton("🚀 Работа", callback_data="sphere_Работа")],
                                      [InlineKeyboardButton("🌿 Состояние",
                                                            callback_data="sphere_Состояние")],
                                      [InlineKeyboardButton("🔄 Всё взаимосвязано",
                                                            callback_data="sphere_Всё")]]))
        return STEP_SPHERE
    user_sessions[q.from_user.id]["detail"] = q.data
    await q.edit_message_text(
        "Благодарю. Опишите ситуацию своими словами.\n\nЧто происходит и что хотите изменить?\n\n(2–5 предложений)")
    return STEP_DESCRIBE


async def handle_describe(update, context):
    """Пользователь описал ситуацию сам — ИИ задаёт ОДИН уточняющий вопрос"""
    uid = update.effective_user.id
    user_text = update.message.text
    user_sessions[uid]["request"] = user_text

    msg = await update.message.reply_text("⏳ Внимательно читаю ваш запрос…")
    await asyncio.sleep(2)
    await msg.delete()

    prompt = f"""Ты — очень тёплый, эмпатичный психолог. Человек поделился с тобой своей болью: "{user_text}"

Ты чувствуешь его переживания. Ответь ему с теплотой и пониманием. Сначала одной короткой фразой вырази поддержку и понимание (например: "Мне очень жаль, что вы через это проходите...", "Я слышу в ваших словах столько боли...", "Спасибо, что поделились этим со мной..."). Потом задай ОДИН мягкий уточняющий вопрос, который покажет твой искренний интерес и желание понять его лучше.

Будь как добрый друг, который действительно хочет выслушать и поддержать. Не давай советов. Не будь холодным или отстранённым. Говори с теплотой."""

    question = await ask_ai(prompt)
    if not question:
        question = "Я слышу вас. Расскажите подробнее, что вы чувствуете в этой ситуации? Я хочу понять вас лучше."

    await update.message.reply_text(question)
    return STEP_AI_DIALOG


async def handle_ai_dialog(update, context):
    """После ответа пользователя на уточняющий вопрос — сразу диагностика"""
    uid = update.effective_user.id
    user_text = update.message.text

    msg = await update.message.reply_text("⏳ Глубоко анализирую ваш запрос…")
    await asyncio.sleep(3)
    await msg.delete()

    full_request = user_sessions[uid].get("request", "") + "\n" + user_text
    user_sessions[uid]["full_request"] = full_request

    mission = user_sessions[uid].get("mission", 1)
    md = MISSIONS.get(mission, MISSIONS[1])
    quote = full_request[:200]

    prompt = SYSTEM_PROMPT.format(mission=mission, description=md["description"],
                                  q1=md["qualities"][0], q2=md["qualities"][1], q3=md["qualities"][2],
                                  quote=quote, shadow=md["shadow"])
    diag = await ask_ai(prompt)

    mission_block = (
        f"\n\n🌿 О вашей миссии:\nПо вашей дате рождения ваша миссия — {mission}. {md['description']}\n\n"
        f"Ваши сильные качества:\n✔️ {md['qualities'][0]}\n✔️ {md['qualities'][1]}\n✔️ {md['qualities'][2]}\n\n"
        f"Теневая сторона: {md['shadow']}")

    if diag:
        diag = diag + mission_block
    else:
        diag = (
            f"🌿 Я внимательно прочитал(а) ваш запрос.\n\nВы пишете: «{quote}».\n\n"
            f"По вашей дате рождения ваша миссия — {mission}. {md['description']}\n\n"
            f"✔️ {md['qualities'][0]}\n✔️ {md['qualities'][1]}\n✔️ {md['qualities'][2]}\n\n"
            f"{md['shadow']}\n\nЭто не ваша вина. Это сценарий, который можно изменить.")

    user_sessions[uid]["diagnostic"] = diag
    stats["completed"] += 1
    save_stats(stats)

    await update.message.reply_text(diag)
    await update.message.reply_text(
        "🌿 Вы уже увидели одну важную вещь.\n\n"
        "По вашей дате рождения и запросу видно, что проблема не возникла случайно.\n\n"
        "Она повторяется по определённому внутреннему сценарию.\n\n"
        "И сейчас перед вами возникает самый важный вопрос.\n\n"
        "👇 Что вы хотите понять дальше?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Почему это повторяется?", callback_data="final_why")],
            [InlineKeyboardButton("🌱 Можно ли это изменить?", callback_data="final_can")],
            [InlineKeyboardButton("🧭 Что делать дальше?", callback_data="final_what")]]))
    return STEP_DIAGNOSTIC


async def handle_final(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id
    bot_username = context.bot.username

    share_text = (
        f"🌿 Привет! Нашёл классного бота-психолога «Ваша Точка Разворота».\n\n"
        f"Он считает твою миссию по дате рождения и с помощью ИИ показывает, "
        f"что сейчас реально происходит в твоей жизни и как это изменить.\n\n"
        f"Это не просто тест, а глубокий разбор. Мне очень помогло понять себя.\n\n"
        f"Попробуй тоже: https://t.me/{bot_username}")

    if d == "final_why":
        text = (
            "Большинство людей меняют обстоятельства.\nМеняют работу.\nМеняют партнёров.\nМеняют города.\n\n"
            "Но спустя время снова оказываются в похожей ситуации.\n\n"
            "Почему?\n\nПотому что меняются последствия.\nА источник остаётся прежним.\n\n"
            "Пока источник не найден, жизнь снова и снова возвращает человека к похожим событиям.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌿 Что такое источник?", callback_data="final_source")],
            [InlineKeyboardButton("🧭 Что делать дальше?", callback_data="final_what")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])

    elif d == "final_can":
        text = ("Да.\n\nНо изменения начинаются не тогда, когда человек получает совет.\n"
                "Они начинаются тогда, когда становится понятно:\n\n"
                "✔️ почему именно у вас возникла эта ситуация\n"
                "✔️ что удерживает её годами\n"
                "✔️ какие внутренние решения её поддерживают\n"
                "✔️ и какую новую стратегию можно построить\n\n"
                "Именно поэтому простого понимания обычно недостаточно.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Как найти источник?", callback_data="final_source")],
            [InlineKeyboardButton("🧭 Что делать дальше?", callback_data="final_what")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])

    elif d == "final_what":
        text = (f"Следующий шаг — не искать ещё один совет.\n\n"
                f"Следующий шаг — определить настоящий источник вашей ситуации.\n\n"
                f"Именно для этого существует стратегическая сессия «{SESSION_NAME}».\n\n"
                "Во время неё мы разбираем не симптомы, а глубинные причины, "
                "повторяющиеся сценарии, сильные стороны и выстраиваем новую стратегию именно под вашу ситуацию.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Как проходит сессия", callback_data="final_format")],
            [InlineKeyboardButton("✨ Что я получу?", callback_data="final_result")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])

    elif d == "final_source":
        text = (f"🌿 ЧТО ТАКОЕ ИСТОЧНИК?\n\n"
                f"Источник — это не событие из прошлого.\n"
                f"Это внутренняя точка запуска сценария.\n\n"
                f"То, что заставляет вас повторять одни и те же выборы, "
                f"оказываться в похожих ситуациях и чувствовать одно и то же годами.\n\n"
                f"На стратегической сессии «{SESSION_NAME}» мы находим ваш источник, "
                f"разбираем его структуру и выстраиваем новую стратегию.\n\n"
                f"Вы перестаёте бороться с последствиями и начинаете менять причину.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Как проходит сессия", callback_data="final_format")],
            [InlineKeyboardButton("✨ Что я получу?", callback_data="final_result")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])

    elif d == "final_format":
        text = (f"📖 КАК ПРОХОДИТ СТРАТЕГИЧЕСКАЯ СЕССИЯ «{SESSION_NAME}»\n\n"
                f"Это глубинная работа на 90–120 минут.\n"
                f"Онлайн, один на один с ЛюдМилой.\n\n"
                f"Мы не просто говорим о проблеме — мы находим её корень.\n\n"
                f"Что происходит:\n"
                f"✔️ Разбираем вашу ситуацию и запрос\n"
                f"✔️ Находим источник повторяющегося сценария\n"
                f"✔️ Определяем, что удерживает ситуацию\n"
                f"✔️ Раскрываем ваши сильные стороны по дате рождения\n"
                f"✔️ Выстраиваем стратегию выхода\n\n"
                f"Вы уходите не с советом, а с пониманием: что делать именно вам.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Что я получу?", callback_data="final_result")],
            [InlineKeyboardButton("❓ Частые вопросы", callback_data="final_faq")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])

    elif d == "final_result":
        text = ("✨ ЧТО ВЫ ПОЛУЧИТЕ ПОСЛЕ ВСТРЕЧИ?\n\n"
                "✔️ Ясность — что на самом деле происходит\n"
                "✔️ Понимание источника — почему это повторяется\n"
                "✔️ Объяснение — какие решения поддерживают сценарий\n"
                "✔️ Свои сильные стороны — как использовать их\n"
                "✔️ Направление движения\n"
                "✔️ Первые конкретные шаги\n\n"
                "И самое главное — вы перестанете двигаться вслепую.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❓ Частые вопросы", callback_data="final_faq")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])

    elif d == "final_faq":
        text = ("❓ ЧАСТЫЕ ВОПРОСЫ\n\n"
                "🕐 Сколько длится?\n90–120 минут — достаточно для глубинной работы.\n\n"
                "💻 Как проходит?\nОнлайн по видеосвязи из любого места.\n\n"
                "📋 Нужна подготовка?\nНет. Только запрос и готовность смотреть глубже.\n\n"
                "👤 Подходит ли мне?\nЕсли устали от повторений и хотите изменить — подходит.\n\n"
                "📅 Что после?\nЗапись сессии, план действий и ясное направление.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Готов(а) сделать шаг", callback_data="final_ready")],
            [InlineKeyboardButton("💰 Стоимость и запись", callback_data="final_price")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])

    elif d == "final_ready":
        text = ("🌿 ГОТОВЫ СДЕЛАТЬ СЛЕДУЮЩИЙ ШАГ?\n\n"
                "Если вы чувствуете, что хотите не просто понимать свою ситуацию, "
                "а разобраться в ней глубже и получить новую стратегию действий — "
                f"запишитесь на стратегическую сессию «{SESSION_NAME}».\n\n"
                "Это встреча один на один с ЛюдМилой, где вы получите не совет, а точную стратегию.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Записаться на сессию", callback_data="final_book")],
            [InlineKeyboardButton("💰 Стоимость и запись", callback_data="final_price")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])

    elif d == "final_price":
        try:
            with open("price.jpg", "rb") as photo:
                await q.message.reply_photo(photo=photo)
        except:
            pass

        text = (
            "✅ Если вы приняли решение больше не откладывать свою жизнь и хотите понять, что на самом деле мешает вам двигаться вперёд, — приглашаю вас на стратегическую сессию «Источник».\n\n"
            "Стратегическая сессия «Источник» —\n это не шаблонная консультация.\nЭто индивидуальная работа, где мы вместе находим не следствие, а настоящий источник вашей ситуации.\n\n"
            "После встречи вы уйдёте не просто с пониманием.\nВы получите:\n✔️ ясность, что происходит именно с вами;\n✔️ понимание, почему ситуация повторяется;\n✔️ своё сильное направление;\n✔️ конкретную стратегию дальнейших действий.\n\n"
            "📍Продолжительность встречи — 90–120 минут.\n💰 Стоимость — 6 000 ₽.\n\n"
            "Если вы чувствуете, что готовы перестать ходить по кругу и хотите найти настоящий источник своей ситуации —\n📩 напишите мне: «Готов(а) к сессии \"Источник\"».\n\n"
            "Я свяжусь с вами, мы согласуем удобный день и время встречи, отвечу на организационные вопросы и отправлю реквизиты для оплаты.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Записаться", callback_data="final_book")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])
        await q.message.reply_text(text, reply_markup=kb)
        return STEP_FINAL

    elif d == "final_book":
        stats["booked"] += 1
        save_stats(stats)
        msg = gen_msg(user_sessions.get(uid, {}))
        text = ("🚀 ПОСЛЕДНИЙ ШАГ\n\n"
                "Скопируйте это сообщение и отправьте ЛюдМиле в удобной соцсети:\n\n"
                f"{msg}\n\n"
                "👇 Выберите, куда написать:")
        soc_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📲 Telegram", url=f"https://t.me/{TELEGRAM_USERNAME}")],
            [InlineKeyboardButton("💬 WhatsApp", url=f"https://wa.me/{WHATSAPP_NUMBER}")],
            [InlineKeyboardButton("📘 ВКонтакте", url=f"https://vk.me/{VK_USERNAME}")],
            [InlineKeyboardButton("📷 Instagram", url=f"https://instagram.com/{INSTAGRAM_USERNAME}")],
            [InlineKeyboardButton("🎵 TikTok", url=f"https://tiktok.com/@{TIKTOK_USERNAME}")],
            [InlineKeyboardButton("🎁 Поделиться с другом", callback_data="final_share")],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])
        await q.edit_message_text(text, reply_markup=soc_kb)
        return STEP_FINAL

    elif d == "final_share":
        share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}&text={urllib.parse.quote(share_text)}"
        share_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Отправить другу в Telegram", url=share_url)],
            [InlineKeyboardButton("🔙 Назад", callback_data="final_back")]])
        await q.edit_message_text(
            "🎁 ПОДЕЛИТЬСЯ С ДРУГОМ\n\n"
            "Нажмите на кнопку ниже, чтобы отправить приглашение другу в Telegram.\n"
            "Сообщение будет подставлено автоматически — вам останется только выбрать, кому отправить.",
            reply_markup=share_kb)
        return STEP_FINAL

    elif d == "final_back":
        text = ("🌿 Вы уже увидели одну важную вещь.\n\n"
                "По вашей дате рождения и запросу видно, что проблема не возникла случайно.\n\n"
                "Она повторяется по определённому внутреннему сценарию.\n\n"
                "И сейчас перед вами возникает самый важный вопрос.\n\n"
                "👇 Что вы хотите понять дальше?")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Почему это повторяется?", callback_data="final_why")],
            [InlineKeyboardButton("🌱 Можно ли это изменить?", callback_data="final_can")],
            [InlineKeyboardButton("🧭 Что делать дальше?", callback_data="final_what")]])
        await q.edit_message_text(text, reply_markup=kb)
        return STEP_DIAGNOSTIC

    else:
        text = "🌿 Что вы хотите понять дальше?"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Почему это повторяется?", callback_data="final_why")],
            [InlineKeyboardButton("🌱 Можно ли это изменить?", callback_data="final_can")],
            [InlineKeyboardButton("🧭 Что делать дальше?", callback_data="final_what")]])

    await q.edit_message_text(text, reply_markup=kb)
    return STEP_FINAL


if __name__ == "__main__":
    print("🤖 БОТ ЗАПУСКАЕТСЯ...")
    if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_ТОКЕН_СЮДА":
        print("❌ Не указан BOT_TOKEN!")
        sys.exit(1)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STEP_START: [CallbackQueryHandler(step_honesty, pattern="^start_diag$")],
            STEP_HONESTY: [CallbackQueryHandler(handle_honesty, pattern="^honest_")],
            STEP_BIRTH: [CallbackQueryHandler(step_birth, pattern="^goto_birth$"),
                         MessageHandler(filters.TEXT & ~filters.COMMAND, handle_birth)],
            STEP_SPHERE: [CallbackQueryHandler(step_sphere, pattern="^goto_sphere$"),
                          CallbackQueryHandler(handle_problem, pattern="^problem_"),
                          CallbackQueryHandler(handle_sphere, pattern="^(sphere_|goto_birth)")],
            STEP_DETAIL: [CallbackQueryHandler(handle_detail, pattern="^(detail_|back_to_sphere)")],
            STEP_DESCRIBE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_describe)],
            STEP_AI_DIALOG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_dialog)],
            STEP_DIAGNOSTIC: [CallbackQueryHandler(handle_final, pattern="^final_")],
            STEP_FINAL: [CallbackQueryHandler(handle_final, pattern="^final_")],
        }, fallbacks=[CommandHandler("start", start)]))
    print(f"🔑 API-ключей: {len(key_pool.keys)}")
    print("🚀 Бот готов!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)