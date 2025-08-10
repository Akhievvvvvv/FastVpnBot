import logging
import re
import ssl
import certifi
import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData

# --- Твои данные ---
API_TOKEN = "8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8"
ADMIN_CHAT_ID = -1002593269045
YOUR_USER_ID = 7231676236  # твой ID для подтверждения оплаты

OUTLINE_API_URL = "https://109.196.100.159:7235/gip-npAdi0GP2xswd_f9Nw"
OUTLINE_CERT_SHA256 = "2065D8741DB5F2DD3E9A4C6764F55ECAD1B76FBADC33E1FAF7AD1A21AC163131"

DATABASE = "fastvpn_bot.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

confirm_cb = CallbackData("confirm", "user_id", "tariff")

# SSL для Outline API (с отключенной проверкой сертификата)
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# --- Инициализация базы данных ---

async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                paid INTEGER DEFAULT 0,
                key_config TEXT,
                referrer INTEGER,
                tariff TEXT DEFAULT ''
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
            if referrer and referrer != user_id:
                try:
                    await db.execute("INSERT INTO referrals(referrer, referee) VALUES (?, ?)", (referrer, user_id))
                except aiosqlite.IntegrityError:
                    pass
            await db.commit()

async def set_paid(user_id: int, tariff: str):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET paid = 1, tariff = ? WHERE user_id = ?", (tariff, user_id))
        await db.commit()

async def set_key(user_id: int, key_config: str):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE users SET key_config = ? WHERE user_id = ?", (key_config, user_id))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute(
            "SELECT user_id, username, paid, key_config, referrer, tariff FROM users WHERE user_id = ?",
            (user_id,)
        )
        return await cursor.fetchone()

async def get_referral_stats(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer = ?", (user_id,))
        total = (await cursor.fetchone())[0]
        cursor = await db.execute("""
            SELECT COUNT(*) FROM users 
            WHERE referrer = ? AND paid = 1
        """, (user_id,))
        paid = (await cursor.fetchone())[0]
        return total, paid

# --- Функция создания ключа в Outline API ---

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

# --- Тексты и клавиатуры ---

WELCOME_TEXT = (
    "🌟 <b>Добро пожаловать в FastVpnBot!</b> 🌟\n\n"
    "Здесь ты можешь быстро и просто получить VPN ключ для Outline, подключиться и быть всегда в безопасности! 🔐\n\n"
    "Используй кнопки ниже, чтобы начать:\n"
)

REKVIZITY_TEXT = (
    "💳 <b>Реквизиты для оплаты:</b>\n\n"
    "+7 932 222 99 30 (Ozon Bank)\n"
    "Оплата по тарифам:\n"
    "1 месяц — 99 ₽\n"
    "3 месяца — 249 ₽\n"
    "5 месяцев — 399 ₽\n\n"
    "После оплаты нажми кнопку «💳 Оплатил(а)» для подтверждения.\n"
)

INSTRUCTION_TEXT = (
    "🛠 <b>Как активировать VPN через Outline:</b>\n\n"
    "1️⃣ Перейди в настройки телефона\n"
    "2️⃣ Открой раздел <i>Telegram для бизнеса</i>\n"
    "3️⃣ Нажми <i>Чат-боты</i>\n"
    "4️⃣ Добавь бота <b>@FastVpn_bot_bot</b>\n\n"
    "После оплаты нажми «💳 Оплатил(а)» — и я пришлю тебе ключ!\n"
    "Если есть вопросы — пиши, помогу всегда! 😊"
)

def main_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📃 Тарифы", callback_data="show_tariffs"),
        InlineKeyboardButton("👥 Реферальная система", callback_data="show_referral"),
        InlineKeyboardButton("💳 Реквизиты", callback_data="show_rekvizity"),
        InlineKeyboardButton("🛠 Инструкция", callback_data="instruction"),
        InlineKeyboardButton("💳 Оплатил(а)", callback_data="paid"),
    )
    return kb

def tariffs_menu(user_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("1 месяц — 99 ₽", callback_data=confirm_cb.new(user_id=user_id, tariff="1 мес")),
        InlineKeyboardButton("3 месяца — 249 ₽", callback_data=confirm_cb.new(user_id=user_id, tariff="3 мес")),
        InlineKeyboardButton("5 месяцев — 399 ₽", callback_data=confirm_cb.new(user_id=user_id, tariff="5 мес")),
        InlineKeyboardButton("⬅️ Назад", callback_data="main_menu"),
    )
    return kb

# --- Хендлеры ---

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
                ref = None

    await add_user(user_id, username, ref)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")

@dp.message_handler(commands=["ref"])
async def cmd_referral(message: types.Message):
    user_id = message.from_user.id
    total, paid = await get_referral_stats(user_id)
    ref_link = f"https://t.me/FastVpn_bot_bot?start=ref={user_id}"
    text = (
        f"👥 <b>Ваша реферальная ссылка:</b>\n"
        f"{ref_link}\n\n"
        f"👤 Всего перешло по ссылке: {total}\n"
        f"✅ Активировали подписку: {paid}"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message_handler(lambda m: m.text and not m.text.startswith('/'))
async def any_message_reply(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! Используй кнопки ниже, чтобы управлять VPN:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data == "main_menu")
async def cb_main_menu(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "show_tariffs")
async def cb_show_tariffs(call: types.CallbackQuery):
    await call.answer()
    kb = tariffs_menu(call.from_user.id)
    await call.message.edit_text("📃 <b>Выберите тариф:</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query_handler(confirm_cb.filter())
async def cb_confirm_payment(call: types.CallbackQuery, callback_data: dict):
    user_id = int(callback_data["user_id"])
    tariff = callback_data["tariff"]
    if call.from_user.id != user_id:
        await call.answer("Это не для вас!", show_alert=True)
        return

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Оплатил(а)", callback_data="paid"))
    await call.message.edit_text(f"Вы выбрали тариф: <b>{tariff}</b>\n\n{REKVIZITY_TEXT}", reply_markup=kb, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "paid")
async def cb_paid(call: types.CallbackQuery):
    user_id = call.from_user.id
    await call.answer("Спасибо за оплату! Жду подтверждения от администратора.")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"admin_confirm_{user_id}"))
    await bot.send_message(ADMIN_CHAT_ID, f"Пользователь @{call.from_user.username or user_id} (ID: {user_id}) оплатил подписку.", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_confirm_"))
async def cb_admin_confirm(call: types.CallbackQuery):
    if call.from_user.id != YOUR_USER_ID:
        await call.answer("У вас нет прав на это действие.", show_alert=True)
        return
    user_id = int(call.data.split("_")[-1])
    await set_paid(user_id, "подписка")
    key = await create_outline_access_key()
    if key:
        await set_key(user_id, key)
        await bot.send_message(user_id, f"✅ Ваша подписка активирована!\n\nВот ваш VPN ключ для Outline:\n{key}")
    else:
        await bot.send_message(user_id, "❌ Ошибка при создании VPN ключа, свяжитесь с поддержкой.")
    await call.answer("Оплата подтверждена и ключ отправлен пользователю.")
    await call.message.edit_reply_markup()  # убираем кнопки

@dp.callback_query_handler(lambda c: c.data == "show_rekvizity")
async def cb_show_rekvizity(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text(REKVIZITY_TEXT, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
    ), parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "instruction")
async def cb_instruction(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        INSTRUCTION_TEXT,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        ),
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data == "show_referral")
async def cb_show_referral(call: types.CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    total, paid = await get_referral_stats(user_id)
    ref_link = f"https://t.me/FastVpn_bot_bot?start=ref={user_id}"
    text = (
        f"👥 <b>Ваша реферальная ссылка:</b>\n"
        f"{ref_link}\n\n"
        f"👤 Всего перешло по ссылке: {total}\n"
        f"✅ Активировали подписку: {paid}"
    )
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        ),
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data == "show_rekvizity")
async def cb_show_rekvizity(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        REKVIZITY_TEXT,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")
        ),
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data == "main_menu")
async def cb_main_menu(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data == "show_tariffs")
async def cb_show_tariffs(call: types.CallbackQuery):
    await call.answer()
    kb = tariffs_menu(call.from_user.id)
    await call.message.edit_text(
        "📃 <b>Выберите тариф:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query_handler(confirm_cb.filter())
async def cb_confirm_payment(call: types.CallbackQuery, callback_data: dict):
    user_id = int(callback_data["user_id"])
    tariff = callback_data["tariff"]
    if call.from_user.id != user_id:
        await call.answer("Это не для вас!", show_alert=True)
        return

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Оплатил(а)", callback_data="paid"))
    await call.message.edit_text(
        f"Вы выбрали тариф: <b>{tariff}</b>\n\n{REKVIZITY_TEXT}",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data == "paid")
async def cb_paid(call: types.CallbackQuery):
    user_id = call.from_user.id
    await call.answer("Спасибо за оплату! Жду подтверждения от администратора.")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"admin_confirm_{user_id}"))
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"Пользователь @{call.from_user.username or user_id} (ID: {user_id}) оплатил подписку.",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_confirm_"))
async def cb_admin_confirm(call: types.CallbackQuery):
    if call.from_user.id != YOUR_USER_ID:
        await call.answer("У вас нет прав на это действие.", show_alert=True)
        return
    user_id = int(call.data.split("_")[-1])
    await set_paid(user_id, "подписка")
    key = await create_outline_access_key()
    if key:
        await set_key(user_id, key)
        await bot.send_message(
            user_id,
            f"✅ Ваша подписка активирована!\n\nВот ваш VPN ключ для Outline:\n{key}"
        )
    else:
        await bot.send_message(user_id, "❌ Ошибка при создании VPN ключа, свяжитесь с поддержкой.")
    await call.answer("Оплата подтверждена и ключ отправлен пользователю.")
    await call.message.edit_reply_markup()  # убираем кнопки

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
                ref = None

    await add_user(user_id, username, ref)
    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.message_handler(commands=["ref"])
async def cmd_referral(message: types.Message):
    user_id = message.from_user.id
    total, paid = await get_referral_stats(user_id)
    ref_link = f"https://t.me/FastVpn_bot_bot?start=ref={user_id}"
    text = (
        f"👥 <b>Ваша реферальная ссылка:</b>\n"
        f"{ref_link}\n\n"
        f"👤 Всего перешло по ссылке: {total}\n"
        f"✅ Активировали подписку: {paid}"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message_handler(lambda m: m.text and not m.text.startswith('/'))
async def any_message_reply(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! Используй кнопки ниже, чтобы управлять VPN:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

# Запуск бота

from aiogram import executor

async def main():
    await init_db()
    logging.info("Бот запущен")
    await dp.start_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
