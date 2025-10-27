from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters.callback_data import CallbackData
from typing import Dict

STAR_PACKS = [50, 75, 100, 150, 250, 350, 500, 750, 1000, 1500, 2500, 5000, 10000, 25000, 35000, 50000, 100000, 150000, 500000, 1000000]
PACKS_PER_PAGE = 5

PREMIUM_PLANS = [
    {"name": "3 месяца", "price": 799, "duration": 90},
    {"name": "6 месяцев", "price": 1499, "duration": 180},
    {"name": "12 месяцев", "price": 2499, "duration": 365}
]

class SubscribeCallback(CallbackData, prefix="sub"):
    action: str

def get_main_menu_kb(config, user_id: int, support_contact: str, news_channel_link: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="⭐ Купить звёзды", callback_data="buy_stars"), InlineKeyboardButton(text="💎 Купить премиум", callback_data="buy_premium")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"), InlineKeyboardButton(text="🧮 Калькулятор", callback_data="calculator")]
    ]
    bottom_row = []
    if support_contact:
        bottom_row.append(InlineKeyboardButton(text="🆘 Поддержка", url=f"https://t.me/{support_contact.lstrip('@')}"))
    if news_channel_link:
        bottom_row.append(InlineKeyboardButton(text="📢 Новостной канал", url=news_channel_link))
    if bottom_row:
        buttons.append(bottom_row)
    if user_id in config.bot.admin_ids:
        buttons.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="profile_topup_menu"), InlineKeyboardButton(text="🎟️ Промокоды", callback_data="profile_activate_promo")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

def get_payment_methods_keyboard(enabled_systems: Dict[str, bool]) -> InlineKeyboardMarkup:
    buttons = []
    
    all_methods = {
        'lolz': InlineKeyboardButton(text="🔥 Lolz", callback_data="payment_lolz"),
        'cryptobot': InlineKeyboardButton(text="🤖 CryptoBot", callback_data="payment_cryptobot"),
        'xrocet': InlineKeyboardButton(text="🚀 xRocet", callback_data="payment_xrocet"),
        'crystalpay': InlineKeyboardButton(text="💎 CrystalPay", callback_data="payment_crystalpay")
    }

    for method_code, button in all_methods.items():
        if enabled_systems.get(method_code):
            buttons.append([button])
            
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_keyboard(payment_url: str, invoice_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_payment_{invoice_id}")]
    ])

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action")]])

def get_main_menu_only_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]])

def get_crypto_selection_keyboard(available_assets: list = None) -> InlineKeyboardMarkup:
    allowed_assets = ["BNB", "BTC", "ETH", "LTC", "SOL", "TON", "TRX", "USDT"]
    crypto_icons = {"USDT": "🔸", "TON": "💎", "BTC": "🟡", "ETH": "🔷", "SOL": "⚡", "BNB": "🟠", "TRX": "🔴", "LTC": "⚪"}
    buttons = []
    for asset in allowed_assets:
        buttons.append([InlineKeyboardButton(text=f"{crypto_icons.get(asset, '💰')} {asset}", callback_data=f"crypto_{asset}")])
    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_buy_stars_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍💼 Себе", callback_data="buy_stars_self"), InlineKeyboardButton(text="🎁 Другому", callback_data="buy_stars_gift")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

def get_star_packs_kb(page: int, prefix: str, star_price: float, discount: float = None, back_target: str = "buy_stars") -> InlineKeyboardMarkup:
    start, end = page * PACKS_PER_PAGE, (page + 1) * PACKS_PER_PAGE
    packs = STAR_PACKS[start:end]
    kb = []
    for amount in packs:
        price = round(amount * star_price, 2)
        btn_text = f"⭐ {amount:,} Stars — {price}₽"
        if discount:
            discounted_price = round(price * (1 - float(discount) / 100), 2)
            btn_text = f"⭐ {amount:,} Stars — {price}₽ → {discounted_price}₽ (-{discount}%)"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"{prefix}_pack_{amount}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}_packs_page_{page-1}"))
    if end < len(STAR_PACKS):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}_packs_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=kb)
    
def get_buy_premium_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍💼 Себе", callback_data="buy_premium_self"), InlineKeyboardButton(text="🎁 Другому", callback_data="buy_premium_gift")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

def get_premium_plans_kb(premium_prices: list, discount: float = None, prefix: str = "buy_premium_self_plan", back_target: str = "buy_premium") -> InlineKeyboardMarkup:
    kb = []
    for i, plan in enumerate(PREMIUM_PLANS):
        price = premium_prices[i]
        btn_text = f"💎 {plan['name']} — {price}₽"
        if discount:
            discounted_price = round(price * (1 - float(discount) / 100), 2)
            btn_text += f" → {discounted_price}₽ (-{discount}%)"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"{prefix}_{i}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=kb)
    
def get_calculator_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Рассчитать по звездам", callback_data="calc_by_stars")],
        [InlineKeyboardButton(text="₽ Рассчитать по рублям", callback_data="calc_by_rub")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

def get_subscription_check_kb(channel_link: str) -> InlineKeyboardMarkup:
     return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться", url=channel_link)],
        [InlineKeyboardButton(text="Проверить подписку", callback_data=SubscribeCallback(action="check").pack())]
    ])