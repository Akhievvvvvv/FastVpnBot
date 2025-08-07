import logging
import asyncio
import subprocess
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputFile
from aiogram.utils import executor
import sqlite3
import os

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'

SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820
SERVER_INTERFACE = 'wg0'

ADMIN_GROUP_ID = -1002593269045
BOT_USERNAME = 'FastVpn_bot_bot'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot)

TARIFFS = {
    "1": {"name": "1 месяц", "price": 99, "days": 30},
    "3": {"name": "3 месяца", "price": 249, "days": 90},
    "5": {"name": "5 месяцев", "price": 449, "days": 150}
}

REF_PREFIX = "ref_"

DB_PATH = 'vpn_users.db'

# Инициализация базы
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
      CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        private_key TEXT,
        public_key TEXT,
        ip TEXT,
        tariff TEXT,
        subscription_expire TEXT,
        paid INTEGER,
        ref_from INTEGER
      )
    ''')
    conn.commit()
    conn.close()

def db_execute(query, args=(), fetch=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, args)
    data = None
    if fetch:
        data = c.fetchone()
    conn.commit()
    conn.close()
    return data

def db_fetchall(query, args=()):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, args)
    data = c.fetchall()
    conn.commit()
    conn.close()
    return data

def get_user(user_id):
    row = db_execute("SELECT * FROM users WHERE user_id=?", (user_id,), fetch=True)
    if not row:
        return None
    keys = ['user_id', 'private_key', 'public_key', 'ip', 'tariff', 'subscription_expire', 'paid', 'ref_from']
    user = dict(zip(keys, row))
    if user['subscription_expire']:
        user['subscription_expire'] = datetime.fromisoformat(user['subscription_expire'])
    else:
        user['subscription_expire'] = None
    user['paid'] = bool(user['paid'])
    return user

def save_user(user):
    sub_expire_str = user['subscription_expire'].isoformat() if user['subscription_expire'] else None
    paid_int = 1 if user.get('paid') else 0
    db_execute('''
      INSERT OR REPLACE INTO users (user_id, private_key, public_key, ip, tariff, subscription_expire, paid, ref_from)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user['user_id'], user['private_key'], user['public_key'], user['ip'], user['tariff'], sub_expire_str, paid_int, user['ref_from']))

def generate_private_key():
    result = subprocess.run(['wg', 'genkey'], capture_output=True, text=True)
    return result.stdout.strip()

def generate_public_key(private_key):
    process = subprocess.Popen(['wg', 'pubkey'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    pubkey, _ = process.communicate(input=private_key)
    return pubkey.strip()

def get_all_assigned_ips():
    rows = db_fetchall("SELECT ip FROM users WHERE ip IS NOT NULL")
    return set(row[0] for row in rows)

def generate_client_ip():
    assigned_ips = get_all_assigned_ips()
    for last_octet in range(2, 255):
        ip = f"10.0.0.{last_octet}"
        if ip not in assigned_ips:
            return ip
    raise Exception("IP addresses exhausted!")

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
    args = message.get_args()
    ref = None
    if args.startswith(REF_PREFIX):
        try:
            ref = int(args[len(REF_PREFIX):])
        except:
            ref = None
    user = get_user(user_id)
    if not user:
        user = {
            'user_id': user_id,
            'private_key': None,
            'public_key': None,
            'ip': None,
            'tariff': None,
            'subscription_expire': None,
            'paid': False,
            'ref_from': ref
        }
        save_user(user)

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
    user = get_user(user_id)
    if not user:
        await message.answer("❗ Произошла ошибка, попробуй /start")
        return
    for key, val in TARIFFS.items():
        if message.text == f"{val['name']} — {val['price']}₽":
            user['tariff'] = key
            user['paid'] = False
            save_user(user)
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
    user = get_user(user_id)
    if not user or not user.get("tariff"):
        await message.answer("❗ Сначала выбери тариф.")
        return
    if user["paid"]:
        await message.answer("⏳ Уже жду подтверждение от администратора.")
        return
    user["paid"] = True
    save_user(user)

    tariff = TARIFFS[user["tariff"]]
    confirm_button = types.InlineKeyboardMarkup()
    confirm_button.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{user_id}"))
    msg = (
        f"💸 <b>Новый платёж:</b>\n\n"
        f"👤 Пользователь: @{message.from_user.username if message.from_user.username else 'не указан'}\n"
        f"🆔 ID: {user_id}\n"
        f"📦 Тариф: {tariff['name']} — {tariff['price']}₽\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await bot.send_message(ADMIN_GROUP_ID, msg, reply_markup=confirm_button)
    await message.answer("🕐 Оплата зафиксирована! Жди подтверждения 👀", reply_markup=main_menu())

def add_peer_to_wg(public_key, client_ip):
    # Добавляем пир в WireGuard
    try:
        subprocess.run(['wg', 'set', SERVER_INTERFACE, 'peer', public_key, 'allowed-ips', f"{client_ip}/32"], check=True)
        return True
    except Exception as e:
        logging.error(f"Ошибка добавления пира в wg
