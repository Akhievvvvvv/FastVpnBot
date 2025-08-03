print("✅ Бот запущен!")
import logging
logging.basicConfig(level=logging.INFO)
import asyncio
import secrets
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'

SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820
SERVER_INTERFACE = 'wg0'

ADMIN_GROUP_ID = -1002593269045
BOT_USERNAME = 'FastVpn_bot_bot'

bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot)

TARIFFS = {
    "1": {"name": "1 месяц", "price": 99, "days": 30},
    "3": {"name": "3 месяца", "price": 249, "days": 90},
    "5": {"name": "5 месяцев", "price": 449, "days": 150}
}

issued_clients = {}  # user_id: {данные}
last_assigned_ip = 2

REF_PREFIX = "ref_"

def generate_private_key():
    return secrets.token_urlsafe(32)

def generate_client_ip():
    global last_assigned_ip
    ip = f"10.0.0.{last_assigned_ip}"
    last_assigned_ip += 1
    return ip

def generate_wg_config(private_key, client_ip):
    return f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/24
DNS = 1.1.1.1

[Peer]
PublicKey = {SERVER_PUBLIC_KEY}
Endpoint = {SERVER_IP}:{SERVER_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💳 Тарифы"))
    kb.add(KeyboardButton("🎁 Реферальная система"))
    return kb

def tariff_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for key, val in TARIFFS.items():
        kb.add(KeyboardButton(f"{val['name']} — {val['price']}₽"))
    kb.add(KeyboardButton("⬅️ Назад"))
    return kb

def payment_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("✅ Я оплатил(а)"))
    kb.add(KeyboardButton("⬅️ Назад"))
    return kb

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    ref = None
    if message.get_args().startswith(REF_PREFIX):
        try:
            ref = int(message.get_args()[len(REF_PREFIX):])
        except:
            ref = None
    if user_id not in issued_clients:
        issued_clients[user_id] = {
            "ref_from": ref,
            "paid": False,
            "private_key": None,
            "ip": None,
            "tariff": None,
            "subscription_expire": None
        }
    welcome = (
        "👋 <b>Привет!</b> Добро пожаловать в FastVPN! 🔐\n\n"
        "📲 Установи <b>WireGuard</b>:\n"
        "• Android: https://play.google.com/store/apps/details?id=com.wireguard.android\n"
        "• iOS: https://apps.apple.com/app/wireguard/id1441195209\n\n"
        "Выбери тариф, оплати, и я пришлю конфигурацию для подключения.\n\n"
        "👇 Выбирай ниже 👇"
    )
    await message.answer(welcome, reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "💳 Тарифы")
async def show_tariffs(message: types.Message):
    await message.answer("💼 Выбери тариф:", reply_markup=tariff_keyboard())

@dp.message_handler(lambda m: any(m.text == f"{v['name']} — {v['price']}₽" for v in TARIFFS.values()))
async def selected_tariff(message: types.Message):
    user_id = message.from_user.id
    for key, val in TARIFFS.items():
        if message.text == f"{val['name']} — {val['price']}₽":
            issued_clients[user_id]['tariff'] = key
            break
    await message.answer(
        f"💰 Реквизиты для оплаты:\n\n"
        f"🧾 Тариф: {message.text}\n"
        f"🏦 Переведи на карту <b>Ozon Банк</b>:\n"
        f"<code>89322229930</code>\n\n"
        f"После оплаты нажми <b>«Я оплатил(а)»</b> 👇",
        reply_markup=payment_keyboard()
    )

@dp.message_handler(lambda m: m.text == "✅ Я оплатил(а)")
async def payment_confirmed(message: types.Message):
    user_id = message.from_user.id
    client = issued_clients.get(user_id)
    if not client or not client.get("tariff"):
        await message.answer("❗ Сначала выбери тариф.")
        return
    if client["paid"]:
        await message.answer("⏳ Уже жду подтверждение от администратора.")
        return
    client["paid"] = True
    tariff = TARIFFS[client["tariff"]]
    msg = (
        f"💸 <b>Новый платёж:</b>\n\n"
        f"👤 Пользователь: @{message.from_user.username}\n"
        f"🆔 ID: {user_id}\n"
        f"📦 Тариф: {tariff['name']} — {tariff['price']}₽\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    confirm_button = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{user_id}")
    )
    await bot.send_message(ADMIN_GROUP_ID, msg, reply_markup=confirm_button)
    await message.answer("🕐 Оплата зафиксирована! Жди подтверждения 👀", reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_"))
async def confirm_callback(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    client = issued_clients.get(user_id)
    if not client or not client["paid"]:
        await call.answer("⚠️ Невозможно подтвердить — нет данных или уже подтверждено.", show_alert=True)
        return

    client["private_key"] = generate_private_key()
    client["ip"] = generate_client_ip()
    days = TARIFFS[client["tariff"]]["days"]
    client["subscription_expire"] = datetime.now() + timedelta(days=days)
    client["paid"] = False

    config_text = generate_wg_config(client["private_key"], client["ip"])
    filename = f"wg_{user_id}.conf"
    with open(filename, "w") as f:
        f.write(config_text)

    await bot.send_document(user_id, InputFile(filename), caption=(
        "✅ Оплата подтверждена!\n\n"
        "📁 Ниже твой конфиг для WireGuard.\n"
        "🔌 Просто открой его в приложении и включи VPN.\n\n"
        "📲 Android: https://play.google.com/store/apps/details?id=com.wireguard.android\n"
        "🍏 iOS: https://apps.apple.com/app/wireguard/id1441195209\n\n"
        "🔥 Приятного пользования!"
    ))
    await call.message.edit_reply_markup()  # Убираем кнопку после подтверждения
    await call.message.answer(f"✅ Конфигурация выдана пользователю с ID {user_id}!")
    await call.answer("✅ Подтверждено!")

@dp.message_handler(lambda m: m.text == "🎁 Реферальная система")
async def referral_system(message: types.Message):
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
    await message.answer(
        f"🎁 <b>Пригласи друзей и получи +7 дней!</b>\n\n"
        f"📨 Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        f"Если кто-то оплатит по ней, ты получишь бонус 🎉"
    )

if __name__ == '__main__':
    print("🚀 Бот запущен и ожидает команды...")
    executor.start_polling(dp, skip_updates=True)
