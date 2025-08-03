import logging
import asyncio
import secrets
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'
ADMIN_GROUP_ID = -1002593269045
REKVIZITY = "💳 Оплата на карту: <code>89322229930</code> (Ozon Банк)"

SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

user_states = {}
user_refs = {}
user_subscriptions = {}
issued_configs = {}
last_ip = 2

# ——— Кнопки ———
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("💼 Тарифы", "🎁 Реферальная система")

# ——— Команды ———
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    ref = msg.get_args()
    uid = msg.from_user.id
    user_refs.setdefault(uid, {"referred_by": None, "referrals": []})
    if ref and ref.isdigit() and int(ref) != uid:
        user_refs[uid]["referred_by"] = int(ref)

    text = (
        "👋 Привет! Это простой VPN для безопасного интернета! 🌐🔒\n\n"
        "Выбирай тариф, оплачивай, и я помогу с настройкой VPN. 🚀"
    )
    await msg.answer(text, reply_markup=main_kb)

# ——— Вывод тарифов ———
@dp.message_handler(lambda m: m.text == "💼 Тарифы")
async def send_tariffs(msg: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("1 месяц — 99₽", callback_data="buy_1"),
        InlineKeyboardButton("3 месяца — 249₽", callback_data="buy_3"),
        InlineKeyboardButton("5 месяцев — 449₽", callback_data="buy_5"),
    )
    await msg.answer("📦 Выберите тариф:", reply_markup=kb)

# ——— Покупка тарифа ———
@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def handle_buy(call: types.CallbackQuery):
    period = int(call.data.split("_")[1])
    prices = {1: "99₽", 3: "249₽", 5: "449₽"}
    text = (
        f"📦 Вы выбрали: <b>{period} мес.</b> — <b>{prices[period]}</b>\n\n"
        f"{REKVIZITY}\n\n"
        "✅ После оплаты нажмите кнопку ниже:"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Оплатил(а)", callback_data=f"paid_{period}"))
    await call.message.edit_text(text, reply_markup=kb)
    user_states[call.from_user.id] = {"tarif": f"{period} месяц — {prices[period]}", "months": period}

# ——— Обработка оплаты ———
@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def handle_paid(call: types.CallbackQuery):
    uid = call.from_user.id
    username = call.from_user.username or "без ника"
    tarif = user_states[uid]["tarif"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text = (
        "💸 <b>Новый платёж:</b>\n\n"
        f"👤 Пользователь: @{username}\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"📦 Тариф: {tarif}\n"
        f"⏰ Время: {now}"
    )

    confirm_kb = InlineKeyboardMarkup()
    confirm_kb.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{uid}"))
    await bot.send_message(chat_id=ADMIN_GROUP_ID, text=text, reply_markup=confirm_kb)
    await call.message.edit_text("✅ Ожидаем подтверждение администратора...")

# ——— Подтверждение платежа ———
@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"))
async def confirm_user(call: types.CallbackQuery):
    uid = int(call.data.split("_")[1])
    if uid in issued_configs:
        await call.answer("Уже подтверждено.")
        return

    global last_ip
    ip = f"10.0.0.{last_ip}"
    last_ip += 1
    private_key = secrets.token_urlsafe(32)

    config = (
        f"[Interface]\nPrivateKey = {private_key}\nAddress = {ip}/24\nDNS = 1.1.1.1\n\n"
        f"[Peer]\nPublicKey = {SERVER_PUBLIC_KEY}\nEndpoint = {SERVER_IP}:{SERVER_PORT}\n"
        "AllowedIPs = 0.0.0.0/0, ::/0\nPersistentKeepalive = 25"
    )
    await bot.send_message(uid, f"🎉 Подписка активирована!\nВот ваша конфигурация WireGuard:\n\n<pre>{config}</pre>")
    issued_configs[uid] = True

    # Рефералка
    ref_info = user_refs.get(uid, {})
    inviter = ref_info.get("referred_by")
    if inviter:
        bonus_end = datetime.now() + timedelta(days=7)
        user_subscriptions[inviter] = bonus_end
        await bot.send_message(inviter, "🎁 Вам начислены +7 бонусных дней за приглашение!")

    # Подписка
    months = user_states[uid]["months"]
    sub_end = datetime.now() + timedelta(days=30 * months)
    user_subscriptions[uid] = sub_end

# ——— Рефералка ———
@dp.message_handler(lambda m: m.text == "🎁 Реферальная система")
async def show_ref(msg: types.Message):
    uid = msg.from_user.id
    link = f"https://t.me/FastVpn_bot_bot?start={uid}"
    await msg.answer(
        f"🎯 Приглашайте друзей и получайте +7 дней за каждого оплатившего!\n\n"
        f"🔗 Ваша реферальная ссылка:\n<code>{link}</code>"
    )

# ——— Напоминания об окончании подписки ———
async def reminder_loop():
    while True:
        now = datetime.now()
        for uid, end_date in list(user_subscriptions.items()):
            if (end_date - now).days == 3:
                await bot.send_message(uid, "⏰ Ваша подписка заканчивается через 3 дня. Пора продлить!")
        await asyncio.sleep(86400)

# ——— Запуск ———
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.create_task(reminder_loop())
    executor.start_polling(dp, skip_updates=True)
