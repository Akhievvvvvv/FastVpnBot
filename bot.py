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
ADMIN_ID = 7231676236  # твой user_id

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Тарифы
TARIFFS = {
    "1m": {"name": "1 месяц", "price": 99, "days": 30},
    "3m": {"name": "3 месяца", "price": 249, "days": 90},
    "5m": {"name": "5 месяцев", "price": 399, "days": 150}
}

DB_PATH = "fastvpn_users.db"

# ------------------------
# Работа с базой данных
# ------------------------

async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ref TEXT,
            paid INTEGER DEFAULT 0,
            plan TEXT,
            payment_time TEXT,
            vpn_key TEXT
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

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, username, ref, paid, plan, payment_time, vpn_key FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row

async def get_all_paid_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, username, plan, payment_time FROM users WHERE paid = 1")
        rows = await cursor.fetchall()
        return rows

# ------------------------
# Вспомогательные функции
# ------------------------

def generate_vpn_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def get_welcome_text(user: types.User):
    ref_link = f"https://t.me/FastVpn_bot_bot?start={user.id}"
    return (
        f"✨👋 <b>Приветствуем тебя в FastVPN — твоём надёжном спутнике в мире безопасного и быстрого интернета!</b> 👋✨\n\n"
        f"Здесь ты получаешь:\n"
        f"🌐 Безграничный доступ к любимым сайтам и приложениям, где бы ты ни был\n"
        f"🔒 Абсолютную защиту и конфиденциальность твоих данных\n"
        f"⚡ Максимально быструю скорость соединения\n"
        f"📱 Поддержку iPhone и Android с удобными приложениями\n"
        f"💎 Простое и быстрое подключение без заморочек\n\n"
        f"📊 <b>Наши тарифы:</b>\n"
        f"🗓️ 1 месяц — 99₽\n"
        f"🗓️ 3 месяца — 249₽\n"
        f"🗓️ 5 месяцев — 399₽\n\n"
        f"👥 <b>Реферальная система:</b>\n"
        f"Приглашай 3 друзей — получай 7 дней бесплатно!\n"
        f"Твоя уникальная реферальная ссылка:\n"
        f"<a href='{ref_link}'>Приглашай друзей и экономь!</a>\n\n"
        f"📲 <b>Как начать пользоваться FastVPN? Очень просто!</b>\n"
        f"1️⃣ Выбираешь тариф\n"
        f"2️⃣ Нажимаешь кнопку для скачивания приложения\n"
        f"3️⃣ После оплаты получаешь свой личный VPN-ключ — просто копируй!\n"
        f"4️⃣ Вставляешь ключ в приложение и наслаждаешься безопасным интернетом!\n\n"
        f"💳 После выбора тарифа увидишь реквизиты для оплаты\n"
        f"⬇️ После оплаты нажми кнопку «Оплатил(а)»\n"
        f"🔔 Администратор проверит оплату и пришлёт тебе ключ\n\n"
        f"🎉 Добро пожаловать в FastVPN! Безопасность и свобода интернета с тобой! 🌟"
    )

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

# ------------------------
# Хэндлеры
# ------------------------

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user = message.from_user
    ref_id = message.get_args() if message.get_args() else None
    await add_user(user.id, user.username or "", ref_id)
    text = get_welcome_text(user)
    await message.answer(text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=main_menu_keyboard())

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tariff_'))
async def process_tariff(callback_query: types.CallbackQuery):
    tariff_key = callback_query.data[len("tariff_"):]
    if tariff_key not in TARIFFS:
        await callback_query.answer("Выбран неверный тариф.")
        return
    tariff = TARIFFS[tariff_key]
    user_id = callback_query.from_user.id
    await set_user_plan(user_id, tariff_key)
    text = (
        f"Вы выбрали тариф: <b>{tariff['name']}</b> за <b>{tariff['price']}₽</b>.\n\n"
        f"💳 Для оплаты переведите деньги на реквизиты:\n"
        f"+7 932 222 99 30 (Ozon Bank)\n\n"
        f"После оплаты нажмите кнопку <b>Оплатил(а)</b>, чтобы мы могли проверить и активировать ваш VPN-ключ."
    )
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=paid_button())
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "paid")
async def process_paid(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_data = await get_user(user_id)
    if not user_data or not user_data[4]:  # plan
        await callback_query.answer("Сначала выберите тариф.")
        return
    if user_data[3] == 1:  # paid
        await callback_query
