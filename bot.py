import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# --- Твои данные ---
BOT_TOKEN = "8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8"
ADMIN_CHAT_ID = -1002593269045  # Твоя админ-группа

OUTLINE_API_URL = "https://109.196.100.159:7235/gip-npAdi0GP2xswd_f9Nw"
OUTLINE_CERT_SHA256 = "2065D8741DB5F2DD3E9A4C6764F55ECAD1B76FBADC33E1FAF7AD1A21AC163131"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Временная база (для продакшена подключай БД)
users = {}        # user_id -> dict с данными пользователя
payments = {}     # user_id -> статус платежа ("pending", "confirmed")

# --- Вспомогательная функция для создания ключа Outline VPN через API ---
async def create_outline_key(name: str):
    """
    Создаёт ключ Outline VPN для пользователя.
    Возвращает словарь с ключом и ссылкой.
    """
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            # В реальном окружении добавь авторизацию, если нужно
        }
        # Создаем ключ (парсим JSON как в официальном API Outline)
        url = f"{OUTLINE_API_URL}/access-keys"
        payload = {
            "name": name
        }

        # Обход ошибки сертификата TLS - для простоты, можно отключить verify SSL,
        # но это снижает безопасность — лучше импортировать сертификат Outline
        async with session.post(url, json=payload, ssl=False) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data
            else:
                text = await resp.text()
                raise Exception(f"Ошибка Outline API: {resp.status} {text}")

# --- Клавиатуры ---
def main_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Тарифы", callback_data="show_tariffs"),
        InlineKeyboardButton("🤝 Реферальная система", callback_data="show_referral"),
    )
    kb.add(InlineKeyboardButton("⚙️ Активировать бота", callback_data="activate_bot"))
    return kb

# --- Обработчики команд ---
@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"paid": False, "key_id": None, "access_url": None, "referrals": []}

    await message.answer(
        f"👋 Привет, <b>{message.from_user.full_name}</b>!\n\n"
        "Я — бот FastVPN.\n"
        "⚡️ Быстро выдаю рабочие VPN ключи через Outline.\n"
        "🔐 Защищай свои данные и получай доступ без ограничений!\n\n"
        "Выбери действие ниже ⬇️",
        reply_markup=main_kb(),
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data == "show_tariffs")
async def show_tariffs(callback_query: types.CallbackQuery):
    text = (
        "💎 Тарифы FastVPN:\n\n"
        "🆓 Бесплатно — 7 дней пробного доступа\n"
        "💳 Подписка — 99₽/месяц\n\n"
        "Чтобы оплатить, напиши команду /pay"
    )
    await callback_query.answer()
    await callback_query.message.edit_text(text)

@dp.callback_query_handler(lambda c: c.data == "show_referral")
async def show_referral(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user = users.get(user_id, {})
    ref_link = f"https://t.me/FastVpn_bot_bot?start={user_id}"
    refs = user.get("referrals", [])
    text = (
        f"🤝 Ваша реферальная ссылка:\n"
        f"<code>{ref_link}</code>\n\n"
        f"Количество приглашённых: {len(refs)}"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu"),
    )
    await callback_query.answer()
    await callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback_query: types.CallbackQuery):
    await start_handler(callback_query.message)

@dp.callback_query_handler(lambda c: c.data == "activate_bot")
async def activate_bot(callback_query: types.CallbackQuery):
    text = (
        "⚙️ Как активировать FastVPN:\n\n"
        "1️⃣ Зарегистрируйтесь в Telegram Business.\n"
        "2️⃣ Перейдите в Настройки → Telegram для бизнеса → Чат-боты.\n"
        "3️⃣ Добавьте нашего бота @FastVpn_bot_bot туда.\n"
        "4️⃣ После оплаты и подтверждения — получите VPN ключ.\n\n"
        "Наслаждайтесь безопасным интернетом! 🚀"
    )
    await callback_query.answer()
    await callback_query.message.edit_text(text)

@dp.message_handler(commands=["pay"])
async def pay_handler(message: types.Message):
    user_id = message.from_user.id
    payments[user_id] = "pending"

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"confirm_pay_{user_id}")
    )
    await bot.send_message(ADMIN_CHAT_ID,
                           f"Пользователь <a href='tg://user?id={user_id}'>{user_id}</a> хочет оплатить подписку.",
                           parse_mode="HTML", reply_markup=kb)
    await message.answer("Спасибо! Ожидайте подтверждения оплаты администратором.", reply_markup=None)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("confirm_pay_"))
async def confirm_pay(callback_query: types.CallbackQuery):
    admin_id = callback_query.from_user.id
    if admin_id != ADMIN_CHAT_ID:
        await callback_query.answer("У вас нет прав подтверждать оплату.", show_alert=True)
        return
    user_id = int(callback_query.data.split("_")[-1])
    if payments.get(user_id) != "pending":
        await callback_query.answer("Платеж уже подтвержден или не найден.", show_alert=True)
        return

    # Обновляем статус оплаты
    payments[user_id] = "confirmed"
    users[user_id]["paid"] = True

    # Создаем ключ Outline
    try:
        key_data = await create_outline_key(f"User-{user_id}")
    except Exception as e:
        await callback_query.message.answer(f"Ошибка создания ключа: {e}")
        return

    users[user_id]["key_id"] = key_data["id"]
    users[user_id]["access_url"] = key_data["accessUrl"]

    await callback_query.answer("Оплата подтверждена и ключ создан!", show_alert=True)
    await callback_query.message.edit_reply_markup(reply_markup=None)

    # Отправляем пользователю
    kb_user = InlineKeyboardMarkup(row_width=2)
    kb_user.add(
       
