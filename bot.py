import asyncio
import secrets
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'

# Настройки WireGuard
SERVER_PUBLIC_KEY = 'D4na0QwqCtqZatcyavT95NmLITuEaCjsnS9yl0mymUA='
SERVER_IP = '109.196.100.159'
SERVER_PORT = 51820

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

issued_clients = {}
last_assigned_ip = 1

TARIFFS = {
    "1 месяц": 100,
    "3 месяца (+бонусные дни)": 250,
    "5 месяцев (+бонусные дни)": 400,
}

REKVIZITS = "Реквизиты для оплаты:\n\n📱 Телефон: 89322229930\n🏦 Банк: Ozon bank"

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

def main_menu_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for t in TARIFFS:
        kb.insert(InlineKeyboardButton(text=f"{t} — {TARIFFS[t]} ₽", callback_data=f"tariff_{t}"))
    kb.insert(InlineKeyboardButton(text="FAQ 🤔", callback_data="faq"))
    kb.insert(InlineKeyboardButton(text="Реферальная система 🎁", callback_data="referral"))
    return kb

def payment_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(text="Я оплатил, жду подтверждения ✅", callback_data="paid"))
    return kb

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Я бот FastVpnBot — выдаю конфигурации WireGuard VPN после оплаты.\n"
        "Выбери тариф для подключения:",
        reply_markup=main_menu_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('tariff_'))
async def process_tariff_selection(callback_query: types.CallbackQuery):
    tariff_name = callback_query.data[7:]
    price = TARIFFS.get(tariff_name)
    if not price:
        await callback_query.answer("Неизвестный тариф.")
        return
    text = f"Вы выбрали тариф: *{tariff_name}*\nЦена: *{price} ₽*\n\n"
    text += REKVIZITS
    text += "\n\nПосле оплаты нажмите кнопку ниже, чтобы сообщить мне, что оплатили."
    await bot.send_message(callback_query.from_user.id, text, parse_mode='Markdown', reply_markup=payment_keyboard())
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'faq')
async def process_faq(callback_query: types.CallbackQuery):
    faq_text = (
        "❓ *FAQ* ❓\n\n"
        "➡️ *Реферальная система:*\n"
        "Приглашайте друзей по вашей ссылке и получайте по 7 дней бонуса за каждого, кто оплатит подписку!\n\n"
        "➡️ *Как оплатить:*\n"
        "Переведите деньги на реквизиты, которые я выдал после выбора тарифа.\n\n"
        "➡️ *Подтверждение оплаты:*\n"
        "После оплаты сообщите мне, нажав кнопку \"Я оплатил\" в меню тарифа.\n\n"
        "Администратор проверит оплату и подтвердит вашу подписку, после чего вы получите VPN конфигурацию."
    )
    await bot.send_message(callback_query.from_user.id, faq_text, parse_mode='Markdown')
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'referral')
async def process_referral(callback_query: types.CallbackQuery):
    referral_text = (
        "🎁 *Реферальная система*\n\n"
        "За каждого приглашённого вами человека, который оплатит подписку, вы получите +7 дней бесплатного использования VPN!\n\n"
        "Поделитесь своей реферальной ссылкой с друзьями и зарабатывайте бонусы.\n\n"
        "Реферальная ссылка будет доступна скоро (или можно добавить сейчас, если есть реализация)."
    )
    await bot.send_message(callback_query.from_user.id, referral_text, parse_mode='Markdown')
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'paid')
async def process_paid(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id,
                           "Спасибо за оплату! Ожидайте подтверждения от администратора.")
    await callback_query.answer()

@dp.message_handler(commands=['confirm'])
async def admin_confirm_payment(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /confirm <user_id>")
        return
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("Ошибка: user_id должен быть числом.")
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
        await bot.send_message(user_id, "🎉 Ваша подписка активирована! Вот ваша конфигурация WireGuard:\n\n" + wg_config)
        await message.answer(f"Конфигурация выдана пользователю {user_id}.")
    except Exception as e:
        await message.answer(f"Ошибка при отправке конфигурации пользователю {user_id}: {e}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
