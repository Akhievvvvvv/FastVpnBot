from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from aiogram.utils.callback_data import CallbackData
import asyncio
import logging
import random
import string
from datetime import datetime, timedelta

API_TOKEN = '8484443635:AAGpJkY1qDtfDFmvsh-cbu6CIYqC8cfVTD8'

ADMIN_CHAT_ID = -1002593269045
ADMIN_USER_ID = 7231676236

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# CallbackData для тарифов и подтверждения
buy_cb = CallbackData('buy', 'period')
confirm_cb = CallbackData('confirm', 'user_id')

# Структура данных для хранения пользователей (в реальном проекте лучше БД)
users = {}  
# users = {
#   user_id: {
#     'key': str,
#     'subscription_end': datetime,
#     'referrer': user_id or None,
#     'ref_bonus_days': int,
#     'ref_count': int,
#   }
# }

# Тарифы
TARIFFS = {
    '1m': {'months': 1, 'price': 99},
    '3m': {'months': 3, 'price': 249},
    '5m': {'months': 5, 'price': 399},
}

REKVIZITS = """
💳 Оплата через:
+7 932 222 99 30 (Ozon Bank)

После оплаты нажмите кнопку "Оплатил(а)" для подтверждения.
"""

# Функция генерации уникального ключа VPN (пример)
def generate_vpn_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

# Форматирование приветствия
def welcome_text(user: types.User):
    text = (
        f"👋 Привет, <b>{user.first_name}!</b>\n\n"
        "✨ Я — <b>FastVPN Bot</b> — твой помощник для быстрого и удобного VPN!\n\n"
        "Что ты получаешь:\n"
        "🔒 Безопасный и приватный доступ в интернет\n"
        "⚡ Высокая скорость и стабильность\n"
        "📱 Работает на всех твоих устройствах через Outline\n"
        "🎁 Бонусы за приглашённых друзей\n"
        "💳 Простая оплата и моментальная активация\n\n"
        "Выбери подходящий тариф и начни пользоваться VPN прямо сейчас!\n\n"
    )
    return text

# Клавиатура тарифов
def tariff_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        kb.insert(InlineKeyboardButton(
            f"{t['months']} месяц(ев) — {t['price']}₽", callback_data=buy_cb.new(period=key)
        ))
    return kb

# Клавиатура оплаты
def payment_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.insert(InlineKeyboardButton("💰 Оплатил(а)", callback_data="paid"))
    return kb

# Клавиатура подтверждения оплаты (для админа)
def admin_confirm_keyboard(user_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.insert(InlineKeyboardButton("✅ Подтвердить оплату", callback_data=confirm_cb.new(user_id=user_id)))
    return kb

# Клавиатура для "Посмотреть реквизиты"
def view_rekvizit_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.insert(InlineKeyboardButton("👀 Посмотреть реквизиты", callback_data="view_rekvizit"))
    return kb

# Генерация реферальной ссылки
def referral_link(user_id: int):
    return f"https://t.me/FastVpn_bot_bot?start=ref{user_id}"

# Обработка /start с поддержкой рефералов
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    args = message.get_args()
    referrer_id = None
    if args and args.startswith('ref'):
        try:
            referrer_id = int(args[3:])
        except:
            pass

    user_id = message.from_user.id

    if user_id not in users:
        users[user_id] = {
            'key': None,
            'subscription_end': None,
            'referrer': referrer_id if referrer_id != user_id else None,
            'ref_bonus_days': 0,
            'ref_count': 0,
        }

    text = welcome_text(message.from_user)
    text += "\nВыберите тариф для оплаты:"
    kb = tariff_keyboard()

    # Покажем реферальную ссылку внизу
    text += f"\n\n💡 Ваша реферальная ссылка:\n{referral_link(user_id)}\n" \
            f"Приглашайте друзей и получайте +7 дней бонуса за каждого, кто оплатит тариф!"

    await message.answer(text, reply_markup=kb)

# Обработка выбора тарифа
@dp.callback_query_handler(buy_cb.filter())
async def buy_callback_handler(query: types.CallbackQuery, callback_data: dict):
    period = callback_data['period']
    tariff = TARIFFS.get(period)
    if not tariff:
        await query.answer("Неверный тариф", show_alert=True)
        return

    text = (
        f"Вы выбрали тариф: <b>{tariff['months']} месяц(ев) — {tariff['price']}₽</b>\n\n"
        f"{REKVIZITS}\n"
        "После оплаты нажмите кнопку ниже для уведомления администратора."
    )
    await query.message.edit_text(text, reply_markup=payment_keyboard())

# Обработка нажатия "Оплатил(а)"
@dp.callback_query_handler(text="paid")
async def paid_callback_handler(query: types.CallbackQuery):
    user_id = query.from_user.id
    user = users.get(user_id)
    if not user:
        await query.answer("Пользователь не найден", show_alert=True)
        return

    # Отправляем в админ-группу сообщение для подтверждения
    text = (
        f"💰 Оплата от пользователя:\n"
        f"👤 Username: @{query.from_user.username or 'нет'}\n"
        f"🆔 User ID: {user_id}\n"
        f"Дата/время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Ссылка: [перейти к чату](tg://user?id={user_id})"
    )
    await bot.send_message(ADMIN_CHAT_ID, text, parse_mode='Markdown', reply_markup=admin_confirm_keyboard(user_id))
    await query.answer("Администратор получил уведомление и скоро подтвердит оплату.", show_alert=True)

# Подтверждение оплаты админом
@dp.callback_query_handler(confirm_cb.filter())
async def confirm_payment_handler(query: types.CallbackQuery, callback_data: dict):
    admin_id = query.from_user.id
    if admin_id != ADMIN_USER_ID:
        await query.answer("Нет доступа", show_alert=True)
        return

    user_id = int(callback_data['user_id'])
    user = users.get(user_id)
    if not user:
        await query.answer("Пользователь не найден", show_alert=True)
        return

    # Здесь нужно определить, какой тариф выбирал пользователь.
    # Для простоты примера — поставим 1 месяц, в реальном проекте надо хранить выбор тарифа.
    # Можно сделать, чтобы тариф сохранялся при выборе.

    # Для улучшения — сохраним тариф при выборе
    # Добавим тариф в users[user_id]['selected_tariff']

    # Но сейчас попробуем просто добавить 30 дней (для теста)

    # Для лучшей логики нужно хранить last_selected_tariff:
    last_selected_tariff = user.get('selected_tariff')
    if last_selected_tariff and last_selected_tariff in TARIFFS:
        months = TARIFFS[last_selected_tariff]['months']
    else:
        # Если нет — 1 месяц по умолчанию
        months = 1

    now = datetime.now()
    if user['subscription_end'] and user['subscription_end'] > now:
        user['subscription_end'] += timedelta(days=30*months)
    else:
        user['subscription_end'] = now + timedelta(days=30*months)

    # Генерируем ключ
    key = generate_vpn_key()
    user['key'] = key

    # Если есть реферер — даём бонус
    if user['referrer']:
        ref_user = users.get(user['referrer'])
        if ref_user:
            ref_user['subscription_end'] = (ref_user['subscription_end'] if ref_user['subscription_end'] and ref_user['subscription_end'] > now else now) + timedelta(days=7)
            ref_user['ref_bonus_days'] = ref_user.get('ref_bonus_days', 0) + 7
            ref_user['ref_count'] = ref_user.get('ref_count', 0) + 1

            # Можно уведомить реферера
            await bot.send_message(user['referrer'],
                                   f"🎉 Поздравляем! По вашей реферальной ссылке пользователь оплатил тариф. Вам добавлено +7 дней бонуса!")

    # Отправляем пользователю ключ и инструкцию
    instruction = (
        f"🎉 <b>Оплата подтверждена!</b>\n\n"
        f"🔑 Ваш уникальный ключ VPN:\n<code>{key}</code>\n\n"
        "📌 Как использовать ключ:\n"
        "1️⃣ Скачайте приложение Outline VPN на ваше устройство.\n"
        "2️⃣ Нажмите 'Добавить сервер' и выберите 'Ввести ключ вручную'.\n"
        "3️⃣ Вставьте данный ключ и подключитесь.\n\n"
        f"⏳ Ваша подписка активна до: <b>{user['subscription_end'].strftime('%Y-%m-%d')}</b>\n"
        "Спасибо, что выбрали FastVPN! Если будут вопросы — пишите сюда."
    )
    await bot.send_message(user_id, instruction, parse_mode='HTML')

    await query.answer("Оплата подтверждена, ключ отправлен пользователю.")
    await query.message.edit_reply_markup()  # убираем кнопку у админа

# Сохраняем выбранный тариф при выборе
@dp.callback_query_handler(buy_cb.filter())
async def save_tariff_handler(query: types.CallbackQuery, callback_data: dict):
    user_id = query.from_user.id
    period = callback_data['period']
    if user_id in users:
        users[user_id]['selected_tariff'] = period
    await buy_callback_handler(query, callback_data)

# Обработка кнопки "Посмотреть реквизиты"
@dp.callback_query_handler(text="view_rekvizit")
async def view_rekvizit_handler(query: types.CallbackQuery):
    await query.answer()
    await query.message.answer(REKVIZITS)

# Ежедневная проверка подписок и напоминаний (пример)
async def subscription_checker():
    while True:
        now = datetime.now()
        for user_id, data in users.items():
            if data['subscription_end']:
                days_left = (data['subscription_end'] - now).days
                if days_left in [3, 2, 1]:
                    try:
                        await bot.send_message(user_id, f"⏳ Ваша подписка истекает через {days_left} день(дней). Не забудьте продлить её!")
                    except Exception:
                        pass
                elif days_left < 0:
                    try:
                        await bot.send_message(user_id, "⚠️ Ваша подписка истекла. Чтобы продолжить пользоваться VPN, пожалуйста, оплатите тариф.")
                    except Exception:
                        pass
        await asyncio.sleep(24 * 60 * 60)  # проверять раз в сутки

# Запуск проверок в фоне
async def on_startup(dp):
    asyncio.create_task(subscription_checker())

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, on_startup=on_startup)
