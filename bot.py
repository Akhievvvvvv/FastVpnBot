import logging
import asyncio
import requests
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

logging.basicConfig(level=logging.INFO)

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'
OUTLINE_API_URL = 'https://109.196.100.159:54356/op86CXDhYiq1dKmhCmG_rg'
ADMIN_GROUP_ID = -1002593269045
REF_PREFIX = "ref_"
DB_PATH = 'vpn_users.db'

bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot)

TARIFFS = {
    "1": {"name": "1 месяц", "price": 99, "days": 30},
    "3": {"name": "3 месяца", "price": 249, "days": 90},
    "5": {"name": "5 месяцев", "price": 449, "days": 150}
}

# --- DATABASE FUNCTIONS ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        outline_key_id TEXT,
        outline_access_url TEXT,
        surname TEXT,
        tariff INTEGER,
        expire_at TEXT,
        paid INTEGER,
        ref_from INTEGER
      )""")
    conn.commit()
    conn.close()

def save_user(u):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
      INSERT OR REPLACE INTO users(user_id, outline_key_id, outline_access_url, tariff, expire_at, paid, ref_from)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (u['user_id'], u.get('outline_key_id'),
          u.get('outline_access_url'), u.get('tariff'),
          u.get('expire_at').isoformat() if u.get('expire_at') else None,
          int(u.get('paid', 0)), u.get('ref_from')))
    conn.commit(); conn.close()

def load_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    keys = ['user_id','outline_key_id','outline_access_url','surname','tariff','expire_at','paid','ref_from']
    u = dict(zip(keys, row))
    if u['expire_at']:
        u['expire_at'] = datetime.fromisoformat(u['expire_at'])
    u['paid'] = bool(u['paid'])
    return u

def all_users():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT * FROM users WHERE expire_at IS NOT NULL").fetchall()
    conn.close()
    return rows

# --- OUTLINE API ---
def create_outline_key(name):
    resp = requests.post(f"{OUTLINE_API_URL}/access-keys", json={"name": name}, verify=False)
    resp.raise_for_status()
    j = resp.json()
    return j['id'], j['accessUrl']

def delete_outline_key(key_id):
    requests.delete(f"{OUTLINE_API_URL}/access-keys/{key_id}", verify=False)

# --- BOT HANDLERS ---
@dp.message_handler(commands=['start'])
async def start_cmd(msg: types.Message):
    user = load_user(msg.from_user.id)
    args = msg.get_args()
    ref = None
    if args.startswith(REF_PREFIX):
        try: ref = int(args.split("_")[1])
        except: ref = None
    if not user:
        user = {'user_id': msg.from_user.id, 'outline_key_id': None, 'outline_access_url': None,
                'tariff': None, 'expire_at': None, 'paid': False, 'ref_from': ref}
        save_user(user)
    welcome = (
        f"👋 Привет, @{msg.from_user.username or msg.from_user.first_name}!\n\n"
        "Я — FastVPN бот. После оплаты я автоматически создам тебе ссылку Outline VPN.\n"
        "Выбери тариф ⤵️"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    for k,v in TARIFFS.items():
        kb.add(InlineKeyboardButton(f"{v['name']} — {v['price']}₽", callback_data=f"tariff_{k}"))
    await msg.answer(welcome, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("tariff_"))
async def tariff_chosen(c: types.CallbackQuery):
    key = c.data.split("_")[1]
    user = load_user(c.from_user.id)
    user['tariff'] = int(key); user['paid'] = False
    save_user(user)
    v = TARIFFS[key]
    text = (f"💰 Тариф: {v['name']} — {v['price']}₽.\n\n"
            "Оплати на карту Ozon Bank:\n<code>89322229930</code>\n\n"
            "После оплаты жми ниже:")
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid"))
    await c.message.edit_text(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data=="paid")
async def paid(c: types.CallbackQuery):
    user = load_user(c.from_user.id)
    if not user or not user.get('tariff'):
        await c.answer("Сначала выбери тариф")
        return
    if user['paid']:
        await c.answer("Уже ждём подтверждения")
        return
    user['paid'] = True; save_user(user)
    v = TARIFFS[user['tariff']]
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{user['user_id']}"))
    await bot.send_message(ADMIN_GROUP_ID, f"💸 Оплата от @{c.from_user.username or c.from_user.id}, тариф: {v['name']} — {v['price']}₽", reply_markup=kb)
    await c.message.edit_text("🕐 Благодарим! Ожидай подтверждения админа.", parse_mode='HTML')

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"))
async def confirm(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_GROUP_ID and c.message.chat.id!=ADMIN_GROUP_ID:
        await c.answer("Нет доступа")
        return
    uid = int(c.data.split("_")[1]); user = load_user(uid)
    if not user or not user['paid']:
        await c.answer("Ошибка")
        return
    uid_obj = uid
    key_id, url = create_outline_key(f"user_{uid}")
    user['outline_key_id'] = key_id
    user['outline_access_url'] = url
    days = TARIFFS[user['tariff']]['days']
    user['expire_at'] = datetime.utcnow() + timedelta(days=days)
    user['paid'] = False
    save_user(user)
    await bot.send_message(uid, f"🔐 Вот твоя VPN-ссылка (через Outline):\n\n{url}\n\n📌 Действует до {user['expire_at'].strftime('%Y-%m-%d %H:%M UTC')}")
    await c.message.edit_reply_markup(None)
    await c.answer("Ключ выдан!")

# --- PERIODIC EXPIRATION CHECK ---
async def check_expire():
    while True:
        for row in all_users():
            uid, kid, url, surname, tariff, expire_at_str, paid, ref = row
            if expire_at_str:
                exp = datetime.fromisoformat(expire_at_str)
                if datetime.utcnow() > exp:
                    delete_outline_key(kid)
                    await bot.send_message(uid, "⛔ Твой VPN ключ истёк, доступ отключён.")
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("DELETE FROM users WHERE user_id=?", (uid,))
                    conn.commit(); conn.close()
        await asyncio.sleep(3600)

if __name__ == '__main__':
    init_db()
    loop = asyncio.get_event_loop()
    loop.create_task(check_expire())
    executor.start_polling(dp, skip_updates=True)
