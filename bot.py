import logging
import random
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)

# Токен бота (лучше ставить в переменную окружения, но для примера так)
BOT_TOKEN = "8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8"
if not BOT_TOKEN:
    print("Error: BOT_TOKEN is not set!")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

ADMIN_CHAT_ID = -1002593269045  # твоя админ-группа
ADMIN_USER_ID = 7231676236      # твой личный ID для подтверждения

REF_BONUS_DAYS = 7
BONUS_3MONTH_DAYS = 15
roulette_days = [3, 5, 7, 10]

# Для примера конфиги можно заменить ссылками или строками
CONFIGS = {
    'default': 'https://example.com/configs/default.ovpn',
    'fastvpn': 'https://example.com/configs/fastvpn.ovpn',
    'securevpn': 'https://example.com/configs/securevpn.ovpn',
}

# Хранение данных пользователей (лучше хранить в БД)
users = {}
payments_pending = {}

FAQ_TEXT = (
    "❓ <b>Часто задаваемые вопросы</b>\n\n"
    "1️⃣ Как купить подписку?\n➡️ Выберите тариф и оплатите.\n\n"
    "2️⃣ Как сменить конфигурацию VPN?\n➡️ Используйте кнопку 'Сменить конфиг'.\n\n"
    "3️⃣ Как получить бонусные дни?\n➡️ За подписки и рефералов.\n\n"
    "4️⃣ Как связаться с поддержкой?\n➡️ Нажмите кнопку 'Поддержка'.\n"
)

WELCOME_TEXT = (
    "👋 Привет! Я бот FastVPN 🛡️\n"
    "Здесь можно купить подписку на VPN с бонусами и реферальной системой.\n\n"
    "Выбери тариф и начни пользоваться уже сегодня!"
)

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("1 месяц - 100₽", callback_data="buy_1m"),
        InlineKeyboardButton("3 месяца - 250₽ + бонус", callback_data="buy_3m"),
        InlineKeyboardButton("5 месяцев - 400₽ + бонус", callback_data="buy_5m"),
    )
    kb.add(
        InlineKeyboardButton("🎰 Рулетка бонусов", callback_data="roulette"),
        InlineKeyboardButton("⚙️ Сменить конфиг", callback_data="change_config"),
    )
    kb.add(
        InlineKeyboardButton("❓ FAQ", callback_data="faq"),
        InlineKeyboardButton("📞 Поддержка", callback_data="support"),
    )
    return kb

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {
            "subscription_until": None,
            "config": "default",
            "referrals": 0,
            "roulette_used": False,  # Отметка, что рулетка использована
        }
    await message.answer(WELCOME_TEXT, reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id

    if user_id not in users:
        users[user_id] = {
            "subscription_until": None,
            "config": "default",
            "referrals": 0,
            "roulette_used": False,
        }

    if data.startswith("buy_"):
        months = int(data.split("_")[1][0])  # 'buy_1m' -> 1, 'buy_3m' -> 3, 'buy_5m' -> 5
        price_map = {1: 100, 3: 250, 5: 400}
        price = price_map.get(months)
        if not price:
            await callback_query.answer("Ошибка тарифа")
            return

        pay_text = (
            f"💳 Вы выбрали подписку на {months} месяц(ев) за {price}₽.\n"
            "Оплатите на номер карты Ozon Банка:\n"
            "+7 932 222-99-30\n\n"
            "После оплаты нажмите кнопку ниже, чтобы подтвердить."
        )
        payments_pending[user_id] = {
            "months": months,
            "price": price,
            "timestamp": datetime.now(),
        }
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid_confirm"))
        await callback_query.message.answer(pay_text, reply_markup=kb)
        await callback_query.answer()

    elif data == "paid_confirm":
        if user_id not in payments_pending:
            await callback_query.answer("Нет ожидающей оплаты.", show_alert=True)
            return

        pay_info = payments_pending[user_id]

        confirm_text = (
            f"🛎 Пользователь @{callback_query.from_user.username or user_id} "
            f"запросил активацию подписки:\n"
            f"• {pay_info['months']} мес. за {pay_info['price']}₽\n"
            f"• Время: {pay_info['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "Нажмите кнопку для подтверждения активации."
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_confirm_{user_id}"))
        await bot.send_message(ADMIN_CHAT_ID, confirm_text, reply_markup=kb)

        await callback_query.answer("Запрос отправлен на подтверждение администратору.", show_alert=True)

    elif data.startswith("admin_confirm_"):
        admin_user_id = callback_query.from_user.id
        if admin_user_id != ADMIN_CHAT_ID and admin_user_id != ADMIN_USER_ID:
            await callback_query.answer("У вас нет прав на подтверждение.", show_alert=True)
            return
        uid = int(data.split("_")[-1])
        if uid not in payments_pending:
            await callback_query.answer("Оплата не найдена или уже подтверждена.", show_alert=True)
            return
        pay_info = payments_pending.pop(uid)

        now = datetime.now()
        current_until = users.get(uid, {}).get("subscription_until")
        if current_until and current_until > now:
            new_until = current_until + timedelta(days=30*pay_info["months"])
        else:
            new_until = now + timedelta(days=30*pay_info["months"])

        bonus_days = 0
        if pay_info["months"] == 3:
            bonus_days += BONUS_3MONTH_DAYS
        bonus_days += REF_BONUS_DAYS * users.get(uid, {}).get("referrals", 0)
        new_until += timedelta(days=bonus_days)

        users.setdefault(uid, {})["subscription_until"] = new_until
        users[uid]["roulette_used"] = False  # при новой подписке рулетка снова доступна

        # Формируем уникальную VPN ссылку для пользователя
        vpn_link = f"https://example.com/vpnconfig/{uid}.ovpn"

        try:
            await bot.send_message(
                uid,
                f"✅ Ваша подписка активирована до {new_until.strftime('%Y-%m-%d %H:%M:%S')}!\n"
                f"🎁 Включая бонусы {bonus_days} дней!\n\n"
                f"🔗 Ваша персональная VPN ссылка для Outline VPN:\n{vpn_link}\n\n"
                "Скопируйте ссылку и вставьте в приложение Outline для подключения."
            )
        except Exception:
            pass

        await callback_query.answer("Подписка подтверждена и активирована.")

    elif data == "roulette":
        user = users.get(user_id)
        if not user or not user.get("subscription_until") or user["subscription_until"] < datetime.now():
            await callback_query.answer("У вас нет активной подписки.", show_alert=True)
            return
        if user.get("roulette_used", False):
            await callback_query.answer("Вы уже использовали рулетку бонусов.", show_alert=True)
            return

        reward_days = random.choice(roulette_days)
        user["subscription_until"] += timedelta(days=reward_days)
        user["roulette_used"] = True
        await callback_query.answer(f"🎉 Поздравляем! Вам добавлено {reward_days} бонусных дней!", show_alert=True)

    elif data == "change_config":
        user = users.get(user_id)
        current_config = user.get("config", "default")
        configs_kb = InlineKeyboardMarkup(row_width=1)
        for c in CONFIGS.keys():
            mark = "✅" if c == current_config else ""
            configs_kb.insert(InlineKeyboardButton(f"{c} {mark}", callback_data=f"set_config_{c}"))
        await callback_query.message.answer("Выберите новую конфигурацию:", reply_markup=configs_kb)
        await callback_query.answer()

    elif data.startswith("set_config_"):
        config_name = data.split("_")[-1]
        if config_name not in CONFIGS:
            await callback_query.answer("Конфигурация не найдена.")
            return
        users[user_id]["config"] = config_name
        await callback_query.answer(f"Конфигурация изменена на {config_name}.")
        await callback_query.message.answer(f"Теперь ваш конфиг: {config_name}\nСсылка: {CONFIGS[config_name]}")

    elif data == "faq":
        await callback_query.message.answer(FAQ_TEXT, parse_mode="HTML")
        await callback_query.answer()

    elif data == "support":
        await callback_query.message.answer("📞 Свяжитесь с нашей поддержкой: @YourSupportUsername")
        await callback_query.answer()

    else:
        await callback_query.answer("Неизвестная команда.")

if __name__ == "__main__":
    print("Bot started")
    asyncio.run(dp.start_polling())
