import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'
ADMIN_CHAT_ID = -1002593269045  # твоя админ-группа

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Сохраняем выбор тарифа пользователя в памяти (для примера, в реале нужно БД)
user_tariffs = {}

# Клавиатура выбора тарифов
tariff_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
tariff_kb.add(
    KeyboardButton("1 месяц — 99₽"),
    KeyboardButton("3 месяца — 249₽"),
    KeyboardButton("5 месяцев — 449₽"),
)
tariff_kb.add(KeyboardButton("Реферальная система"))

# Кнопка после выбора тарифа
paid_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(
    KeyboardButton("Оплатил(а)")
)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    welcome_text = (
        "👋 Привет! Это простой VPN для безопасного интернета! 🌐🔒\n\n"
        "Выбирай тариф, оплачивай, а я помогу с настройкой VPN. 🚀\n\n"
        "Выбери тариф из меню ниже 👇"
    )
    await message.answer(welcome_text, reply_markup=tariff_kb)

@dp.message_handler(lambda msg: msg.text in ["1 месяц — 99₽", "3 месяца — 249₽", "5 месяцев — 449₽"])
async def choose_tariff(message: types.Message):
    tariff = message.text
    user_tariffs[message.from_user.id] = tariff

    payment_info = (
        f"Вы выбрали тариф: {tariff}\n\n"
        "Оплатите по реквизитам:\n"
        "📱 Номер карты (Ozon Банк): 89322229930\n\n"
        "После оплаты нажмите кнопку «Оплатил(а)» для подтверждения."
    )
    await message.answer(payment_info, reply_markup=paid_kb)

@dp.message_handler(lambda msg: msg.text == "Оплатил(а)")
async def paid_confirm(message: types.Message):
    user_id = message.from_user.id
    tariff = user_tariffs.get(user_id)

    if not tariff:
        await message.answer("Пожалуйста, сначала выберите тариф.")
        return

    # Отправляем уведомление в админ-группу
    user_name = message.from_user.username or message.from_user.full_name
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"⚡ Новый платеж:\nПользователь: {user_name} (id: {user_id})\nТариф: {tariff}\nВремя: {now}"
    await bot.send_message(ADMIN_CHAT_ID, text)

    await message.answer("Спасибо за оплату! Ждите подтверждения от администратора.", reply_markup=tariff_kb)

@dp.message_handler(lambda msg: msg.text == "Реферальная система")
async def referral_info(message: types.Message):
    user_id = message.from_user.id
    referral_link = f"https://t.me/YourBotUsername?start={user_id}"

    text = (
        "💡 Реферальная система:\n\n"
        "Приглашай друзей по своей реферальной ссылке и получай +7 дней бесплатного VPN за каждого оплатившего приглашённого!\n\n"
        f"Твоя личная реферальная ссылка:\n{referral_link}"
    )
    await message.answer(text, reply_markup=tariff_kb)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
