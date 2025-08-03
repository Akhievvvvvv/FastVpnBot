import asyncio
import secrets
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'
ADMIN_GROUP_ID = -1002593269045
BOT_USERNAME = 'FastVpn_bot'

SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

issued_clients = {}
subscriptions = {}
last_assigned_ip = 1

TARIFFS = {
    "7 дней — 99₽": 7,
    "30 дней — 299₽": 30,
    "90 дней — 699₽": 90,
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
    ref = message.get_args()
    user_id = message.from_user.id
    if ref and ref.isdigit() and int(ref) != user_id:
        if user_id not in issued_clients:
            issued_clients[user_id] = {"referred_by": int(ref)}

    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📶 Выбрать тариф", callback_data="choose_tariff"),
        InlineKeyboardButton("🎁 Реферальная система", callback_data="referral_info")
    )
    await message.answer(
        "👋 Привет! Это простой VPN для безопасного интернета! 🌐🔒\n\n"
        "Выбирай тариф, оплачивай, а я помогу с настройкой VPN. 🚀",
        reply_markup=markup
    )

@dp.callback_query_handler(lambda c: c.data == 'choose_tariff')
async def show_tariffs(callback: types.CallbackQuery):
    markup = InlineKeyboardMarkup()
    for name in TARIFFS:
        markup.add(InlineKeyboardButton(name, callback_data=f"pay_{name}"))
    await callback.message.edit_text("Выберите тариф:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("pay_"))
async def pay_tariff(callback: types.CallbackQuery):
    tariff = callback.data[4:]
    days = TARIFFS.get(tariff)
    user_id = callback.from_user.id
    text = (
        f"💳 Вы выбрали тариф: *{tariff}*\n\n"
        "Переведите указанную сумму и нажмите «Оплатил(а)».\n"
        "Оплата (например, на карту): `1234 5678 9012 3456`\n\n"
        "После подтверждения админом вы получите VPN-доступ."
    )
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Оплатил(а)", callback_data=f"confirm_request_{days}")
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_request_"))
async def confirm_request(callback: types.CallbackQuery):
    days = int(callback.data.split("_")[2])
    user = callback.from_user
    await bot.send_message(
        ADMIN_GROUP_ID,
        f"💰 Новый запрос на оплату!\n"
        f"👤 Пользователь: {user.first_name} (@{user.username or 'нет'})\n"
        f"🆔 ID: `{user.id}`\n"
        f"📅 Тариф: {days} дней\n"
        f"⏰ Время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"⚙️ Подтвердите через команду: /confirm {user.id} {days}",
        parse_mode="Markdown"
    )
    await callback.message.edit_text("⏳ Заявка отправлена администратору. Ждите подтверждения!")

@dp.message_handler(commands=['confirm'])
async def admin_confirm(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3:
        await message.reply("Формат: /confirm <user_id> <дней>")
        return
    user_id = int(parts[1])
    days = int(parts[2])

    if user_id in subscriptions:
        await message.reply("Пользователь уже имеет подписку.")
        return

    private_key = generate_private_key()
    client_ip = generate_client_ip()
    config = generate_wg_config(private_key, client_ip)

    issued_clients[user_id] = {"private_key": private_key, "ip": client_ip}
    subscriptions[user_id] = {
        "expires": datetime.datetime.now() + datetime.timedelta(days=days)
    }

    referrer = issued_clients.get(user_id, {}).get("referred_by")
    if referrer:
        subscriptions.setdefault(referrer, {"expires": datetime.datetime.now()})
        subscriptions[referrer]["expires"] += datetime.timedelta(days=7)
        await bot.send_message(referrer, "🎉 Ура! За приглашённого пользователя вы получили +7 дней VPN!")

    try:
        await bot.send_message(
            user_id,
            f"✅ Подписка активирована! Вот ваша конфигурация WireGuard:\n\n```ini\n{config}```",
            parse_mode="Markdown"
        )
        await message.reply("Пользователь получил конфигурацию.")
    except Exception as e:
        await message.reply(f"Ошибка отправки пользователю: {e}")

@dp.callback_query_handler(lambda c: c.data == 'referral_info')
async def referral_info(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    await callback.message.answer(
        f"👥 Реферальная программа:\n\n"
        f"Приглашайте друзей! За каждого оплатившего подписку — вы получаете *7 дней* VPN бесплатно. 🎁\n\n"
        f"Ваша ссылка: {link}",
        parse_mode="Markdown"
    )

async def notify_expirations():
    while True:
        now = datetime.datetime.now()
        for user_id, sub in list(subscriptions.items()):
            if (sub["expires"] - now).days == 1:
                try:
                    await bot.send_message(user_id, "📢 Напоминание: ваша подписка истекает через 1 день.")
                except:
                    pass
            elif now >= sub["expires"]:
                try:
                    await bot.send_message(user_id, "⛔️ Ваша подписка истекла. Пожалуйста, продлите её.")
                    del subscriptions[user_id]
                except:
                    pass
        await asyncio.sleep(3600)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(notify_expirations())
    executor.start_polling(dp, skip_updates=True)
