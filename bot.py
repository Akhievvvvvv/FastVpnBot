import asyncio
import secrets
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'
ADMIN_CHAT_ID = -1002593269045  # Вставьте свой админский чат ID

# WireGuard серверные данные
SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

issued_clients = {}
last_assigned_ip = 1
user_tariffs = {}  # user_id -> выбранный тариф

TARIFFS = {
    "1 месяц — 100₽": 30,
    "3 месяца — 250₽ (+бонусные дни)": 30*3,  # Бонусные дни можно реализовать отдельно
    "5 месяцев — 400₽ (+бонусные дни)": 30*5,
}

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

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Тарифы 💰", "Реферальная система 🎁", "Оплатил(а) ✅")
    await message.answer(
        "👋 Привет! Это простой VPN для безопасного интернета! 🌐🔒\n\n"
        "Выбирай тариф, оплачивай, а я помогу с настройкой VPN. 🚀",
        reply_markup=keyboard
    )

@dp.message_handler(lambda m: m.text == "Тарифы 💰")
async def show_tariffs(message: types.Message):
    keyboard = types.InlineKeyboardMarkup()
    for name in TARIFFS.keys():
        keyboard.add(types.InlineKeyboardButton(text=name, callback_data=f"tariff_{name}"))
    await message.answer("Выбери тариф для покупки:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tariff_'))
async def process_tariff_selection(callback_query: types.CallbackQuery):
    tariff_name = callback_query.data[len("tariff_"):]
    user_tariffs[callback_query.from_user.id] = tariff_name
    await bot.answer_callback_query(callback_query.id, text=f"Выбран тариф: {tariff_name}")
    await bot.send_message(callback_query.from_user.id,
                           f"Вы выбрали тариф: {tariff_name}\n\n"
                           f"После оплаты нажмите кнопку «Оплатил(а) ✅», чтобы сообщить нам.")

@dp.message_handler(lambda m: m.text == "Реферальная система 🎁")
async def referral_info(message: types.Message):
    user_id = message.from_user.id
    # Для примера сделаем просто текст с инфой и ссылкой
    referral_link = f"https://t.me/YourBotUsername?start={user_id}"  # замените YourBotUsername
    await message.answer(
        f"🎉 Приглашай друзей и получай бонусы! 🎁\n\n"
        f"За каждого приглашенного, который оплатит подписку, ты получаешь +7 дней бесплатно! ⏳\n\n"
        f"Твоя реферальная ссылка:\n{referral_link}"
    )

@dp.message_handler(lambda m: m.text == "Оплатил(а) ✅")
async def payment_confirm(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Не указан"
    user_fullname = message.from_user.full_name
    selected_tariff = user_tariffs.get(user_id, "Тариф не выбран")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    admin_msg = (
        f"💳 Подтверждение оплаты:\n"
        f"👤 {user_fullname} (@{username})\n"
        f"🆔 ID: {user_id}\n"
        f"⏰ Время: {now_str}\n"
        f"💼 Тариф: {selected_tariff}\n\n"
        f"Используйте команду /confirm {user_id} для выдачи доступа."
    )

    await bot.send_message(ADMIN_CHAT_ID, admin_msg)
    await message.answer("Спасибо! Оплата подтверждена, жди одобрения администратора. 🔥")

@dp.message_handler(commands=['confirm'])
async def admin_confirm_payment(message: types.Message):
    # Ожидается: /confirm <user_id>
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /confirm <user_id>")
        return

    try:
        user_id = int(args[1])
    except:
        await message.answer("Неверный ID пользователя.")
        return

    if user_id in issued_clients:
        await message.answer(f"Пользователь {user_id} уже получил конфигурацию.")
        return

    client_private_key = generate_private_key()
    client_ip = generate_client_ip()

    issued_clients[user_id] = {
        "private_key": client_private_key,
        "ip": client_ip,
    }

    wg_config = generate_wg_config(client_private_key, client_ip)

    try:
        await bot.send_message(user_id,
            "Ваша подписка активирована! Вот ваша конфигурация WireGuard VPN:\n\n" + wg_config)
        await message.answer(f"Конфигурация выдана пользователю {user_id}.")
    except Exception as e:
        await message.answer(f"Ошибка при отправке конфигурации пользователю {user_id}: {e}")

if __name__ == '__main__':
    print("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)
