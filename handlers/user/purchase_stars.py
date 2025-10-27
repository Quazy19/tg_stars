import re
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from services.repository import Repository
from services.fragment_sender import FragmentSender
from services.profit_calculator import ProfitCalculator
from keyboards import user_kb
from states.user import BuyStarsGiftStates, BuyStarsSelfStates, BuyStarsConfirmStates
from .start import format_text_with_user_data
from config import Config
from utils.safe_message import safe_delete_and_send_photo, safe_edit_message

router = Router()

@router.callback_query(F.data == "buy_stars")
async def buy_stars_callback(call: types.CallbackQuery, state: FSMContext, config: Config):
    await state.clear()
    await safe_delete_and_send_photo(
        call, config, config.visuals.img_url_stars,
        "<b>Купить звёзды</b>\n\nКому вы хотите купить звёзды?",
        user_kb.get_buy_stars_kb()
    )

@router.callback_query(F.data == "buy_stars_self")
async def buy_stars_self_callback(call: types.CallbackQuery, config: Config):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔢 Ввести количество", callback_data="buy_stars_self_amount"), types.InlineKeyboardButton(text="📦 Готовые паки", callback_data="buy_stars_self_packs")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars")]
    ])
    await safe_edit_message(call, text="<b>Покупка звёзд для себя</b>\n\nВыберите способ:", reply_markup=kb)

@router.callback_query(F.data == "buy_stars_self_amount")
async def buy_stars_self_amount_callback(call: types.CallbackQuery, state: FSMContext):
    await safe_edit_message(call, text="<b>Введите количество звёзд для покупки (минимум 50):</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars_self")]]))
    await state.set_state(BuyStarsSelfStates.waiting_for_self_amount)

@router.message(BuyStarsSelfStates.waiting_for_self_amount)
async def process_self_amount(message: types.Message, state: FSMContext, repo: Repository):
    try:
        amount = int(message.text)
        if amount < 50:
            await message.answer("❗ Минимальное количество для покупки — 50 звёзд.")
            return
    except ValueError:
        await message.answer("❗ Введите целое число.")
        return

    star_price = float(await repo.get_setting('star_price'))
    total = round(amount * star_price, 2)
    user = await repo.get_user(message.from_user.id)
    discount = user["discount"]

    if discount:
        discounted_total = round(total * (1 - float(discount) / 100), 2)
        price_text = f"Вы выбрали: <b>{amount}</b> звёзд\nИтоговая стоимость: <s>{total}₽</s> <b>{discounted_total}₽</b> (скидка {discount}%)"
        await state.update_data(amount=amount, total=discounted_total)
    else:
        price_text = f"Вы выбрали: <b>{amount}</b> звёзд\nИтоговая стоимость: <b>{total}₽</b>"
        await state.update_data(amount=amount, total=total)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="buy_stars_self_confirm")], [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars_self")]])
    await message.answer(f"{price_text}\n\nПодтвердить покупку?", reply_markup=kb)
    await state.set_state(BuyStarsConfirmStates.waiting_for_confirm)

@router.callback_query(F.data == "buy_stars_self_packs")
@router.callback_query(F.data.startswith("buy_stars_self_packs_page_"))
async def buy_stars_self_packs_callback(call: types.CallbackQuery, repo: Repository):
    page = int(call.data.split("_")[-1]) if "page" in call.data else 0
    user = await repo.get_user(call.from_user.id)
    star_price = float(await repo.get_setting('star_price'))
    await safe_edit_message(call, text="<b>Выберите готовый пакет звёзд:</b>", reply_markup=user_kb.get_star_packs_kb(page, "buy_stars_self", star_price, user["discount"], back_target="buy_stars_self"))

@router.callback_query(F.data.startswith("buy_stars_self_pack_"))
async def buy_stars_self_pack_selected(call: types.CallbackQuery, state: FSMContext, repo: Repository):
    amount = int(call.data.split("_")[-1])
    star_price = float(await repo.get_setting('star_price'))
    total = round(amount * star_price, 2)
    user = await repo.get_user(call.from_user.id)
    discount = user["discount"]

    if discount:
        discounted_total = round(total * (1 - float(discount) / 100), 2)
        price_text = f"Вы выбрали пакет: <b>{amount}</b> звёзд\nИтоговая стоимость: {total}₽ → <b>{discounted_total}₽</b> (скидка {discount}%)"
        await state.update_data(amount=amount, total=discounted_total)
    else:
        price_text = f"Вы выбрали пакет: <b>{amount}</b> звёзд\nИтоговая стоимость: <b>{total}₽</b>"
        await state.update_data(amount=amount, total=total)
        
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="buy_stars_self_confirm")], [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars_self_packs")]])
    await safe_edit_message(call, text=f"{price_text}\n\nПодтвердить покупку?", reply_markup=kb)
    await state.set_state(BuyStarsConfirmStates.waiting_for_confirm)

@router.callback_query(BuyStarsConfirmStates.waiting_for_confirm, F.data == "buy_stars_self_confirm")
async def buy_stars_self_confirm_callback(call: types.CallbackQuery, state: FSMContext, repo: Repository, fragment_sender: FragmentSender):
    if not call.from_user.username:
        await call.answer("У вас нету логина в тг, установите его и попробуйте еще раз", show_alert=True)
        await state.clear()
        return
    
    data = await state.get_data()
    amount, total = data.get("amount"), data.get("total")
    user_obj = call.from_user
    user_db = await repo.get_user(user_obj.id)

    if float(user_db["balance"]) < total:
        error_message = f"Недостаточно средств! Не хватает: <b>{total - float(user_db['balance'])}₽</b>"
        error_kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="profile_topup_menu")]])
        await safe_edit_message(call, text=error_message, reply_markup=error_kb)
        await state.clear()
        return
        
    profit_calc = ProfitCalculator()
    cost_ton, profit_rub = await profit_calc.calculate_stars_profit(amount, total)
    
    success_text_template = await repo.get_setting('purchase_success_text')
    success_text = format_text_with_user_data(success_text_template, user_obj)
    
    await repo.update_user_balance(user_obj.id, total, operation='sub')
    
    success = await fragment_sender.send_stars(call.from_user.username, amount)
    
    if success:
        await repo.update_user_discount(user_obj.id, None)
        await repo.add_purchase_to_history(user_obj.id, 'stars', f'{amount} Stars', amount, total, profit_rub)
        await safe_edit_message(call, text=success_text, reply_markup=None)
        
        profit_text = (f"💰 <b>Новая продажа звёзд</b>\n\n"
                       f"👤 Покупатель: @{call.from_user.username}\n"
                       f"⭐ Количество: {amount} звёзд\n"
                       f"💵 Выручка: {total:.2f}₽\n"
                       f"📈 Прибыль: {profit_rub:.2f}₽\n"
                       f"📊 Маржа: {profit_calc.get_profit_margin(total - profit_rub, total):.1f}%")
        await fragment_sender._notify_admins(profit_text)
    else:
        await repo.update_user_balance(user_obj.id, total, operation='add')
        error_kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
        await safe_edit_message(call, text="❌ Произошла ошибка при отправке звёзд. Средства возвращены на ваш баланс. Обратитесь в поддержку.", reply_markup=error_kb)
    await state.clear()

@router.callback_query(F.data == "buy_stars_gift")
async def buy_stars_gift_callback(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_message(call, text="<b>Пожалуйста, укажите юзернейм (@username) получателя.</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars")]]))
    await state.set_state(BuyStarsGiftStates.waiting_for_recipient)

@router.message(BuyStarsGiftStates.waiting_for_recipient)
async def process_gift_recipient(message: types.Message, state: FSMContext, config: Config):
    match = re.match(r"^@?([a-zA-Z0-9_]{5,32})$", message.text.strip())
    if not match:
        await message.answer("❗️<b>Неверный формат!</b>\n\nВведите корректный юзернейм (например, <code>@username</code>).")
        return

    recipient = match.group(1)
    await state.update_data(recipient=recipient)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔢 Ввести количество", callback_data="buy_stars_gift_amount"), types.InlineKeyboardButton(text="📦 Готовые паки", callback_data="buy_stars_gift_packs")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars_gift")]
    ])
    
    await message.delete()
    await message.answer_photo(
        photo=config.visuals.img_url_stars,
        caption=f"Получатель: <code>@{recipient}</code>.\nВыберите способ:", 
        reply_markup=kb
    )

@router.callback_query(F.data == "buy_stars_gift_amount")
async def buy_stars_gift_amount_callback(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_gift_choice")]])
    await safe_edit_message(call, text=f"Получатель: <code>@{data.get('recipient')}</code>\n\n<b>Введите количество звёзд для подарка (минимум 50):</b>", reply_markup=kb)
    await state.set_state(BuyStarsGiftStates.waiting_for_gift_amount)

@router.callback_query(F.data == "buy_stars_gift_packs")
@router.callback_query(F.data.startswith("buy_stars_gift_packs_page_"))
async def buy_stars_gift_packs_callback(call: types.CallbackQuery, state: FSMContext, repo: Repository):
    page = int(call.data.split("_")[-1]) if "page" in call.data else 0
    data = await state.get_data()
    user = await repo.get_user(call.from_user.id)
    star_price = float(await repo.get_setting('star_price'))
    
    text = f"Получатель: <code>@{data.get('recipient')}</code>\n\n<b>Выберите пакет звёзд для подарка:</b>"
    kb = user_kb.get_star_packs_kb(page, "buy_stars_gift", star_price, user["discount"], back_target="back_to_gift_choice")
    await safe_edit_message(call, text=text, reply_markup=kb)

@router.callback_query(F.data.startswith("buy_stars_gift_pack_"))
async def buy_stars_gift_pack_selected(call: types.CallbackQuery, state: FSMContext, repo: Repository):
    amount = int(call.data.split("_")[-1])
    star_price = float(await repo.get_setting('star_price'))
    total = round(amount * star_price, 2)
    user = await repo.get_user(call.from_user.id)
    data = await state.get_data()
    recipient = data.get("recipient")
    discount = user["discount"]

    if discount:
        discounted_total = round(total * (1 - float(discount) / 100), 2)
        price_text = f"Пакет для <code>@{recipient}</code>: <b>{amount}</b> звёзд\nСтоимость: {total}₽ → <b>{discounted_total}₽</b> (скидка {discount}%)"
        await state.update_data(amount=amount, total=discounted_total)
    else:
        price_text = f"Пакет для <code>@{recipient}</code>: <b>{amount}</b> звёзд\nСтоимость: <b>{total}₽</b>"
        await state.update_data(amount=amount, total=total)
        
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="buy_stars_gift_confirm")], [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars_gift_packs")]])
    await safe_edit_message(call, text=f"{price_text}\n\nПодтвердить покупку?", reply_markup=kb)
    await state.set_state(BuyStarsConfirmStates.waiting_for_gift_confirm)

@router.message(BuyStarsGiftStates.waiting_for_gift_amount)
async def process_gift_amount(message: types.Message, state: FSMContext, repo: Repository):
    try:
        amount = int(message.text)
        if amount < 50:
            await message.answer("❗ Минимальное количество для подарка — 50 звёзд.")
            return
    except ValueError:
        await message.answer("❗ Введите целое число.")
        return

    star_price = float(await repo.get_setting('star_price'))
    total = round(amount * star_price, 2)
    data = await state.get_data()
    recipient = data.get("recipient")
    user = await repo.get_user(message.from_user.id)
    discount = user["discount"]

    if discount:
        discounted_total = round(total * (1 - float(discount) / 100), 2)
        price_text = f"Подарок для <code>@{recipient}</code>: <b>{amount}</b> звёзд\nСтоимость: <s>{total}₽</s> <b>{discounted_total}₽</b> (скидка {discount}%)"
        await state.update_data(amount=amount, total=discounted_total)
    else:
        price_text = f"Подарок для <code>@{recipient}</code>: <b>{amount}</b> звёзд\nСтоимость: <b>{total}₽</b>"
        await state.update_data(amount=amount, total=total)
        
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="buy_stars_gift_confirm")], [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars_gift_amount")]])
    await message.answer(f"{price_text}\n\nПодтвердить покупку?", reply_markup=kb)
    await state.set_state(BuyStarsConfirmStates.waiting_for_gift_confirm)

@router.callback_query(BuyStarsConfirmStates.waiting_for_gift_confirm, F.data == "buy_stars_gift_confirm")
async def buy_stars_gift_confirm_callback(call: types.CallbackQuery, state: FSMContext, repo: Repository, fragment_sender: FragmentSender):
    data = await state.get_data()
    amount, total, recipient = data.get("amount"), data.get("total"), data.get("recipient")
    user_obj = call.from_user
    user_db = await repo.get_user(user_obj.id)

    if float(user_db["balance"]) < total:
        error_message = f"Недостаточно средств! Не хватает: <b>{total - float(user_db['balance'])}₽</b>"
        error_kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="profile_topup_menu")]])
        await safe_edit_message(call, text=error_message, reply_markup=error_kb)
        await state.clear()
        return
        
    profit_calc = ProfitCalculator()
    cost_ton, profit_rub = await profit_calc.calculate_stars_profit(amount, total)
    
    success_text_template = await repo.get_setting('purchase_success_text')
    success_text = format_text_with_user_data(success_text_template, user_obj)
    
    await repo.update_user_balance(user_obj.id, total, operation='sub')
    
    success = await fragment_sender.send_stars(recipient, amount)
    
    if success:
        await repo.update_user_discount(user_obj.id, None) 
        await repo.add_purchase_to_history(user_obj.id, 'stars', f'{amount} Stars for @{recipient}', amount, total, profit_rub)
        final_message = f"{success_text}\n\nПодарок для <code>@{recipient}</code> на <b>{amount} звёзд</b> успешно отправлен!"
        await safe_edit_message(call, text=final_message, reply_markup=None)
        
        profit_text = (f"🎁 <b>Новый подарок звёзд</b>\n\n"
                       f"👤 Покупатель: @{call.from_user.username}\n"
                       f"🎯 Получатель: @{recipient}\n"
                       f"⭐ Количество: {amount} звёзд\n"
                       f"💵 Выручка: {total:.2f}₽\n"
                       f"📈 Прибыль: {profit_rub:.2f}₽\n"
                       f"📊 Маржа: {profit_calc.get_profit_margin(total - profit_rub, total):.1f}%")
        await fragment_sender._notify_admins(profit_text)
    else:
        await repo.update_user_balance(user_obj.id, total, operation='add')
        error_kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]])
        await safe_edit_message(call, text="❌ Произошла ошибка при отправке звёзд. Средства возвращены на ваш баланс. Обратитесь в поддержку.", reply_markup=error_kb)
    await state.clear()

@router.callback_query(F.data == "back_to_gift_choice")
async def back_to_gift_choice(call: types.CallbackQuery, state: FSMContext, config: Config):
    data = await state.get_data()
    recipient = data.get('recipient')
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔢 Ввести количество", callback_data="buy_stars_gift_amount"), types.InlineKeyboardButton(text="📦 Готовые паки", callback_data="buy_stars_gift_packs")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_stars_gift")]
    ])
    await call.message.delete()
    await call.message.answer_photo(
        photo=config.visuals.img_url_stars,
        caption=f"Получатель: <code>@{recipient}</code>.\nВыберите способ:", 
        reply_markup=kb
    )