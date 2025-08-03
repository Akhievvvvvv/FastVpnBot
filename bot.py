import asyncio
import secrets
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardRemove
from aiogram.utils import executor

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'
ADMIN_CHAT_ID = -1002593269045  # Твоя админ-группа

# WireGuard server info
SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Тарифы и цены
TARIFFS = {
    "1": {"name": "1 месяц", "price": 99, "duration_days": 30},
    "3": {"name": "3 месяца", "price": 249, "duration_days": 90},
    "5": {"name": "5 месяцев", "price": 449, "duration_days": 150},
}

REKVIZITI = "💳 Реквизиты для оплаты:\n\n📱 89322229930 (Ozon Банк)"

# Базы данных в памяти (можно заменить на БД)
users_data = {}  # user_id: {tariff, start_date, end_date, private_key, client_ip, referral_id}
issued_ips = set()
last_assigned_ip = 1

def generate_private_key():
    return secrets.token_urlsafe(32)

def generate_client_ip():
    global last_assigned_ip
    last_assigned_ip += 1
    ip = f"10.0.0.{last_assigned_ip}"
    while ip in issued_ips:
        last_assigned_ip += 1
        ip = f"10.0.0.{last_assigned_ip}"
    issued_ips.add(ip)
    return ip

def generate_wg_config(private_key: str, client_ip: str) -> str:
    return (
        f"[Interface]\n"
        f"PrivateKey = {private_key}\n"
        f"Address = {client_ip}/24\n"
        f"DNS = 1.1.1.1\n\n"
        f"[Peer]\n"
        f"PublicKey = {SERVER_PUBLIC_KEY}\n"
        f"Endpoint = {SERVER_IP}:{SERVER_PORT}\n"
        f"AllowedIPs = 0.0.0.0/0, ::/0\n"
        f"PersistentKeepalive = 25\n"
    )

def format_referral_link(user_id: int) -> str:
    return f"https://t.me/YourBotUsername?start=ref{user_id}"

def format_subscription_dates(start: datetime, end: datetime) -> str:
    return f"Срок действия: с {start.strftime('%d.%m.%Y')} по {end.strftime('%d.%m.%Y')}"

async def send_tariffs(message: types.Message):
    text = (
        "Выбери тариф и оплати VPN:\n\n"
        "🔹 1 месяц — 99₽\n"
        "🔹 3 месяца — 249₽\n"
        "🔹 5 месяцев — 449₽\n\n"
        f"{REKVIZITI}\n\n"
        "После оплаты нажми кнопку «Оплатил(а)», и администратор проверит платеж.\n"
        "Если всё ок, ты сразу получишь свою уникальную VPN-конфигурацию!"
    )
    buttons = ["1 месяц", "3 месяца", "5 месяцев", "Оплатил(а)", "Реферальная система"]
    await message.answer(text)
    for b in buttons:
        await message.answer(b)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    # Проверяем реферальный параметр
    args = message.get_args()
    referral_id = None
    if args.startswith("ref"):
        try:
            referral_id = int(args[3:])
        except:
            referral_id = None

    # Сохраняем реферала (если есть и не сам себя)
    if referral_id and referral_id != user_id:
        if user_id not in users_data:
            users_data[user_id] = {}
        users_data[user_id]['referral_id'] = referral_id

    await message.answer(
        "👋 Привет! Это простой VPN для безопасного интернета! 🌐🔒\n\n"
        "Выбирай тариф, оплачивай, а я помогу с настройкой VPN. 🚀"
    )
    await send_tariffs(message)

# Обработка текстовых сообщений (выбор тарифа и действия)
@dp.message_handler()
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Выбор тарифа
    if text in ["1 месяц", "3 месяца", "5 месяцев"]:
        # Найти тариф по названию
        selected = None
        for k, v in TARIFFS.items():
            if v['name'] == text:
                selected = k
                break
        if not selected:
            await message.answer("Ошибка выбора тарифа, попробуйте снова.")
            return
        if user_id not in users_data:
            users_data[user_id] = {}
        users_data[user_id]['selected_tariff'] = selected
        await message.answer(
            f"Ты выбрал тариф: {TARIFFS[selected]['name']} за {TARIFFS[selected]['price']}₽.\n\n"
            f"Пожалуйста, оплати на реквизиты:\n{REKVIZITI}\n\n"
            "После оплаты нажми кнопку «Оплатил(а)», чтобы администратор проверил платёж."
        )
        return

    # Пользователь нажал "Оплатил(а)"
    if text == "Оплатил(а)":
        if user_id not in users_data or 'selected_tariff' not in users_data[user_id]:
            await message.answer("Сначала выбери тариф.")
            return
        tariff_id = users_data[user_id]['selected_tariff']
        tariff_name = TARIFFS[tariff_id]['name']
        now = datetime.now()

        # Отправляем в админ-группу уведомление
        admin_text = (
            f"📢 Оплата от пользователя:\n"
            f"👤 ID: {user_id}\n"
            f"🕒 Время: {now.strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"💳 Тариф: {tariff_name}\n\n"
            f"Для подтверждения оплаты введите в чат бота:\n"
            f"/confirm {user_id}"
        )
        await bot.send_message(ADMIN_CHAT_ID, admin_text)
        await message.answer("Спасибо, заявка отправлена на проверку. Жди подтверждения от администратора.")
        return

    # Реферальная система
    if text == "Реферальная система":
        ref_link = format_referral_link(user_id)
        bonus_text = (
            "🎁 Реферальная система:\n\n"
            "Приглашай друзей по своей реферальной ссылке ниже.\n"
            "Если по твоей ссылке кто-то купит VPN — ты получишь +7 дней бесплатно!\n\n"
            f"Твоя ссылка: {ref_link}\n\n"
            "Поделись ей и получай бонусы!"
        )
        await message.answer(bonus_text)
        return

    # Неизвестное сообщение
    await message.answer("Пожалуйста, выбери тариф из меню или нажми «Реферальная система».")

# Команда подтверждения оплаты админом
@dp.message_handler(commands=['confirm'])
async def admin_confirm(message: types.Message):
    # Формат: /confirm <user_id>
    if message.chat.id != ADMIN_CHAT_ID:
        await message.answer("Нет доступа.")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /confirm <user_id>")
        return
    try:
        user_id = int(args[1])
    except:
        await message.answer("Ошибка: неверный user_id.")
        return

    if user_id not in users_data or 'selected_tariff' not in users_data[user_id]:
        await message.answer("Такого пользователя нет или он не выбирал тариф.")
        return

    # Проверяем, не выдана ли уже конфигурация
    if 'vpn_config' in users_data[user_id]:
        await message.answer("Пользователю уже выдана конфигурация.")
        return

    tariff_id = users_data[user_id]['selected_tariff']
    tariff = TARIFFS[tariff_id]
    now = datetime.now()
    start = now
    end = now + timedelta(days=tariff['duration_days'])

    private_key = generate_private_key()
    client_ip = generate_client_ip()
    wg_config = generate_wg_config(private_key, client_ip)

    users_data[user_id].update({
        "start_date": start,
        "end_date": end,
        "private_key": private_key,
        "client_ip": client_ip,
        "vpn_config": wg_config,
        "tariff": tariff,
    })

    # Отправляем пользователю конфиг
    try:
        await bot.send_message(
            user_id,
            f"✅ Оплата подтверждена! Твой VPN настроен.\n\n"
            f"{tariff['name']} — {tariff['price']}₽\n"
            f"{format_subscription_dates(start, end)}\n\n"
            f"Скопируй эту конфигурацию и вставь в приложение WireGuard:\n\n"
            f"{wg_config}"
        )
        await message.answer(f"Конфигурация выдана пользователю {user_id}.")
    except Exception as e:
        await message.answer(f"Ошибка при отправке конфигурации: {e}")

    # Начисляем бонус за реферала, если есть
    referral_id = users_data[user_id].get('referral_id')
    if referral_id and referral_id in users_data:
        # Добавляем +7 дней бонуса к рефералу
        ref_user = users_data[referral_id]
        old_end = ref_user.get('end_date', now)
        if old_end < now:
            old_end = now
        new_end = old_end + timedelta(days=7)
        ref_user['end_date'] = new_end
        try:
            await bot.send_message(referral_id,
                "🎉 Тебе начислено 7 бонусных дней VPN за приглашённого друга! "
                f"Новый срок подписки: {new_end.strftime('%d.%m.%Y')}")
        except:
            pass

# Фоновая задача — напоминание о скором окончании подписки (каждый день)
async def remind_task():
    while True:
        now = datetime.now()
        for user_id, data in users_data.items():
            end = data.get('end_date')
            if not end:
                continue
            days_left = (end - now).days
            if days_left == 3:
                try:
                    await bot.send_message(user_id,
                        f"⚠️ Внимание! До окончания твоей подписки осталось 3 дня ({end.strftime('%d.%m.%Y')}). "
                        "Не забудь продлить VPN!")
                except:
                    pass
        await asyncio.sleep(24*3600)  # Ждем 24 часа

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(remind_task())
    executor.start_polling(dp, skip_updates=True)
