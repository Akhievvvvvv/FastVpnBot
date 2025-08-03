import asyncio
import secrets
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'

# WireGuard серверные данные
SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Для хранения выданных конфигураций (память в рамках сессии)
issued_clients = {}
last_assigned_ip = 1

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

# Клавиатура с кнопками снизу
main_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("💰 Выбрать тариф")
main_kb.add("✅ Я оплатил(а)")
main_kb.add("🔗 Реферальная система")
main_kb.add("ℹ️ FAQ")

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(
        "👋 Привет! Это простой VPN для безопасного интернета! 🌐🔒\n\n"
        "Выбирай тариф, оплачивай, а я помогу с настройкой VPN. 🚀",
        reply_markup=main_kb
    )

@dp.message_handler(lambda message: message.text == "💰 Выбрать тариф")
async def choose_tariff(message: types.Message):
    text = (
        "Доступные тарифы:\n"
        "1️⃣ 1 месяц — 100₽\n"
        "2️⃣ 3 месяца — 250₽ (+бонусные дни)\n"
        "3️⃣ 5 месяцев — 400₽ (+бонусные дни)\n\n"
        "Оплати удобным способом и нажми «✅ Я оплатил(а)»"
    )
    await message.answer(text)

@dp.message_handler(lambda message: message.text == "✅ Я оплатил(а)")
async def payment_confirm(message: types.Message):
    user_id = message.from_user.id
    # Здесь должна быть логика подтверждения админом (тут просто эхо)
    # Отправляем админу в группу о подтверждении оплаты
    ADMIN_CHAT_ID = -1002593269045  # Вставь сюда ID своей группы или админа
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"Пользователь @{message.from_user.username} (id: {user_id}) сообщил об оплате.\n"
        "Подтверди оплату командой:\n"
        f"/confirm {user_id}"
    )
    await message.answer("Спасибо! Ожидай подтверждения от администратора.")

@dp.message_handler(lambda message: message.text == "🔗 Реферальная система")
async def referral_info(message: types.Message):
    await message.answer(
        "Приглашай друзей и получай бонусы! 👫\n"
        "За каждого приглашенного, который оплатит подписку, ты получаешь +7 дней бесплатно! 🎉"
    )

@dp.message_handler(lambda message: message.text == "ℹ️ FAQ")
async def faq(message: types.Message):
    await message.answer(
        "❓ Вопросы и ответы:\n"
        "1. Как оплатить?\n"
        "2. Как настроить VPN?\n"
        "3. Что делать, если VPN не работает?\n"
        "Если остались вопросы — пиши поддержку!"
    )

# Команда для админа: подтверждаем оплату и выдаем конфиг
@dp.message_handler(commands=['confirm'])
async def admin_confirm_payment(message: types.Message):
    # Формат: /confirm <user_id>
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /confirm <user_id>")
        return

    user_id = int(args[1])
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
        await bot.send_message(user_id, "🎉 Ваша подписка активирована!\n\n" 
                               "Вот ваша конфигурация WireGuard VPN, просто скопируйте и вставьте в приложение:\n\n" + wg_config)
        await message.answer(f"Конфигурация выдана пользователю {user_id}.")
    except Exception as e:
        await message.answer(f"Ошибка при отправке конфигурации пользователю {user_id}: {e}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
