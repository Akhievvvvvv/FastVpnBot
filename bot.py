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
BOT_USERNAME = 'FastVpn_bot_bot'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

issued_clients = {}
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
        f"💸 <b>Новый платёж:</b>

"
        f"👤 Пользователь: @{username}
"
        f"🆔 ID: {user_id}
"
        f"📦 Тариф: {tariff['name']} — {tariff['price']}₽
"
        f"⏰ Время: {now_str}"
    )

def main_menu():
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
            "paid": False,
            "reminded": False
        }
    welcome_text = (
        "👋 <b>Привет!</b> Это простой VPN для безопасного интернета! 🌐🔒

"
        "Выбирай тариф, оплачивай, а я помогу с настройкой VPN. 🚀

"
        "Для начала установи официальное приложение WireGuard:
"
        "📱 <b>Android:</b> https://play.google.com/store/apps/details?id=com.wireguard.android
"
        "🍎 <b>iOS:</b> https://apps.apple.com/app/wireguard/id1441195209

"
        "После оплаты я пришлю тебе файл конфигурации, который можно открыть прямо из Telegram для быстрой настройки.

"
        "👇 Выбери действие в меню ниже 👇"
    )
    await message.answer(welcome_text, reply_markup=main_menu())

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
    user_id = message.from_user.id
    issued_clients[user_id]["tariff"] = chosen
    issued_clients[user_id]["paid"] = False

    pay_text = (
        f"💰 <b>Реквизиты для оплаты:</b>

"
        f"🧾 Тариф: <b>{TARIFFS[chosen]['name']} — {TARIFFS[chosen]['price']}₽</b>
"
        f"🏦 Оплата на карту Ozon Банка:
"
        f"<code>89322229930</code>

"
        f"После оплаты нажми кнопку ниже, чтобы сообщить мне."
    )
    await message.answer(pay_text, reply_markup=payment_info_keyboard())

@dp.message_handler(lambda m: m.text == "✅ Я оплатил(а)")
async def user_paid(message: types.Message):
    user = message.from_user
    user_id = user.id
    if not issued_clients[user_id].get("tariff"):
        await message.answer("⚠️ Пожалуйста, сначала выбери тариф.")
        return
    if issued_clients[user_id].get("paid"):
        await message.answer("✅ Ты уже сообщил об оплате, жди подтверждения от администратора.")
        return
    issued_clients[user_id]["paid"] = True

    tariff_key = issued_clients[user_id]["tariff"]
    username = user.username or user.first_name
    notification = format_payment_notification(username, user_id, tariff_key)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{user_id}"))
    await bot.send_message(ADMIN_GROUP_ID, notification, reply_markup=kb)
    await message.answer("🕐 Оплата зарегистрирована! Жди подтверждения от администратора.", reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"))
async def admin_confirm(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    if user_id not in issued_clients:
        return
    priv = generate_private_key()
    ip = generate_client_ip()
    issued_clients[user_id]["private_key"] = priv
    issued_clients[user_id]["ip"] = ip
    days = TARIFFS[issued_clients[user_id]["tariff"]]["days"]

    # Рефералка
    ref = issued_clients[user_id].get("referral_from")
    if ref and ref in issued_clients:
        issued_clients[ref]["subscription_expire"] += timedelta(days=7)
        days += 7

    issued_clients[user_id]["subscription_expire"] = datetime.now() + timedelta(days=days)
    config = generate_wg_config(priv, ip)
    filename = f"vpn_{user_id}.conf"
    with open(filename, "w") as f:
        f.write(config)

    await bot.send_document(user_id, InputFile(filename), caption=
        "🎉 Оплата подтверждена! Вот твой конфиг-файл WireGuard.

"
        "📱 Просто открой этот файл в приложении WireGuard, и включи VPN одной кнопкой!

"
        "Если ещё не установил приложение:
"
        "📲 Android: https://play.google.com/store/apps/details?id=com.wireguard.android
"
        "🍏 iOS: https://apps.apple.com/app/wireguard/id1441195209

"
        "Безопасного интернета! 🔒🌐", reply_markup=main_menu()
    )
    await callback_query.message.edit_reply_markup()

@dp.message_handler(lambda m: m.text == "🤝 Реферальная система")
async def referral(message: types.Message):
    ref_link = f"https://t.me/{BOT_USERNAME}?start={REFERRAL_PREFIX}{message.from_user.id}"
    await message.answer(f"🎁 <b>Приглашай друзей и получай +7 дней за каждого!</b>

"
                         f"🔗 Твоя ссылка: {ref_link}

"
                         f"📅 Им начислится +7 дней, а тебе — тоже!
"
                         f"💥 Делись и продлевай VPN бесплатно! 🚀", reply_markup=main_menu())

@dp.message_handler()
async def fallback(message: types.Message):
    await message.answer("🤖 Пожалуйста, выбери действие из меню ниже 👇", reply_markup=main_menu())

async def notify_expiring_users():
    while True:
        now = datetime.now()
        for uid, data in issued_clients.items():
            exp = data.get("subscription_expire")
            if exp and 0 < (exp - now).days <= 3 and not data.get("reminded"):
                await bot.send_message(uid, f"⏰ Напоминание: твоя VPN-подписка заканчивается через {(exp - now).days} дня(ей). Продли её, чтобы не потерять доступ! 🔄")
                issued_clients[uid]["reminded"] = True
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(notify_expiring_users())
    executor.start_polling(dp, skip_updates=True)
