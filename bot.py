import logging
import re
import ssl
import certifi
import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData
from aiogram.utils import executor

# ======== Твои данные ========
API_TOKEN = "8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8"
ADMIN_CHAT_ID = -1002593269045  # твоя админ-группа
YOUR_USER_ID = 7231676236       # твой user_id для проверки админа

OUTLINE_API_URL = "https://109.196.100.159:7235/gip-npAdi0GP2xswd_f9Nw"
OUTLINE_CERT_SHA256 = "2065D8741DB5F2DD3E9A4C6764F55ECAD1B76FBADC33E1FAF7AD1A21AC163131"

DATABASE = "fastvpn_bot.db"
# ============================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Для удобной обработки callback данных с user_id
confirm_cb = CallbackData("confirm", "user_id")

# SSL контекст для aiohttp (самоподписанный cert, отключаем проверку)
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ===================== База данных =====================
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                paid INTEGER DEFAULT 0,
                key_config TEXT,
                referrer INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referrer INTEGER,
                referee INTEGER PRIMARY KEY
            )
        """)
        await db.commit()

async def add_user(user_id: int, username: str, referrer: int = None):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        res = await cursor.fetchone()
        if res is None:
            await db.execute(
                "INSERT INTO users(user_id, username, paid, key_config, referrer) VALUES (?, ?, 0, '', ?)",
                (user_id, username, referrer)
            )
            if referrer:
                try:
                    await db.execute("INSERT INTO referrals(referrer, referee) VALUES (?, ?)", (referrer, user_id))
                except aiosqlite.IntegrityError:
                    pass
            await db.commit()

async def set_paid(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET paid = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def set_key(user_id: int, key_config: str):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET key_config = ? WHERE user_id = ?", (key_config, user_id))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(
            "SELECT user_id, username, paid, key_config, referrer FROM users WHERE user_id = ?",
            (user_id,)
        )
        return await cursor.fetchone()

# ========================================================

# Создание ключа Outline через API (async)
async def create_outline_access_key():
    url = f"{OUTLINE_API_URL}/access-keys"
    headers = {
        "Content-Type": "application/json",
        "X-Outline-Server-Cert-Sha256": OUTLINE_CERT_SHA256,
    }
    payload = {
        "name": "VPN Key",
        "accessUrl": None
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, ssl=ssl_context) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("accessUrl")
                else:
                    text = await resp.text()
                    logging.error(f"Outline API error: {resp.status} {text}")
                    return None
    except Exception as e:
        logging.error(f"Outline API request error: {e}")
        return None

# Красочное приветствие
WELCOME_TEXT = (
    "🎉 <b>Добро пожаловать в FastVpnBot!</b> 🎉\n\n"
    "✨ <b>Что я умею:</b> ✨\n"
    "✅ Автоматически выдавать тебе рабочий VPN ключ через Outline\n"
    "✅ Помогать подключиться быстро и просто\n"
    "✅ Принимать оплату и мгновенно активировать подписку\n"
    "✅ Работать с реферальной системой — приглашай друзей и получай бонусы 💰\n\n"
    "👇 Используй кнопки ниже, чтобы начать:"
)

INSTRUCTION_TEXT = (
    "🛠 <b>Как активировать VPN через Outline:</b>\n\n"
    "1️⃣ Перейди в настройки твоего телефона\n"
    "2️⃣ Открой раздел <i>Telegram для бизнеса</i>\n"
    "3️⃣ Нажми <i>Чат-боты</i>\n"
    "4️⃣ Добавь бота <b>@FastVpn_bot_bot</b>\n\n"
    "После оплаты жми кнопку «💳 Оплатил(а)» — и я сразу пришлю тебе ключ!\n\n"
    "Если будут вопросы — я всегда на связи! 😊"
)

# Главное меню с inline-кнопками
def main_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("⚙️ Активировать бота", callback_data="activate"),
        InlineKeyboardButton("📖 Инструкция", callback_data="instruction"),
        InlineKeyboardButton("💳 Оплатил(а)", callback_data="paid"),
    )
    return kb

# Радостный ответ на любое сообщение, кроме команд
@dp.message_handler(lambda message: not message.text.startswith('/'))
async def cheerful_reply(message: types.Message):
    text = (
        f"🌈 Привет-привет, {message.from_user.first_name}! 😄\n\n"
        "Я всегда рад тебе помочь! 🌟\n"
        "Используй кнопки ниже, чтобы управлять VPN:\n\n"
        "👉 Активировать бота\n"
        "👉 Посмотреть инструкцию\n"
        "👉 Сообщить об оплате\n\n"
        "Ты супер, что ты со мной! 🚀✨"
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

# Обработка команды /start с реферальным кодом
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    ref = None
    args = message.get_args()
    if args:
        m = re.search(r"ref=(\d+)", args)
        if m:
            ref = int(m.group(1))
            if ref == user_id:
                ref = None  # Нельзя рефить себя

    await add_user(user_id, username, ref)

    await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "instruction")
async def send_instruction(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, INSTRUCTION_TEXT, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "activate")
async def activate_bot(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "🛠 Чтобы бот работал в личных чатах, добавь его в Telegram Business, как описано в инструкции.",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("📖 Показать инструкцию", callback_data="instruction")
        )
    )

@dp.callback_query_handler(lambda c: c.data == "paid")
async def confirm_payment(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await bot.answer_callback_query(callback_query.id)
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Подтвердить оплату", callback_data=confirm_cb.new(user_id=user_id))
    )
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"💰 Пользователь @{callback_query.from_user.username or user_id} (ID: {user_id}) нажал «Оплатил(а)».\n"
        f"Проверь и подтверди оплату.",
        reply_markup=keyboard
    )
    await bot.send_message(user_id, "✅ Запрос на подтверждение оплаты отправлен администратору. Ожидайте, пожалуйста!")

@dp.callback_query_handler(confirm_cb.filter())
async def admin_confirm_payment(callback_query: types.CallbackQuery, callback_data: dict):
    admin_id = callback_query.from_user.id
    if admin_id != YOUR_USER_ID:
        await bot.answer_callback_query(callback_query.id, "❌ У тебя нет доступа к этой функции", show_alert=True)
        return

    user_id = int(callback_data["user_id"])
    user = await get_user(user_id)
    if not user:
        await bot.answer_callback_query(callback_query.id, "❌ Пользователь не найден в базе", show_alert=True)
        return

    await bot.answer_callback_query(callback_query.id, "✅ Оплата подтверждена, создаю ключ...")

    key = await create_outline_access_key()
    if key is None:
        await bot.send_message(admin_id, f"❌ Не удалось создать ключ для пользователя {user_id}")
        await bot.send_message(user_id, "❌ Ошибка при создании VPN ключа, свяжитесь с администратором.")
        return

    await set_paid(user_id)
    await set_key(user_id, key)

    await bot.send_message(
        user_id,
        f"🎉 Поздравляем! Оплата подтверждена.\n\n"
        f"🔑 Вот твой VPN ключ для приложения Outline:\n\n"
        f"<code>{key}</code>\n\n"
        "Если есть вопросы — пиши, я всегда помогу! 🌟",
        parse_mode="HTML"
    )

    await bot.send_message(admin_id, f"✅ Ключ для пользователя {user_id} успешно создан и отправлен.")

if __name__ == "__main__":
    import asyncio
    from aiogram import executor

    # Инициализируем базу данных до запуска бота
    asyncio.run(init_db())

    # Создаем и устанавливаем новый event loop вручную
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Запускаем polling с указанным event loop
    executor.start_polling(dp, skip_updates=True, loop=loop)
