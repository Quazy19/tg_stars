from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from services.repository import Repository
from states.admin import PriceStates
from keyboards.admin_kb import get_prices_menu_kb, get_premium_prices_kb
from keyboards.user_kb import PREMIUM_PLANS

router = Router()

async def get_premium_prices(repo: Repository):
    keys = [f'premium_price_{i}' for i in range(len(PREMIUM_PLANS))]
    prices_db = await repo.get_multiple_settings(keys)
    return [float(prices_db.get(f'premium_price_{i}', plan['price'])) for i, plan in enumerate(PREMIUM_PLANS)]

@router.callback_query(F.data == "admin_prices")
async def admin_prices_menu(call: types.CallbackQuery):
    await call.message.edit_text(text="<b>📈 Управление ценами</b>", reply_markup=get_prices_menu_kb())

@router.callback_query(F.data == "price_stars")
async def price_stars_show(call: types.CallbackQuery, state: FSMContext, repo: Repository):
    star_price = await repo.get_setting('star_price')
    await call.message.edit_text(
        text=f"<b>⭐ Текущая цена за 1 звезду:</b> <code>{star_price}</code> ₽\n\nВведите новую цену:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_prices")]])
    )
    await state.set_state(PriceStates.stars_input)

@router.message(PriceStates.stars_input)
async def price_stars_input_msg(message: types.Message, state: FSMContext, repo: Repository):
    try:
        price = float(message.text.replace(",", "."))
        if price <= 0: raise ValueError
    except ValueError:
        await message.answer("Введите корректное положительное число.")
        return
    await repo.update_setting('star_price', price)
    await message.answer(f"✅ Цена за 1 звезду изменена на <b>{price}₽</b>.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="В админ-панель", callback_data="admin_panel")]]))
    await state.clear()

@router.callback_query(F.data == "price_premium")
async def price_premium_choose(call: types.CallbackQuery, state: FSMContext, repo: Repository):
    premium_prices = await get_premium_prices(repo)
    await call.message.edit_text(
        text="<b>💎 Выберите тариф для изменения цены:</b>",
        reply_markup=get_premium_prices_kb(premium_prices)
    )
    await state.set_state(PriceStates.premium_choose)
    
@router.callback_query(PriceStates.premium_choose, F.data.startswith("price_premium_"))
async def price_premium_input_start(call: types.CallbackQuery, state: FSMContext):
    plan_index = int(call.data.split("_")[-1])
    await state.update_data(plan_index=plan_index)
    await call.message.edit_text(
        f"<b>💎 Тариф «{PREMIUM_PLANS[plan_index]['name']}»</b>\n\nВведите новую цену в рублях:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_prices")]])
    )
    await state.set_state(PriceStates.premium_input)

@router.message(PriceStates.premium_input)
async def price_premium_input_msg(message: types.Message, state: FSMContext, repo: Repository):
    try:
        price = float(message.text.replace(",", "."))
        if price <= 0: raise ValueError
    except ValueError:
        await message.answer("Введите корректное положительное число.")
        return
        
    data = await state.get_data()
    plan_index = data.get("plan_index")
    await repo.update_setting(f'premium_price_{plan_index}', price)
    await message.answer(f"✅ Цена тарифа «{PREMIUM_PLANS[plan_index]['name']}» изменена на <b>{price}₽</b>.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="В админ-панель", callback_data="admin_panel")]]))
    await state.clear()