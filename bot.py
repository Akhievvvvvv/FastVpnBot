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

ADMIN_GROUP_ID = -1002593269045
BOT_USERNAME = 'FastVpn_bot_bot'  # твой username без @

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

issued_clients = {}  # user_id: dict с данными клиента
last_assigned_ip = 1

TARIFFS = {
    "1": {"name": "1 месяц", "price": 99, "days": 30},
    "3": {"name": "3 месяца", "price": 249, "days": 90},
    "5": {"name": "5 месяцев", "price": 449, "days": 150}
}

REFERRAL_PREFIX = "ref_"

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

def format_payment_notification(username, user_id, tariff_key):
    tariff = TARIFFS[tariff_key]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"💸 <b>Новый платёж:</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"📦 Тариф: {tariff['name']} — {tariff['price']}₽\n"
        f"⏰ Время: {now_str}"
    )

def main_menu_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💳 Выбрать тариф"))
    kb.add(KeyboardButton("🤝 Реферальная система"))
    return kb

def tariffs_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for key, val in TARIFFS.items():
        kb.add(KeyboardButton(f"{val['name']} — {val['price']}₽"))
    kb.add(KeyboardButton("⬅️ Назад"))
    return kb

def payment_info_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("✅ Я оплатил(а)"))
    kb.add(KeyboardButton("⬅️ Назад"))
    return kb

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    ref = None
    if message.get_args().startswith(REFERRAL_PREFIX):
        try:
            ref = int(message.get_args()[len(REFERRAL_PREFIX):])
        except:
            ref = None
    if user_id not in issued_clients:
        issued_clients[user_id] = {
            "referral_from": ref,
            "subscription_expire": datetime.now(),
            "private_key": None,
            "ip": None,
            "tariff": None,
            "paid": False
        }
    welcome_text = (
        "👋 <b>Привет!</b> Это простой VPN для безопасного интернета! 🌐🔒\n\n"
        "Выбирай тариф, оплачивай, а я помогу с настройкой VPN. 🚀\n\n"
        "Для начала установи официальное приложение WireGuard:\n"
        "📱 <b>Android:</b> https://play.google.com/store/apps/details?id=com.wireguard.android\n"
        "🍎 <b>iOS:</b> https://apps.apple.com/app/wireguard/id1441195209\n\n"
        "После оплаты я пришлю тебе файл конфигурации, который можно открыть прямо из Telegram для быстрой настройки.\n\n"
        "👇 Выбери действие в меню ниже 👇"
    )
    await message.answer(welcome_text, reply_markup=main_menu_keyboard())

@dp.message_handler(lambda m: m.text == "💳 Выбрать тариф")
async def choose_tariff(message: types.Message):
    await message.answer("🛒 Выбери тариф из списка ниже:", reply_markup=tariffs_keyboard())

@dp.message_handler(lambda m: any(m.text == f"{val['name']} — {val['price']}₽" for val in TARIFFS.values()))
async def selected_tariff(message: types.Message):
    chosen = None
    for key, val in TARIFFS.items():
        if message.text == f"{val['name']} — {val['price']}₽":
            chosen = key
            break
    if not chosen:
        await message.answer("❌ Неизвестный тариф, попробуй ещё раз.")
        return
    user_id = message.from_user.id
    issued_clients.setdefault(user_id, {})
    issued_clients[user_id]["tariff"] = chosen
    issued_clients[user_id]["paid"] = False

    pay_text = (
        f"💰 <b>Реквизиты для оплаты:</b>\n\n"
        f"🧾 Тариф: <b>{TARIFFS[chosen]['name']} — {TARIFFS[chosen]['price']}₽</b>\n"
        f"🏦 Оплата на карту Ozon Банка:\n"
        f"<code>89322229930</code>\n\n"
        f"После оплаты нажми кнопку ниже, чтобы сообщить мне."
    )
    await message.answer(pay_text, reply_markup=payment_info_keyboard())

@dp.message_handler(lambda m: m.text == "✅ Я оплатил(а)")
async def user_paid(message: types.Message):
    user = message.from_user
    user_id = user.id

    if user_id not in issued_clients or not issued_clients[user_id].get("tariff"):
        await message.answer("⚠️ Пожалуйста, сначала выбери тариф.")
        return

    if issued_clients[user_id].get("paid"):
        await message.answer("✅ Ты уже сообщил об оплате, жди подтверждения от администратора.")
        return

    issued_clients[user_id]["paid"] = True

    tariff_key = issued_clients[user_id]["tariff"]
    username = user.username or user.first_name

    notification_text = format_payment_notification(username, user_id, tariff_key)

    confirm_button = InlineKeyboardMarkup()
    confirm_button.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{user_id}"))

    await bot.send_message(ADMIN_GROUP_ID, notification_text, reply_markup=confirm_button)
    await message.answer("🕐 Оплата зарегистрирована! Жди подтверждения от администратора.", reply_markup=main_menu_keyboard())

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_"))
async def admin_confirm_payment(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    # Можно добавить проверку, что это админ (необязательно)
    user_id_str = callback_query.data.split("_")[1]
    user_id = int(user_id_str)

    if user_id not in issued_clients or not issued_clients[user_id].get("paid"):
        await callback_query.answer("❌ Платёж не найден или уже подтверждён.", show_alert=True)
        return

    # Генерация данных пользователя
    priv_key = generate_private_key()
    client_ip = generate_client_ip()

    issued_clients[user_id].update({
        "private_key": priv_key,
        "ip": client_ip,
        "subscription_expire": datetime.now() + timedelta(days=TARIFFS[issued_clients[user_id]["tariff"]]["days"]),
        "paid": False  # теперь оплачено и подтверждено
    })

    # Формируем конфиг и отправляем файл
    wg_config = generate_wg_config(priv_key, client_ip)
    filename = f"vpn_{user_id}.conf"
    with open(filename, "w") as f:
        f.write(wg_config)

    await bot.send_document(user_id, InputFile(filename), caption=(
        "🎉 Оплата подтверждена! Вот твой файл конфигурации WireGuard.\n\n"
        "📱 Просто открой этот файл в приложении WireGuard, и включи VPN одной кнопкой!\n\n"
        "Если ещё не установил приложение, вот ссылки:\n"
        "📲 Android: https://play.google.com/store/apps/details?id=com.wireguard.android\n"
        "🍏 iOS: https://apps.apple.com/app/wireguard/id1441195209\n\n"
        "Безопасного интернета! 🔒🌐"
    ), reply_markup=main_menu_keyboard())

    # Уведомление админу
    await callback_query.message.edit_reply_markup(reply_markup=None)
