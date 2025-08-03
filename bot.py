import logging
import random
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import urllib3

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

ADMIN_CHAT_ID = -1002593269045
ADMIN_USER_ID = 7231676236

users = {}  # user_id -> {"subscription_until": datetime, "roulette_used": bool}
payments_pending = {}  # user_id -> {"months": int, "price": int, "timestamp": datetime}

roulette_days = [3, 5, 7, 10]

# ✅ Актуальные данные из Outline API
OUTLINE_API_URL = "https://109.196.100.159:55633/bkz9X4_oG7jiaYtDNinlBQ"

# Отключаем предупреждения о самоподписанном сертификате
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("1 месяц - 100₽", callback_data="buy_1m"),
        InlineKeyboardButton("3 месяца - 250₽ + бонус", callback_data="buy_3m"),
        InlineKeyboardButton("5 месяцев - 400₽ + бонус", callback_data="buy_5m"),
    )
    kb.add(
        InlineKeyboardButton("🎰 Рулетка бонусов", callback_data="roulette"),
    )
    return kb

def create_outline_user():
    try:
        # Токен — это часть URL после последнего слеша
        token = OUTLINE_API_URL.split('/')[-1]
        api_base_url = OUTLINE_API_URL.rsplit('/', 1)[0]

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        url = f"{api_base_url}/access-keys"
        response = requests.post(url, headers=headers, verify=False)
        if response.status_code == 200:
            data = response.json()
            return data["accessUrl"]  # Уникальная ссылка Outline
        else:
            print(f"Ошибка Outline API: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Ошибка при создании Outline ключа: {e}")
        return None

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {"subscription_until": None, "roulette_used": False}
    await message.answer("Привет! Выбери тариф:", reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if user_id not in users:
        users[user_id] = {"subscription_until": None, "roulette_used": False}

    if data.startswith("buy_"):
        months = int(data.split("_")[1][0])
        price_map = {1: 100, 3: 250, 5: 400}
        price = price_map.get(months)
        payments_pending[user_id] = {"months": months, "price": price, "timestamp": datetime.now()}
        await callback_query.message.answer(
            f"Вы выбрали подписку на {months} месяц(ев) за {price}₽.\n"
            "Оплатите на карту Ozon Банка: +7 932 222-99-30\n\n"
            "После оплаты нажмите кнопку ниже, чтобы подтвердить.",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Я оплатил(а)", callback_data="paid_confirm"))
        )
        await callback_query.answer()

    elif data == "paid_confirm":
        if user_id not in payments_pending:
            await callback_query.answer("Нет ожидающей оплаты.", show_alert=True)
            return
        pay_info = payments_pending[user_id]
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"Пользователь @{callback_query.from_user.username or user_id} запросил активацию подписки:\n"
            f"• {pay_info['months']} мес. за {pay_info['price']}₽\n"
            f"• Время: {pay_info['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "Нажмите кнопку ниже для подтверждения активации.",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_confirm_{user_id}")
            )
        )
        await callback_query.answer("Запрос отправлен администратору.", show_alert=True)

    elif data.startswith("admin_confirm_"):
        admin_id = callback_query.from_user.id
        if admin_id != ADMIN_USER_ID:
            await callback_query.answer("Нет прав на подтверждение.", show_alert=True)
            return

        uid = int(data.split("_")[-1])
        if uid not in payments_pending:
            await callback_query.answer("Оплата не найдена или уже подтверждена.", show_alert=True)
            return

        pay_info = payments_pending.pop(uid)
        now = datetime.now()
        current_until = users.get(uid, {}).get("subscription_until")
        if current_until and current_until > now:
            new_until = current_until + timedelta(days=30 * pay_info["months"])
        else:
            new_until = now + timedelta(days=30 * pay_info["months"])

        # Бонусные дни
        bonus_days = 0
        if pay_info["months"] == 3:
            bonus_days = 15
        elif pay_info["months"] == 5:
            bonus_days = 30
        new_until += timedelta(days=bonus_days)

        users[uid]["subscription_until"] = new_until
        users[uid]["roulette_used"] = False

        outline_link = create_outline_user()

        if outline_link:
            await bot.send_message(
                uid,
                f"✅ Ваша подписка активирована до {new_until.strftime('%Y-%m-%d %H:%M:%S')}!\n"
                f"🎁 Бонусные дни: {bonus_days}\n\n"
                f"🔗 Ваша персональная VPN-ссылка для Outline:\n{outline_link}\n\n"
                "Скопируйте её в приложение Outline и подключайтесь."
            )
        else:
            await bot.send_message(
                uid,
                "✅ Подписка активирована, но не удалось выдать ссылку Outline.\n"
                "Обратитесь в поддержку."
            )

        await callback_query.answer("Подписка активирована.")

    elif data == "roulette":
        user = users.get(user_id)
        now = datetime.now()
        if not user["subscription_until"] or user["subscription_until"] < now:
            await callback_query.answer("У вас нет активной подписки.", show_alert=True)
            return
        if user["roulette_used"]:
            await callback_query.answer("Рулетку можно использовать только один раз на подписку.", show_alert=True)
            return

        reward_days = random.choice(roulette_days)
        user["subscription_until"] += timedelta(days=reward_days)
        user["roulette_used"] = True

        await callback_query.answer(f"🎉 Вам добавлено {reward_days} бонусных дней!", show_alert=True)

    else:
        await callback_query.answer("Неизвестная команда.")

if __name__ == "__main__":
    print("Bot started")
    asyncio.run(dp.start_polling())
