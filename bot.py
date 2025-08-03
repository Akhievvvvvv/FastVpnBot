import asyncio
import secrets
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'

# Настройки сервера WireGuard
SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820
SERVER_WG_INTERFACE = 'wg0'

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Простая база для примера: сохранение выданных IP и ключей
issued_clients = {}
# Для генерации IP-адресов внутри подсети 10.0.0.0/24, начиная с 10.0.0.2
last_assigned_ip = 1

def generate_private_key():
    # Генерируем 32 байта случайных данных и кодируем в base64
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
    await message.answer(
        "Привет! Здесь бот выдаёт WireGuard конфигурации после подтверждения оплаты.\n"
        "Жди подтверждения от администратора после оплаты."
    )

# Команда для админа, чтобы подтвердить оплату и выдать ссылку
@dp.message_handler(commands=['confirm'])
async def admin_confirm_payment(message: types.Message):
    # Ожидается формат: /confirm <user_id>
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /confirm <user_id>")
        return

    user_id = int(args[1])

    # Проверяем, если клиент уже получил конфиг, не выдаём новый
    if user_id in issued_clients:
        await message.answer(f"Пользователь {user_id} уже получил конфигурацию.")
        return

    # Генерируем ключ и IP
    client_private_key = generate_private_key()
    client_ip = generate_client_ip()

    issued_clients[user_id] = {
        "private_key": client_private_key,
        "ip": client_ip,
    }

    wg_config = generate_wg_config(client_private_key, client_ip)

    try:
        await bot.send_message(user_id, "Ваша подписка активирована! Вот ваша конфигурация WireGuard:\n\n" + wg_config)
        await message.answer(f"Конфигурация выдана пользователю {user_id}.")
    except Exception as e:
        await message.answer(f"Ошибка при отправке конфигурации пользователю {user_id}: {e}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
