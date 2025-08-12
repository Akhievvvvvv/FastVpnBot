#!/usr/bin/env python3
# bot.py — FastVpnBot (complete)
import logging
import asyncio
import ssl
import json
from datetime import datetime, timedelta

import certifi
import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
API_TOKEN = "8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8"
ADMIN_CHAT_ID = -1002593269045
ADMIN_USER_ID = 7231676236   # твой ID для подтверждения оплат (через callback/button)
BOT_USERNAME = "FastVpn_bot_bot"

OUTLINE_API_URL = "https://109.196.100.159:62185/IAdSwxfb6r7xmb1KMLGB-w"
OUTLINE_CERT_SHA256 = "65BB55F76E33DB8492917F5D5E37530F1AA2FB7A177C1C8A1F2ADC1390766ABC"

DATABASE = "fastvpn_bot.db"

# Тарифы (ключи для БД/логики)
TARIFFS = {
    "1m": {"name": "1 месяц", "price": 99,  "days": 30},
    "3m": {"name": "3 месяца", "price": 149, "days": 90},
    "5m": {"name": "5 месяцев", "price": 399, "days": 150},
}

REKVIZITES = "+7 932 222 99 30 (Ozon Bank)"

# ==========================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# SSL for Outline API (disable strict verification because server uses custom cert)
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ----------------- Database -----------------

async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                referrer INTEGER,
                subscription_end TEXT,
                outline_key_id TEXT,
                outline_access_url TEXT
            )
        """)

        # Проверяем и добавляем колонку subscription_end, если её нет
        try:
            await db.execute("SELECT subscription_end FROM users LIMIT 1")
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN subscription_end TEXT")

        # Проверяем и добавляем колонку outline_key_id, если её нет
        try:
            await db.execute("SELECT outline_key_id FROM users LIMIT 1")
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN outline_key_id TEXT")

        # Проверяем и добавляем колонку outline_access_url, если её нет
        try:
            await db.execute("SELECT outline_access_url FROM users LIMIT 1")
        except aiosqlite.OperationalError:
            await db.execute("ALTER TABLE users ADD COLUMN outline_access_url TEXT")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tariff_key TEXT,
                amount INTEGER,
                status TEXT, -- pending, confirmed, canceled
                created_at TEXT,
                confirmed_at TEXT,
                outline_key_id TEXT,
                outline_access_url TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer INTEGER,
                referee INTEGER
            )
        """)
        await db.commit()
    logger.info("Initialized DB")

# helper DB operations
async def add_user_to_db(user_id: int, username: str = "", ref: int | None = None):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id, username, referrer) VALUES (?, ?, ?)",
                         (user_id, username or "", ref))
        if ref and ref != user_id:
            try:
                await db.execute("INSERT OR IGNORE INTO referrals(referrer, referee) VALUES (?, ?)", (ref, user_id))
            except Exception:
                pass
        await db.commit()

async def get_user_row(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        cur = await db.execute("SELECT user_id, username, referrer, subscription_end, outline_key_id, outline_access_url FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone()

async def save_subscription(user_id: int, end_dt: datetime, outline_key_id: str | None, outline_access_url: str | None):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            UPDATE users SET subscription_end = ?, outline_key_id = ?, outline_access_url = ? WHERE user_id = ?
        """, (end_dt.isoformat(), outline_key_id, outline_access_url, user_id))
        await db.commit()

async def create_payment_record(user_id: int, tariff_key: str):
    tariff = TARIFFS[tariff_key]
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DATABASE) as db:
        cur = await db.execute("""
            INSERT INTO payments(user_id, tariff_key, amount, status, created_at) VALUES (?, ?, ?, 'pending', ?)
        """, (user_id, tariff_key, tariff["price"], now))
        await db.commit()
        return cur.lastrowid

async def set_payment_confirmed(payment_id: int, outline_key_id: str | None, outline_access_url: str | None):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            UPDATE payments SET status='confirmed', confirmed_at=?, outline_key_id=?, outline_access_url=? WHERE id=?
        """, (now, outline_key_id, outline_access_url, payment_id))
        await db.commit()

async def get_payment(payment_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        cur = await db.execute("SELECT id, user_id, tariff_key, amount, status, created_at FROM payments WHERE id=?", (payment_id,))
        return await cur.fetchone()

async def get_pending_payments():
    async with aiosqlite.connect(DATABASE) as db:
        cur = await db.execute("SELECT id, user_id, tariff_key, amount, created_at FROM payments WHERE status='pending'")
        return await cur.fetchall()

async def get_active_subscriptions_expired(before_dt: datetime):
    async with aiosqlite.connect(DATABASE) as db:
        cur = await db.execute("SELECT user_id, subscription_end, outline_key_id FROM users WHERE subscription_end IS NOT NULL")
        rows = await cur.fetchall()
        expired = []
        for r in rows:
            user_id, subscription_end, outline_key_id = r
            if not subscription_end:
                continue
            try:
                end_dt = datetime.fromisoformat(subscription_end)
            except Exception:
                continue
            if end_dt <= before_dt:
                expired.append((user_id, outline_key_id))
        return expired

async def extend_subscription(user_id: int, extra_days: int):
    row = await get_user_row(user_id)
    now = datetime.utcnow()
    if row and row[3]:
        try:
            existing = datetime.fromisoformat(row[3])
        except Exception:
            existing = now
    else:
        existing = now
    if existing > now:
        new_end = existing + timedelta(days=extra_days)
    else:
        new_end = now + timedelta(days=extra_days)
    await save_subscription(user_id, new_end, row[4] if row else None, row[5] if row else None)
    return new_end

# ----------------- Outline API -----------------

async def outline_create_access_key():
    """
    Call Outline server to create access key.
    Returns tuple (key_id, access_url) if success, otherwise (None, None).
    """
    url = f"{OUTLINE_API_URL}/access-keys"
    headers = {
        "Content-Type": "application/json",
        "X-Outline-Server-Cert-Sha256": OUTLINE_CERT_SHA256
    }
    payload = {"name": "FastVpn user key", "accessUrl": None}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, ssl=ssl_context, timeout=30) as resp:
                text = await resp.text()
                if resp.status in (200, 201):
                    data = json.loads(text) if text else {}
                    # Outline typical response contains "id" and "accessUrl"
                    key_id = data.get("id") or data.get("key") or data.get("accessKeyId")
                    access_url = data.get("accessUrl") or data.get("access_url") or data.get("url") or data.get("accessKey")
                    return key_id, access_url
                else:
                    logger.error("Outline create failed %s: %s", resp.status, text)
                    return None, None
    except Exception as e:
        logger.exception("Outline create error: %s", e)
        return None, None

async def outline_delete_access_key(key_id: str):
    """
    Delete access key by id if API supports DELETE /access-keys/{id}
    Returns True on success or if no id provided (nothing to do).
    """
    if not key_id:
        return True
    url = f"{OUTLINE_API_URL}/access-keys/{key_id}"
    headers = {"X-Outline-Server-Cert-Sha256": OUTLINE_CERT_SHA256}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers, ssl=ssl_context, timeout=30) as resp:
                if resp.status in (200, 204):
                    return True
                else:
                    text = await resp.text()
                    logger.warning("Outline delete returned %s: %s", resp.status, text)
                    return False
    except Exception as e:
        logger.exception("Outline delete error: %s", e)
        return False
# ----------------- Keyboards & texts -----------------

WELCOME_TEXT = (
    "✨🔥 <b>Добро пожаловать в FastVPN — твой надёжный щит в интернете!</b> 🔥✨\n\n"
    "🌍 Защити свои данные и получи мгновенный доступ к качественному VPN без заморочек.\n\n"
    "🔐 Полная анонимность и безопасность\n"
    "⚡ Молниеносная скорость без ограничений\n"
    "🎁 Реферальная программа — пригласи друзей и получи бонусные дни бесплатно!\n\n"
    "Выбирай действие ниже и начни путешествие в безопасный интернет уже сейчас! 🚀👇"
)

def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📃 Тарифы и преимущества 💎", callback_data="show_tariffs"),
        InlineKeyboardButton("👥 Реферальная система — бонусы 🎉", callback_data="show_referral"),
        InlineKeyboardButton("🛠 Инструкция по подключению ⚙️", callback_data="show_instruction"),
        InlineKeyboardButton("💳 Реквизиты для оплаты 💰", callback_data="show_rekviz")
    )
    return kb

def tariffs_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for key in ("1m", "3m", "5m"):
        kb.add(InlineKeyboardButton(f"{TARIFFS[key]['name']} — {TARIFFS[key]['price']}₽", callback_data=f"tariff:{key}"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main"))
    return kb

def rekviz_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="main"))
    return kb

def admin_confirm_kb(user_id: int, payment_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(f"✅ Подтвердить оплату {user_id} (#{payment_id})",
                             callback_data=f"admin_confirm:{user_id}:{payment_id}")
    )
    return kb

REF_TEXT = (
    "👥 <b>Реферальная система</b>\n\n"
    "Делись своей ссылкой — за каждого приглашённого, оплатившего подписку, вы получите +7 дней.\n\n"
    "Ваша реферальная ссылка будет показана ниже."
)

INSTRUCTION_TEXT = (
    "📱 <b>Инструкция — как подключиться через Outline</b>\n\n"
    "1) Установите приложение Outline (iOS/Android).\n"
    "2) Получите от бота уникальный ключ после подтверждения оплаты.\n"
    "3) В приложении Outline выберите Add key / Access key и вставьте ключ.\n\n"
    "Если что-то не работает — пишите администратору."
)

REKVIZ_TEXT = (
    f"💳 <b>Реквизиты для оплаты</b>\n\n{REKVIZITES}\n\n"
    "После оплаты нажмите «✅ Я оплатил(а)» — админ получит уведомление и подтвердит платёж.\n\n"
    "Тарифы:\n" +
    "\n".join([f"• {TARIFFS[k]['name']} — {TARIFFS[k]['price']}₽" for k in ("1m","3m","5m")])
)

# ----------------- Handlers -----------------

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    args = message.get_args() or ""
    ref = None
    if args:
        import re
        m = re.search(r"ref[_=]?(\d+)", args)
        if m:
            try:
                r = int(m.group(1))
                if r != message.from_user.id:
                    ref = r
            except:
                ref = None
    await add_user_to_db(message.from_user.id, message.from_user.username or "", ref)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())

@dp.callback_query_handler(lambda c: c.data == "main")
async def cb_main(query: types.CallbackQuery):
    await query.answer()
    await query.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())

@dp.callback_query_handler(lambda c: c.data in ["show_rekviz", "show_rekvizity"])
async def cb_rekviz(query: types.CallbackQuery):
    await query.answer()
    await query.message.edit_text(REKVIZ_TEXT, reply_markup=rekviz_kb())

@dp.callback_query_handler(lambda c: c.data in ["show_instruction", "instruction"])
async def cb_instruction(query: types.CallbackQuery):
    await query.answer()
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="main"))
    await query.message.edit_text(INSTRUCTION_TEXT, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "show_tariffs")
async def cb_tariffs(query: types.CallbackQuery):
    await query.answer()
    await query.message.edit_text("📃 <b>Выберите тариф:</b>", reply_markup=tariffs_kb())

@dp.callback_query_handler(lambda c: c.data.startswith("tariff:"))
async def cb_select_tariff(query: types.CallbackQuery):
    tariff_key = query.data.split(":",1)[1]
    if tariff_key not in TARIFFS:
        await query.answer("Неверный тариф", show_alert=True)
        return

    payment_id = await create_payment_record(query.from_user.id, tariff_key)

    text = (
        f"🔥 <b>Вы выбрали тариф:</b> <i>{TARIFFS[tariff_key]['name']}</i>\n"
        f"💰 <b>Цена:</b> {TARIFFS[tariff_key]['price']}₽\n\n"
        f"💳 <b>Реквизиты для оплаты:</b>\n"
        f"+7 932 222 99 30 (Ozon Bank)\n\n"
        f"<i>Номер платежа:</i> <b>#{payment_id}</b>\n"
        "После оплаты нажмите «✅ Я оплатил(а)» — админ получит запрос на подтверждение."
    )

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Я оплатил(а)", callback_data=f"paid:{payment_id}"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="show_tariffs"))

    await query.message.edit_text(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("paid"))
async def cb_user_paid(query: types.CallbackQuery):
    parts = query.data.split(":")
    if len(parts) != 2:
        await query.answer("Ошибка данных.", show_alert=True)
        return
    payment_id = int(parts[1])
    payment = await get_payment(payment_id)
    if not payment:
        await query.answer("Платёж не найден.", show_alert=True)
        return
    if payment[4] != "pending":
        await query.answer("Платёж уже в обработке.", show_alert=True)
        return
    # Далее можно добавить уведомление администратору и обработку

    # notify admin with confirm button (callback contains user_id and payment_id)
    user_id = payment[1]
    tariff_key = payment[2]
    amount = payment[3]
    text = (
        f"📣 <b>Поступил запрос на подтверждение оплаты</b>\n\n"
        f"Пользователь: <a href='tg://user?id={user_id}'>ID {user_id}</a>\n"
        f"Тариф: {TARIFFS[tariff_key]['name']} — {amount}₽\n"
        f"Платёж ID: #{payment_id}\n\n"
        "Проверьте платёж и подтвердите (кнопка ниже) или используйте команду\n"
        f"/activate {user_id} {payment_id}"
    )
    try:
        await bot.send_message(ADMIN_CHAT_ID, text, reply_markup=admin_confirm_kb(user_id, payment_id))
    except Exception as e:
        logger.exception("Failed to send admin message: %s", e)
    await query.answer("Запрос отправлен администратору. Ожидайте подтверждения.")
    await query.message.edit_text("Спасибо! Запрос отправлен администратору. Ожидайте подтверждения.")

@dp.callback_query_handler(lambda c: c.data.startswith("admin_confirm:"))
async def cb_admin_confirm(query: types.CallbackQuery):
    # data format admin_confirm:user_id:payment_id
    if query.from_user.id != ADMIN_USER_ID:
        await query.answer("У вас нет прав.", show_alert=True)
        return
    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Неверные данные.", show_alert=True)
        return
    user_id = int(parts[1])
    payment_id = int(parts[2])
    await process_activation_by_admin(user_id, payment_id, invoked_by=query.from_user.id, reply_message=query.message)
    await query.answer("Подтверждение выполнено.")

@dp.message_handler(commands=["activate"])
async def cmd_activate(message: types.Message):
    # admin command: /activate <user_id> <payment_id>
    if message.from_user.id != ADMIN_USER_ID:
        await message.reply("У вас нет прав для этой команды.")
        return
    args = message.get_args().split()
    if len(args) < 2:
        await message.reply("Использование: /activate <user_id> <payment_id>")
        return
    try:
        user_id = int(args[0]); payment_id = int(args[1])
    except:
        await message.reply("Неверные аргументы.")
        return
    await message.reply("Активирую подписку...")
    await process_activation_by_admin(user_id, payment_id, invoked_by=message.from_user.id, reply_message=message)

async def process_activation_by_admin(user_id: int, payment_id: int, invoked_by: int, reply_message: types.Message | None = None):
    payment = await get_payment(payment_id)
    if not payment:
        if reply_message:
            await reply_message.reply("Платеж не найден.")
        return
    if payment[1] != user_id:
        if reply_message:
            await reply_message.reply("Платёж не принадлежит указанному пользователю.")
        return
    if payment[4] != "pending":
        if reply_message:
            await reply_message.reply("Платёж уже обработан.")
        return

    tariff_key = payment[2]
    days = TARIFFS[tariff_key]["days"]

    # create outline key
    key_id, access_url = await outline_create_access_key()
    if not (key_id or access_url):
        if reply_message:
            await reply_message.reply("Ошибка при создании ключа Outline. Сначала свяжитесь с админом.")
        return

    # mark payment confirmed
    await set_payment_confirmed(payment_id, key_id, access_url)

    # compute new subscription end (extend if already active)
    user_row = await get_user_row(user_id)
    now = datetime.utcnow()
    if user_row and user_row[3]:
        try:
            existing_end = datetime.fromisoformat(user_row[3])
        except:
            existing_end = now
    else:
        existing_end = now

    if existing_end > now:
        new_end = existing_end + timedelta(days=days)
    else:
        new_end = now + timedelta(days=days)

    # save subscription and outline key info to user
    await save_subscription(user_id, new_end, key_id, access_url)

    # if user has a referrer and hasn't been rewarded earlier (we reward on activation)
    if user_row and user_row[2]:
        referrer = user_row[2]
        # give referrer +7 days
        await extend_subscription(referrer, 7)
        # optionally notify referrer
        try:
            await bot.send_message(referrer, f"✅ Вам начислено +7 дней за приглашение пользователя (ID {user_id}).")
        except Exception:
            pass

        # notify user with key and end date
    end_str = new_end.strftime("%Y-%m-%d %H:%M:%S UTC")
    user_text = (
        f"🎉 <b>Оплата подтверждена!</b>\n\n"
        f"Ваш тариф: <b>{TARIFFS[tariff_key]['name']}</b>\n"
        f"Подписка активна до: <b>{end_str}</b>\n\n"
        "Ваш ключ Outline:\n"
        f"<code>{access_url}</code>\n\n"
        "Добавьте его в приложение Outline (Add key / Access key)."
    )
    try:
        await bot.send_message(user_id, user_text, parse_mode='HTML')
    except Exception as e:
        logger.exception("Failed to message user: %s", e)

    # update admin message or reply
    if reply_message:
        try:
            await reply_message.reply(f"Платёж #{payment_id} подтверждён — подписка активирована до {end_str}.")
        except Exception:
            pass

# ----------------- Referral info command -----------------

@dp.callback_query_handler(lambda c: c.data == "show_referral")
async def cb_show_referral(query: types.CallbackQuery):
    await query.answer()
    uid = query.from_user.id
    # build referral link
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    # get stats
    async with aiosqlite.connect(DATABASE) as db:
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer = ?", (uid,))
        total = (await cur.fetchone())[0]
        cur = await db.execute("""
            SELECT COUNT(*) FROM users u
            JOIN payments p ON p.user_id = u.user_id
            WHERE u.referrer = ? AND p.status = 'confirmed'
        """, (uid,))
        paid = (await cur.fetchone())[0]
    text = REF_TEXT + f"\n\nВаша ссылка:\n{link}\n\nВсего пришло: {total}\nОплатили: {paid}"
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="main")))

# ----------------- Background tasks -----------------

async def background_expiry_check():
    """
    Runs periodically. Finds expired subscriptions and deletes Outline keys (if possible),
    clears user's subscription fields and notifies user/admin.
    """
    while True:
        try:
            now = datetime.utcnow()
            expired = await get_active_subscriptions_expired(now)
            for user_id, outline_key_id in expired:
                # attempt to delete outline key
                deleted = await outline_delete_access_key(outline_key_id)
                # clear user's subscription fields
                async with aiosqlite.connect(DATABASE) as db:
                    await db.execute("UPDATE users SET subscription_end = NULL, outline_key_id = NULL, outline_access_url = NULL WHERE user_id = ?", (user_id,))
                    await db.commit()
                # notify user (best-effort)
                try:
                    await bot.send_message(user_id, "ℹ️ Ваша подписка истекла. Ключ был отключён. Для продления выберите тариф в боте.")
                except Exception:
                    pass
                # notify admin
                try:
                    await bot.send_message(ADMIN_CHAT_ID, f"Подписка у пользователя {user_id} истекла. Ключ удалён: {deleted}")
                except Exception:
                    pass
        except Exception as e:
            logger.exception("Error in expiry check: %s", e)
        # sleep 10 minutes
        await asyncio.sleep(600)

# ----------------- Startup / shutdown -----------------

async def on_startup(dp):
    await init_db()
    # start background task
    import asyncio
    asyncio.create_task(background_expiry_check())
    logger.info("Bot started and background tasks launched")

# ----------------- Run -----------------

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
