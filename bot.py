import logging
import random
import string
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import aiosqlite

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'
ADMIN_ID = 7231676236  # Твой user_id
ADMIN_GROUP_ID = -1002593269045  # ID админ-группы

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

TARIFFS = {
    "1m": {"name": "1 месяц", "price": 99, "days": 30},
    "3m": {"name": "3 месяца", "price": 249, "days": 90},
    "5m": {"name": "5 месяцев", "price": 399, "days": 150}
}

DB_PATH = "fastvpn_users.db"

# --- Работа с БД ---

async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ref TEXT,
            paid INTEGER DEFAULT 0,
            plan TEXT,
            payment_time TEXT,
            vpn_key TEXT,
            free_days INTEGER DEFAULT 0,
            free_days_expiry TEXT,
            subscription_end TEXT
        )''')
        await db.commit()

async def add_user(user_id: int, username: str, ref: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, ref) VALUES (?, ?, ?)",
            (user_id, username, ref)
        )
        await db.commit()

async def set_user_plan(user_id: int, plan: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, user_id))
        await db.commit()

async def set_user_paid(user_id: int, paid: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET paid = ? WHERE user_id = ?", (1 if paid else 0, user_id))
        await db.commit()

async def set_payment_time(user_id: int, payment_time: datetime):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET payment_time = ? WHERE user_id = ?", (payment_time.isoformat(), user_id))
        await db.commit()

async def set_vpn_key(user_id: int, key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET vpn_key = ? WHERE user_id = ?", (key, user_id))
        await db.commit()

async def set_subscription_end(user_id: int, end_date: datetime):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET subscription_end = ? WHERE user_id = ?", (end_date.isoformat(), user_id))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, username, ref, paid, plan, payment_time, vpn_key, free_days, free_days_expiry, subscription_end "
            "FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row

# --- Вспомогательные функции ---

def generate_vpn_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def get_welcome_text(user: types.User):
    ref_link = f"https://t.me/FastVpn_bot_bot?start={user.id}"
    text = (
        "╔══════════════════════════╗\n"
        "✨👋 <b>Добро пожаловать в FastVPN!</b> 👋✨\n"
        "╚══════════════════════════╝\n\n"

        "🔹 <b>Почему FastVPN?</b>\n"
        "🌐 Доступ к любым сайтам без ограничений\n"
        "🔒 Защита и конфиденциальность твоих данных\n"
        "⚡ Высокая скорость и стабильное соединение\n"
        "📱 Поддержка iPhone и Android\n"
        "💎 Легкая настройка и использование\n\n"

        "📊 <b>Тарифы:</b>\n"
        "🗓️ 1 месяц — 99₽\n"
        "🗓️ 3 месяца — 249₽\n"
        "🗓️ 5 месяцев — 399₽\n\n"

        "👥 <b>Реферальная программа:</b>\n"
        "Приглашай друзей — получай +7 дней бесплатно при их покупке!\n"
        f"Твоя реферальная ссылка:\n"
        f"<a href='{ref_link}'>Нажми и приглашай друзей!</a>\n\n"

        "📲 <b>Как начать?</b>\n"
        "1️⃣ Выбери тариф\n"
        "2️⃣ Оплати по реквизитам\n"
        "3️⃣ Нажми «Оплатил(а)» для подтверждения\n"
        "4️⃣ Получи VPN-ключ и пользуйся!\n\n"

        "💳 Реквизиты для оплаты:\n"
        "+7 932 222 99 30 (Ozon Bank)\n\n"

        "🎉 Спасибо, что выбрал FastVPN! Безопасность и свобода интернета с тобой! 🌟"
    )
    return text

def main_menu_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        kb.insert(InlineKeyboardButton(text=f"{t['name']} — {t['price']}₽", callback_data=f"tariff_{key}"))
    kb.add(InlineKeyboardButton(text="📲 Скачать для iPhone", url="https://apps.apple.com/app/outline-vpn/id1356177741"))
    kb.add(InlineKeyboardButton(text="🤖 Скачать для Android", url="https://play.google.com/store/apps/details?id=org.outline.android.client"))
    return kb

def paid_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="✅ Оплатил(а)", callback_data="paid"))
    return kb

def admin_confirm_button(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_{user_id}"))
    return kb

# --- Проверка подписки в фоне ---

async def check_subscription_expiry():
    while True:
        await asyncio.sleep(60*60*24)  # 24 часа
        async with aiosqlite.connect(DB_PATH) as db:
            now = datetime.utcnow()
            cursor = await db.execute("SELECT user_id, subscription_end, paid FROM users WHERE paid = 1")
            users = await cursor.fetchall()
            for user in users:
                user_id = user[0]
                subscription_end_str = user[1]
                if not subscription_end_str:
                    continue
                subscription_end = datetime.fromisoformat(subscription_end_str)
                if subscription_end < now:
                    # Обнуляем paid, план, vpn_key
                    await db.execute(
                        "UPDATE users SET paid = 0, plan = NULL, vpn_key = NULL, payment_time = NULL, subscription_end = NULL WHERE user_id = ?",
                        (user_id,)
                    )
                    await db.commit()
                    try:
                        await bot.send_message(
                            user_id,
                            "⛔ Ваша подписка истекла. Пожалуйста, продлите её, чтобы продолжить пользоваться сервисом."
                        )
                    except Exception as e:
                        logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

# --- Обработчики команд ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    args = message.get_args()
    ref = None
    if args and args.isdigit():
        ref = args
    await add_user(message.from_user.id, message.from_user.username or "", ref)
    text = get_welcome_text(message.from_user)
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode='HTML')

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("tariff_"))
async def process_tariff_callback(callback_query: types.CallbackQuery):
    tariff_key = callback_query.data[len("tariff_"):]
    if tariff_key not in TARIFFS:
        await callback_query.answer("Неверный тариф", show_alert=True)
        return
    tariff = TARIFFS[tariff_key]
    text = (
        f"Вы выбрали тариф: {tariff['name']} — {tariff['price']}₽\n\n"
        f"💳 Оплатите по реквизитам:\n"
        f"+7 932 222 99 30 (Ozon Bank)\n\n"
        "После оплаты нажмите кнопку ниже, чтобы подтвердить оплату."
    )
    await callback_query.message.edit_text(text, reply_markup=paid_button())

@dp.callback_query_handler(lambda c: c.data == "paid")
async def process_paid(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user = await get_user(user_id)
    if not user:
        await callback_query.answer("Пользователь не найден", show_alert=True)
        return
    # Отправляем админу сообщение с кнопкой подтверждения
    await bot.send_message(
        ADMIN_GROUP_ID,
        f"Пользователь @{callback_query.from_user.username} ({user_id}) подтвердил оплату.",
        reply_markup=admin_confirm_button(user_id)
    )
    await callback_query.answer("Ваш запрос на подтверждение оплаты отправлен администратору.")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_"))
async def process_confirm_payment(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("У вас нет прав для подтверждения оплаты.", show_alert=True)
        return
    user_id_str = callback_query.data[len("confirm_"):]
    if not user_id_str.isdigit():
        await callback_query.answer("Неверный user_id.", show_alert
