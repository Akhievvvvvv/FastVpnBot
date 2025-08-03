import asyncio
import secrets
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from datetime import datetime

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'
ADMIN_CHAT_ID = -1002593269045  # Твоя админ-группа

# WireGuard сервер
SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820

# Тарифы
TARIFFS = {
    "1 мес — 99₽": 99,
    "3 мес — 249₽": 249,
    "5 мес — 449₽": 449,
}

# База данных (в памяти) для примера, замени на БД по необходимости
issued_clients = {}
last_assigned_ip = 1
user_subscriptions = {}  # user_id: {tariff, expire_date, referral_bonus_days}
user_referrals = {}  # user_id: реферальный код (например, user_id)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Клавиатура тарифов (ReplyKeyboardMarkup)
tariff_buttons = [KeyboardButton(t) for t in TARIFFS.keys()]
tariffs_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(*tariff_buttons).add(KeyboardButton("Реферальная система"))

def generate_private_key():
    return secrets.token_urlsafe(32)

def generate_client_ip():
    global last_assigned_ip
    last_assigned_ip += 1
    return f"10.0.0.{last_assigned_ip}"

def generate_wg_config(client_private_key: str, client_ip: str) -> str:
    return f"""[Interface]
PrivateKey = {client_private_key}
Address = {client_ip}/24
DNS = 1.1.1.1

[Peer]
PublicKey = {SERVER_PUBLIC_KEY}
Endpoint = {SERVER_IP}:{SERVER_PORT}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""

def create_wg_file_content(private_key, client_ip):
    return generate_wg_config(private_key, client_ip).encode('utf-8')

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    user_referrals[message.from_user.id] = str(message.from_user.id)  # просто юзерID - реферальный код
    text = (
        "👋 Привет! Это простой и надежный VPN для безопасного интернета! 🌐🔒\n\n"
        "Выбирай тариф, оплачи его и получи готовую настройку VPN — всё легко и быстро! 🚀\n\n"
        "👉 Для начала выбери тариф ниже:"
    )
    await message.answer(text, reply_markup=tariffs_kb)

@dp.message_handler(lambda m: m.text in TARIFFS)
async def tariff_chosen(message: types.Message):
    tariff_name = message.text
    price = TARIFFS[tariff_name]
    user_id = message.from_user.id

    payment_text = (
        f"💰 Вы выбрали тариф: *{tariff_name}*\n\n"
        f"Для оплаты переведите *{price}₽* на реквизиты:\n"
        f"📱 Номер: *89322229930*\n"
        f"🏦 Банк: *Ozon Банк*\n\n"
        "После оплаты нажмите кнопку *Оплатил(а)* ниже, чтобы мы могли проверить платеж и активировать VPN.\n\n"
        "Если оплатили с реферальной ссылки, получите +7 дней бонуса! 🎁"
    )
    pay_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(KeyboardButton("Оплатил(а)")).add(KeyboardButton("Отмена"))
    
    # Сохраняем выбранный тариф пользователю (в памяти)
    user_subscriptions[user_id] = {"tariff": tariff_name, "paid": False}
    
    await message.answer(payment_text, parse_mode='Markdown', reply_markup=pay_kb)

@dp.message_handler(lambda m: m.text == "Оплатил(а)")
async def payment_confirm(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.full_name

    if user_id not in user_subscriptions or user_subscriptions[user_id].get("paid", False):
        await message.answer("❌ Вы пока не выбрали тариф или уже оплатили.")
        return

    tariff = user_subscriptions[user_id]["tariff"]
    price = TARIFFS[tariff]
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Отправляем уведомление в админ-группу с кнопкой Подтвердить
    confirm_kb = InlineKeyboardMarkup(row_width=1)
    confirm_kb.add(InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_{user_id}"))

    notify_text = (
        f"💸 *Новый платёж:*\n\n"
        f"👤 Пользователь: @{user_name}\n"
        f"🆔 ID: {user_id}\n"
        f"📦 Тариф: {tariff}\n"
        f"💰 Сумма: {price}₽\n"
        f"⏰ Время: {time_str}"
    )

    await bot.send_message(ADMIN_CHAT_ID, notify_text, parse_mode='Markdown', reply_markup=confirm_kb)
    await message.answer("✅ Ваш запрос на активацию оплаты отправлен администратору, ожидайте подтверждения.", reply_markup=tariffs_kb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_"))
async def confirm_payment_callback(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    admin_id = callback_query.from_user.id

    # Проверяем, кто нажал (можно добавить проверку admin_id если нужно)
    if admin_id != ADMIN_CHAT_ID and admin_id != callback_query.message.chat.id:
        await callback_query.answer("❌ У вас нет прав подтверждать оплаты.")
        return

    if user_id not in user_subscriptions:
        await callback_query.answer("❌ Пользователь не найден.")
        return

    if user_subscriptions[user_id].get("paid", False):
        await callback_query.answer("⚠️ Этот пользователь уже активирован.")
        return

    # Генерируем ключи и IP
    client_private_key = generate_private_key()
    client_ip = generate_client_ip()

    issued_clients[user_id] = {
        "private_key": client_private_key,
        "ip": client_ip,
        "tariff": user_subscriptions[user_id]["tariff"],
    }

    # Помечаем как оплачено
    user_subscriptions[user_id]["paid"] = True

    # Формируем конфиг и файл
    wg_config_str = generate_wg_config(client_private_key, client_ip)
    wg_config_bytes = wg_config_str.encode('utf-8')
    filename = f"vpn_{user_id}.conf"

    # Отправляем пользователю конфиг файлом + инструкцию
    instr_text = (
        "🎉 Ваша подписка активирована!\n\n"
        "📁 Вот ваш VPN конфигурационный файл. Просто нажмите на него и выберите приложение WireGuard для импорта.\n\n"
        "📲 Если у вас Android или iOS, скачайте официальное приложение WireGuard:\n"
        " - Android: https://play.google.com/store/apps/details?id=com.wireguard.android\n"
        " - iOS: https://apps.apple.com/app/wireguard/id1441195209\n\n"
        "🔑 После импорта просто включите VPN одним тапом! Без лишних настроек.\n\n"
        "Если возникнут вопросы — пиши мне!"
    )

    try:
        await bot.send_document(user_id, types.InputFile.from_buffer(wg_config_bytes, filename))
        await bot.send_message(user_id, instr_text)
        await callback_query.answer("✅ Конфигурация отправлена пользователю.")
        await bot.send_message(ADMIN_CHAT_ID, f"✅ Оплата пользователя @{issued_clients[user_id].get('username', user_id)} подтверждена и конфиг выслан.")
    except Exception as e:
        await callback_query.answer(f"❌ Не удалось отправить конфиг: {e}")

    # Обновляем сообщение в админ-группе
    await callback_query.message.edit_text(
        callback_query.message.text + "\n\n✅ Оплата подтверждена."
    )
    await callback_query.message.edit_reply_markup(reply_markup=None)

@dp.message
