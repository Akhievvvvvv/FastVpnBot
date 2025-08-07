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
            vpn_key TEXT,
            free_days INTEGER DEFAULT 0,
            free_days_expiry TEXT
        )''')
        await db.commit()

async def add_user(user_id: int, username: str, ref: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        # Вставляем пользователя, если его нет
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

async def add_free_days(user_id: int, days: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем текущие free_days и free_days_expiry
        cursor = await db.execute("SELECT free_days, free_days_expiry FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        now = datetime.utcnow()
        if row:
            current_days = row[0] or 0
            expiry_str = row[1]
            if expiry_str:
                expiry = datetime.fromisoformat(expiry_str)
                if expiry > now:
                    # Увеличиваем free_days и обновляем expiry
                    new_expiry = expiry + timedelta(days=days)
                    new_days = current_days + days
                else:
                    # Истёк — начинаем заново
                    new_expiry = now + timedelta(days=days)
                    new_days = days
            else:
                new_expiry = now + timedelta(days=days)
                new_days = days
        else:
            new_expiry = now + timedelta(days=days)
            new_days = days

        await db.execute(
            "UPDATE users SET free_days = ?, free_days_expiry = ? WHERE user_id = ?",
            (new_days, new_expiry.isoformat(), user_id)
        )
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, username, ref, paid, plan, payment_time, vpn_key, free_days, free_days_expiry FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row

async def get_user_by_referral(ref_user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE ref = ?", (str(ref_user_id),))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

# ------------------------
# Вспомогательные функции
# ------------------------

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

# ------------------------
# Обработка команд и колбеков
# ------------------------

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user = message.from_user
    ref_id = message.get_args() if message.get_args() else None
    if ref_id == str(user.id):
        # чтобы человек не мог сам себя пригласить
        ref_id = None
    await add_user(user.id, user.username or "", ref_id)
    text = get_welcome_text(user)
    await message.answer(text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=main_menu_keyboard())

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tariff_'))
async def process_tariff(callback_query: types.CallbackQuery):
    tariff_key = callback_query.data[len("tariff_"):]
    if tariff_key not in TARIFFS:
        await callback_query.answer("Выбран неверный тариф.", show_alert=True)
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
    if not user_data or not user_data[4]:  # plan не выбран
        await callback_query.answer("Сначала выберите тариф.", show_alert=True)
        return

    # Отправляем уведомление админу в группу
    user_plan_key = user_data[4]
    tariff = TARIFFS.get(user_plan_key)
    payment_text = (
        f"📢 <b>Новая оплата!</b>\n"
        f"👤 Пользователь: @{user_data[1] or 'не указан'} (ID: {user_id})\n"
        f"💼 Тариф: {tariff['name']} за {tariff['price']}₽\n"
        f"⏰ Время: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
    )
    await bot.send_message(ADMIN_GROUP_ID, payment_text, parse_mode='HTML', reply_markup=admin_confirm_button(user_id))
    await callback_query.answer("Оплата отправлена на проверку администратору!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_"))
async def admin_confirm_payment(callback_query: types.CallbackQuery):
    admin_user_id = callback_query.from_user.id
    if admin_user_id != ADMIN_ID:
        await callback_query.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    user_id_to_confirm = int(callback_query.data[len("confirm_"):])
    user_data = await get_user(user_id_to_confirm)
    if not user_data:
        await callback_query.answer("Пользователь не найден.", show_alert=True)
        return
    if user_data[3] == 1:
        await callback_query.answer("Оплата уже подтверждена.", show_alert=True)
        return

    # Обновляем статус оплаты
    await set_user_paid(user_id_to_confirm, True)
    await set_payment_time(user_id_to_confirm, datetime.utcnow())

    # Генерируем VPN-ключ и сохраняем
    vpn_key = generate_vpn_key()
    await set_vpn_key(user_id_to_confirm, vpn_key)

    # Начисляем рефереру +7 дней, если есть реферер и это не сам пользователь
    referrer_id = user_data[2]
    if referrer_id and referrer_id != str(user_id_to_confirm):
        try:
            ref_id_int = int(referrer_id)
            await add_free_days(ref_id_int, 7)
            # Можно уведомить реферера, если хочешь
            try:
                await bot.send_message(ref_id_int,
                    "🎉 Поздравляем! Вы получили +7 дней бесплатного VPN за приглашение друга, который оплатил тариф.")
            except Exception:
                pass
        except ValueError:
            pass  # Некорректный ref в базе

    # Отправляем пользователю сообщение с ключом
    await bot.send_message(user_id_to_confirm,
        f"✅ Ваша оплата подтверждена!\n\n"
        f"🔑 Ваш VPN-ключ:\n<code>{vpn_key}</code>\n\n"
        f"📲 Используйте его в приложении Outline VPN и наслаждайтесь безопасным интернетом! 🌐")

    # Ответ админу
    await callback_query.message.edit_text("Оплата подтверждена и VPN-ключ выдан.", reply_markup=None)
    await callback_query.answer()

# ------------------------
# Запуск бота
# ------------------------

async def on_startup(_):
    await db_init()
    logging.info("Бот запущен и база инициализирована.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
