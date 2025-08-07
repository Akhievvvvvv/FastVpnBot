import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

ADMIN_ID = 7231676236  # Админ ID

TARIFFS = {
    "1m": {"name": "1 месяц", "price": 99, "days": 30},
    "3m": {"name": "3 месяца", "price": 249, "days": 90},
    "5m": {"name": "5 месяцев", "price": 399, "days": 150}
}

# Инициализация базы SQLite
conn = sqlite3.connect("fastvpn.db")
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    ref TEXT,
    vpn_key TEXT,
    paid INTEGER DEFAULT 0,
    plan TEXT,
    payment_time TEXT
)
''')
conn.commit()

# Генерация уникального VPN ключа
def generate_vpn_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

# Добавление или обновление пользователя в базе
def upsert_user(user_id, ref=None, paid=0, plan=None, payment_time=None, vpn_key=None):
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (user_id, ref, paid, plan, payment_time, vpn_key) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, ref, paid, plan, payment_time, vpn_key)
        )
    else:
        cursor.execute(
            "UPDATE users SET ref = ?, paid = ?, plan = ?, payment_time = ?, vpn_key = ? WHERE user_id = ?",
            (ref, paid, plan, payment_time, vpn_key, user_id)
        )
    conn.commit()

# Получение данных пользователя
def get_user(user_id):
    cursor.execute("SELECT user_id, ref, vpn_key, paid, plan, payment_time FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return {
            "user_id": row[0],
            "ref": row[1],
            "vpn_key": row[2],
            "paid": bool(row[3]),
            "plan": row[4],
            "payment_time": datetime.fromisoformat(row[5]) if row[5] else None
        }
    else:
        return None

# Проверка активности подписки
def is_subscription_active(user_data):
    if not user_data or not user_data["paid"] or not user_data["payment_time"] or not user_data["plan"]:
        return False
    plan_days = TARIFFS[user_data["plan"]]["days"]
    expiry_date = user_data["payment_time"] + timedelta(days=plan_days)
    return datetime.now() < expiry_date

# Формирование приветственного сообщения
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

# Клавиатура главного меню
def main_menu_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        kb.insert(InlineKeyboardButton(text=f"{t['name']} — {t['price']}₽", callback_data=f"tariff_{key}"))
    kb.add(InlineKeyboardButton(text="📲 Скачать для iPhone", url="https://apps.apple.com/app/outline-vpn/id1356177741"))
    kb.add(InlineKeyboardButton(text="🤖 Скачать для Android", url="https://play.google.com/store/apps/details?id=org.outline.android.client"))
    return kb

# Кнопка "Оплатил(а)"
def paid_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="✅ Оплатил(а)", callback_data="paid"))
    return kb

# Кнопка подтверждения для админа
def admin_confirm_button(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_{user_id}"))
    return kb

# /start команда
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user = message.from_user
    ref_id = message.get_args() if message.get_args() else None

    existing_user = get_user(user.id)
    if existing_user is None:
        upsert_user(user.id, ref=ref_id)
    else:
        # Обновим реферальный ID, если пришёл с ссылкой
        if ref_id and existing_user["ref"] is None:
            upsert_user(user.id, ref=ref_id, paid=existing_user["paid"], plan=existing_user["plan"],
                        payment_time=existing_user["payment_time"].isoformat() if existing_user["payment_time"] else None,
                        vpn_key=existing_user["vpn_key"])

    text = get_welcome_text(user)
    await message.answer(text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=main_menu_keyboard())

# Выбор тарифа
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tariff_'))
async def process_tariff(callback_query: types.CallbackQuery):
    tariff_key = callback_query.data[len("tariff_"):]
    if tariff_key not in TARIFFS:
        await callback_query.answer("Выбран неверный тариф.")
        return

    user_data = get_user(callback_query.from_user.id)
    if user_data and user_data["paid"]:
        await callback_query.answer("У вас уже есть активная подписка.")
        return

    tariff = TARIFFS[tariff_key]
    upsert_user(callback_query.from_user.id, plan=tariff_key, paid=0, payment_time=None, vpn_key=None)
    text = (
        f"Вы выбрали тариф: <b>{tariff['name']}</b> за <b>{tariff['price']}₽</b>.\n\n"
        f"💳 Для оплаты переведите деньги на реквизиты:\n"
        f"+7 932 222 99 30 (Ozon Bank)\n\n"
        f"После оплаты нажмите кнопку <b>Оплатил(а)</b>, чтобы мы могли проверить и активировать ваш VPN-ключ."
    )
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=paid_button())
    await callback_query.answer()

# Пользователь нажал "Оплатил(а)"
@dp.callback_query_handler(lambda c: c.data == "paid")
async def process_paid(callback_query: types.CallbackQuery):
    user_data = get_user(callback_query.from_user.id)
    if not user_data or not user_data.get("plan"):
        await callback_query.answer("Сначала выберите тариф.")
        return

    if user_data["paid"]:
        await callback_query.answer("У вас уже оплачена подписка.")
        return

    # Уведомление админу о том, что пользователь оплатил
    plan_name = TARIFFS[user_data["plan"]]["name"]
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🔔 Пользователь @{callback_query.from_user.username or user_data['user_id']} "
        f"(ID: {user_data['user_id']}) заявил об оплате.\n"
        f"Тариф: {plan_name}\n"
        f"Время: {time_now}"
    )
    await bot.send_message(ADMIN_ID, msg, reply_markup=admin_confirm_button(user_data['user_id']))
    await callback_query.answer("Ваш запрос на оплату отправлен администратору. Ожидайте подтверждения.")

# Админ подтвердил оплату
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_"))
async def process_admin_confirm(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("У вас нет прав подтверждать оплату.")
        return

    user_id = int(callback
