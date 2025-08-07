from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import asyncio
import logging
import random
import string
from datetime import datetime

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Хранилище пользователей и их статусов (вместо базы данных)
users = {}  # user_id: {'ref': str, 'key': str, 'paid': bool, 'plan': str, 'payment_time': datetime}

# Тарифы
TARIFFS = {
    "1m": {"name": "1 месяц", "price": 99},
    "3m": {"name": "3 месяца", "price": 249},
    "5m": {"name": "5 месяцев", "price": 399}
}

# Админ ID, которому придет уведомление
ADMIN_ID = 7231676236  # твой user_id

# Функция генерации уникального VPN ключа (пример)
def generate_vpn_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

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

# Клавиатура главного меню с тарифами и рефералкой
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

# Старт команды
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user = message.from_user
    # Сохраняем рефералку — если пользователь пришёл по ссылке с параметром start=<id>
    if message.get_args():
        ref_id = message.get_args()
        users[user.id] = {"ref": ref_id, "paid": False, "key": None, "plan": None, "payment_time": None}
    else:
        users.setdefault(user.id, {"ref": None, "paid": False, "key": None, "plan": None, "payment_time": None})

    text = get_welcome_text(user)
    await message.answer(text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=main_menu_keyboard())

# Обработка выбора тарифа
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tariff_'))
async def process_tariff(callback_query: types.CallbackQuery):
    tariff_key = callback_query.data[len("tariff_"):]
    if tariff_key not in TARIFFS:
        await callback_query.answer("Выбран неверный тариф.")
        return
    tariff = TARIFFS[tariff_key]
    user_id = callback_query.from_user.id
    users[user_id]["plan"] = tariff_key
    text = (
        f"Вы выбрали тариф: <b>{tariff['name']}</b> за <b>{tariff['price']}₽</b>.\n\n"
        f"💳 Для оплаты переведите деньги на реквизиты:\n"
        f"+7 932 222 99 30 (Ozon Bank)\n\n"
        f"После оплаты нажмите кнопку <b>Оплатил(а)</b>, чтобы мы могли проверить и активировать ваш VPN-ключ."
    )
    await callback_query.message.edit_text(text, parse_mode='HTML', reply_markup=paid_button())
    await callback_query.answer()

# Обработка нажатия "Оплатил(а)"
@dp.callback_query_handler(lambda c: c.data == "paid")
async def process_paid(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_data = users.get(user_id)
    if not user_data or not user_data.get("plan"):
        await callback_query.answer("Сначала выберите тариф.")
        return
    if user_data["paid"]:
        await callback_query.answer("Вы уже оплатили тариф.")
        return

    # Отправляем админу уведомление
    plan_name = TARIFFS[user_data["plan"]]["name"]
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🔔 Пользователь @{callback_query.from_user.username or user_id} (ID: {user_id}) "
        f"заявил об оплате.\n"
        f"Тариф: {plan_name}\n"
        f"Время: {time_now}"
    )
    await bot.send_message(ADMIN_ID, msg, reply_markup=admin_confirm_button(user_id))
    await callback_query.answer("Ваш запрос на оплату отправлен администратору. Ожидайте подтверждения.")

# Обработка подтверждения админом
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_"))
async def process_admin_confirm(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    if admin_id != ADMIN_ID:
        await callback_query.answer("У вас нет прав подтверждать оплату.")
        return

    user_id = int(callback_query.data[len("confirm_"):])
    user_data = users.get(user_id)
    if not user_data:
        await callback_query.answer("Пользователь не найден.")
        return

    if user_data["paid"]:
        await callback_query.answer("Пользователь уже оплачен.")
        return

    # Генерируем уникальный VPN ключ и ставим оплату
    vpn_key = generate_vpn_key()
    user_data["key"] = vpn_key
    user_data["paid"] = True
    user_data["payment_time"] = datetime.now()

    # Отправляем пользователю ключ и поздравление
    text = (
        f"🎉 <b>Поздравляем с подключением к FastVPN!</b>\n\n"
        f"Вот ваш уникальный VPN-ключ:\n\n"
        f"<code>{
