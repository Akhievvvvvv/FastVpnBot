# bot.py
import logging
import random
import string
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import aiosqlite

# ---------------- CONFIG ----------------
API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'  # <- вставьте ваш токен
ADMIN_ID = 7231676236               # <- ваш юзер id (тот, кто подтверждает оплаты)
ADMIN_GROUP_ID = -1002593269045     # <- группа/чат куда приходят платежи (можно поставить ADMIN_ID для личных уведомлений)
BOT_USERNAME = "FastVpn_bot_bot"    # <- имя бота (без @)
DB_PATH = "fastvpn.db"
# ----------------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot)

# Тарифы
TARIFFS = {
    "1m": {"name": "1 месяц", "price": 99, "days": 30},
    "3m": {"name": "3 месяца", "price": 249, "days": 90},
    "5m": {"name": "5 месяцев", "price": 399, "days": 150}
}

# ---------------- DB ----------------
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
            subscription_end TEXT
        )''')
        await db.commit()

async def add_user(user_id: int, username: str, ref: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, ref) VALUES (?, ?, ?)",
                         (user_id, username, ref))
        await db.commit()

async def set_user_plan(user_id: int, plan: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, user_id))
        await db.commit()

async def set_user_paid_and_subscription(user_id: int, paid: bool, subscription_end: datetime, payment_time: datetime = None):
    pt = payment_time.isoformat() if payment_time else None
    se = subscription_end.isoformat() if subscription_end else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET paid = ?, payment_time = ?, subscription_end = ? WHERE user_id = ?",
                         (1 if paid else 0, pt, se, user_id))
        await db.commit()

async def set_vpn_key(user_id: int, key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET vpn_key = ? WHERE user_id = ?", (key, user_id))
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, username, ref, paid, plan, payment_time, vpn_key, subscription_end FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row

async def get_all_paid_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, subscription_end FROM users WHERE paid = 1")
        rows = await cur.fetchall()
        return rows

# ---------------- Helpers ----------------
def generate_vpn_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=40))

def pretty_dt(iso_str: str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return iso_str

def welcome_text(user: types.User):
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
    return (
        "╔══════════════════════════╗\n"
        "✨👋 <b>Добро пожаловать в FastVPN!</b> 👋✨\n"
        "╚══════════════════════════╝\n\n"
        "<b>Почему FastVPN?</b>\n"
        "🌐 Доступ к любым сайтам и приложениям\n"
        "🔒 Конфиденциальность и шифрование\n"
        "⚡ Быстрое и стабильное соединение\n"
        "📱 Поддержка iOS и Android (инструкция внизу)\n\n"
        "<b>Тарифы:</b>\n"
        "🗓️ 1 месяц — 99₽\n"
        "🗓️ 3 месяца — 249₽\n"
        "🗓️ 5 месяцев — 399₽\n\n"
        "<b>Реферальная программа:</b>\n"
        "Приглашайте друзей — получите +7 дней, если друг перейдёт по вашей ссылке и оплатит тариф.\n"
        f"Твоя реферальная ссылка:\n<a href='{ref_link}'>Пригласить друзей</a>\n\n"
        "<b>Как начать:</b>\n"
        "1️⃣ Нажмите тариф в меню\n"
        "2️⃣ Оплатите по реквизитам\n"
        "3️⃣ Нажмите «✅ Оплатил(а)» — админ проверит и подтвердит\n"
        "4️⃣ Получите свой уникальный VPN-ключ и вставьте его в приложение\n\n"
        "<b>Реквизиты:</b>\n+7 932 222 99 30 (Ozon Bank)\n\n"
        "Если что-то непонятно — напишите сюда.\n"
        "🎉 Спасибо, что выбрали FastVPN!"
    )

def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        kb.add(InlineKeyboardButton(f"{t['name']} — {t['price']}₽", callback_data=f"tariff_{key}"))
    kb.add(InlineKeyboardButton("📲 Скачать для iPhone", url="https://apps.apple.com/app/outline-vpn/id1356177741"))
    kb.add(InlineKeyboardButton("🤖 Скачать для Android", url="https://play.google.com/store/apps/details?id=org.outline.android.client"))
    kb.add(InlineKeyboardButton("👥 Реферальная программа", callback_data="ref_info"))
    return kb

def paid_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Оплатил(а)", callback_data="paid"))
    return kb

def admin_confirm_kb(user_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_{user_id}"))
    return kb

# ---------------- Handlers ----------------

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    args = message.get_args() or ""
    ref = None
    if args.startswith("ref_"):
        ref = args.split("ref_")[1]
        # защитимся, чтобы пользователь не мог сам себя рефить
        if ref == str(message.from_user.id):
            ref = None
    await add_user(message.from_user.id, message.from_user.username or "", ref)
    await message.answer(welcome_text(message.from_user), disable_web_page_preview=True, reply_markup=main_menu_kb())

@dp.callback_query_handler(lambda c: c.data == "ref_info")
async def cb_ref_info(call: types.CallbackQuery):
    user = call.from_user
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
    text = (
        "👥 <b>Реферальная программа</b>\n\n"
        "Приглашайте друзей по вашей уникальной ссылке. Как только приглашённый " 
        "пользователь перейдёт по ссылке и оплатит любой тариф — вы получите +7 дней к подписке.\n\n"
        f"Ваша ссылка: <a href='{ref_link}'>Пригласить</a>\n\n"
        "П.С. Бонус даётся только после того, как приглашённый оплатит и админ подтвердит оплату."
    )
    await call.answer()
    await call.message.answer(text, disable_web_page_preview=True)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("tariff_"))
async def cb_tariff(call: types.CallbackQuery):
    key = call.data.split("tariff_")[1]
    if key not in TARIFFS:
        await call.answer("Неверный тариф.", show_alert=True)
        return
    t = TARIFFS[key]
    await set_user_plan(call.from_user.id, key)
    text = (
        f"Вы выбрали: <b>{t['name']}</b>\nЦена: <b>{t['price']}₽</b>\n\n"
        "💳 Переведите оплату на реквизиты ниже, затем нажмите кнопку «Оплатил(а)».\n\n"
        "<b>Реквизиты:</b>\n+7 932 222 99 30 (Ozon Bank)\n\n"
        "После подтверждения оплаты админ пришлёт вам ваш личный ключ."
    )
    await call.answer()
    await call.message.edit_text(text, parse_mode='HTML', reply_markup=paid_kb())

@dp.callback_query_handler(lambda c: c.data == "paid")
async def cb_paid(call: types.CallbackQuery):
    user = await get_user(call.from_user.id)
    if not user or not user[4]:
        await call.answer("Сначала выберите тариф.", show_alert=True)
        return
    plan_key = user[4]
    t = TARIFFS.get(plan_key)
    if not t:
        await call.answer("Ошибка тарифа.", show_alert=True)
        return

    # Уведомление в админ-группу с кнопкой подтверждения
    username = user[1] or f"{call.from_user.id}"
    text = (f"💸 <b>Новый платёж — подтверждение требуется</b>\n\n"
            f"👤 Пользователь: @{username} (ID: {call.from_user.id})\n"
            f"📦 Тариф: {t['name']} — {t['price']}₽\n"
            f"⏰ Время: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    try:
        await bot.send_message(ADMIN_GROUP_ID, text, parse_mode='HTML', reply_markup=admin_confirm_kb(call.from_user.id))
    except Exception:
        # если отсылка в группу провалилась, высылать администратору личное сообщение
        await bot.send_message(ADMIN_ID, text, parse_mode='HTML', reply_markup=admin_confirm_kb(call.from_user.id))
    await call.answer("Запрос на проверку оплаты отправлен администратору.", show_alert=True)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_"))
async def cb_confirm(call: types.CallbackQuery):
    # только админ может подтверждать
    if call.from_user.id != ADMIN_ID:
        await call.answer("У вас нет прав для этого.", show_alert=True)
        return

    try:
        target_id = int(call.data.split("confirm_")[1])
    except:
        await call.answer("Неверный ID.", show_alert=True)
        return

    user = await get_user(target_id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    plan_key = user[4]
    if not plan_key or plan_key not in TARIFFS:
        await call.answer("У пользователя не выбран тариф.", show_alert=True)
        return
    tariff = TARIFFS[plan_key]
    now = datetime.utcnow()

    # если у пользователя уже есть подписка — продлеваем от текущего конца, иначе от now
    existing_end = None
    if user[7]:
        try:
            existing_end = datetime.fromisoformat(user[7])
        except:
            existing_end = None
    if existing_end and existing_end > now:
        new_end = existing_end + timedelta(days=tariff['days'])
    else:
        new_end = now + timedelta(days=tariff['days'])

    # помечаем оплату и срок
    await set_user_paid_and_subscription(target_id, True, new_end, payment_time=now)

    # генерируем ключ, если нет
    vpn_key = user[6] or generate_vpn_key()
    await set_vpn_key(target_id, vpn_key)

    # если у пользователя есть реферер — начисляем ему +7 дней
    ref = user[2]  # строка
    if ref:
        try:
            ref_id = int(ref)
            # не даём самому себе бонус
            if ref_id != target_id:
                ref_user = await get_user(ref_id)
                # рассчитаем новый конец у реферера
                now2 = datetime.utcnow()
                if ref_user and ref_user[7]:
                    try:
                        ref_existing_end = datetime.fromisoformat(ref_user[7])
                    except:
                        ref_existing_end = None
                else:
                    ref_existing_end = None
                if ref_existing_end and ref_existing_end > now2:
                    ref_new_end = ref_existing_end + timedelta(days=7)
                else:
                    ref_new_end = now2 + timedelta(days=7)
                # применим и (если у реферера нет vpn_key) создадим
                await set_user_paid_and_subscription(ref_id, True, ref_new_end, payment_time=ref_user[5] and datetime.fromisoformat(ref_user[5]) or now2)
                if ref_user and not ref_user[6]:
                    # сгенерируем ключ для реферера, чтобы он мог сразу пользоваться
                    await set_vpn_key(ref_id, generate_vpn_key())
                # оповестим реферера
                try:
                    await bot.send_message(ref_id, "🎉 Вы получили +7 дней бесплатного доступа за приглашённого друга! Проверьте /status.")
                except Exception:
                    pass
        except Exception:
            pass

    # отправляем пользователю ключ и инструкцию
    try:
        await bot.send_message(target_id,
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"🔑 Ваш уникальный VPN-ключ:\n<code>{vpn_key}</code>\n\n"
            "📲 Как использовать:\n"
            "1) Установите приложение Outline (iOS / Android).\n"
            "2) В приложении выберите добавить ключ/activate и вставьте этот ключ.\n"
            "3) Включите VPN и пользуйтесь.\n\n"
            f"⏳ Подписка активна до: <b>{new_end.strftime('%Y-%m-%d %H:%M:%S UTC')}</b>\n\n"
            "Если возникнут вопросы — напишите в этот чат.")
    except Exception:
        await call.answer("Не удалось отправить ключ пользователю (возможно, он заблокировал бота).", show_alert=True)
        # но всё равно подтверждаем

    # уведомляем в админ-группе что подтверждено
    try:
        await bot.send_message(ADMIN_GROUP_ID, f"✅ Подтверждение выполнено для пользователя ID {target_id}. Подписка до {new_end.strftime('%Y-%m-%d %H:%M:%S UTC')}.")
    except:
        pass

    await call.answer("Оплата подтверждена и ключ выслан пользователю.")
    try:
        # убираем кнопки у сообщения с подтверждением (если это нужно)
        await call.message.edit_reply_markup(None)
    except:
        pass

# /status
@dp.message_handler(commands=['status'])
async def cmd_status(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.reply("Вы не зарегистрированы. Отправьте /start, чтобы начать.")
        return
    paid = bool(user[3])
    plan = user[4] or "—"
    vpn_key = user[6] or "—"
    sub_end = pretty_dt(user[7])
    text = (
        "<b>📊 Статус подписки</b>\n\n"
        f"План: <b>{plan}</b>\n"
        f"Оплачено: <b>{'Да' if paid else 'Нет'}</b>\n"
        f"Окончание подписки: <b>{sub_end}</b>\n\n"
        f"🔑 Ваш ключ: <code>{vpn_key}</code>\n\n"
        "Чтобы получить ключ после оплаты — дождитесь подтверждения администратора."
    )
    await message.reply(text)

# ---------------- Background tasks ----------------

async def subscription_watcher():
    await asyncio.sleep(5)  # короткая пауза при старте
    while True:
        try:
            rows = await get_all_paid_users()
            now = datetime.utcnow()
            for r in rows:
                uid = r[0]
                end_str = r[1]
                if not end_str:
                    continue
                try:
                    end = datetime.fromisoformat(end_str)
                except:
                    continue
                days_left = (end - now).days
                # уведомления за 3,2,1 день
                if days_left in (3,2,1):
                    try:
                        await bot.send_message(uid, f"⏳ Ваша подписка истекает через {days_left} {'день' if days_left==1 else 'дня' if days_left in (2,3) else 'дней'}. Не забудьте продлить.")
                    except:
                        pass
                # если истекла
                if end < now:
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE users SET paid = 0, plan = NULL, vpn_key = NULL, payment_time = NULL, subscription_end = NULL WHERE user_id = ?", (uid,))
                        await db.commit()
                    try:
                        await bot.send_message(uid, "⛔ Ваша подписка истекла. Вы потеряли доступ — чтобы возобновить, выберите тариф и оплатите снова.")
                    except:
                        pass
        except Exception as e:
            logging.exception("Ошибка в subscription_watcher: %s", e)
        # проверяем каждые 6 часов
        await asyncio.sleep(60 * 60 * 6)

# ---------------- Startup ----------------
async def on_startup(dp):
    await db_init()
    # запустим фонового наблюдателя
    loop = asyncio.get_event_loop()
    loop.create_task(subscription_watcher())
    logging.info("Бот запущен. База и фоновые задачи инициализированы.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
