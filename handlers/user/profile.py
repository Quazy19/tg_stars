import logging
from aiogram import F, Router, Bot, types
from aiogram.fsm.context import FSMContext
from datetime import datetime

from config import Config
from services.repository import Repository
from payments.cryptobot import create_cryptopay_invoice, get_usdt_rub_rate
from payments.lolzteam import create_lzt_payment_link
from payments.crystalpay import create_crystalpay_invoice
from payments.payment_manager import PaymentManager
from keyboards import user_kb
from states.user import TopupCryptoPayStates, TopupLztStates, TopupCrystalPayStates, PromoUserStates
from utils.safe_message import safe_answer_photo, safe_answer, safe_delete_message
from .start import show_main_menu

router = Router()

@router.callback_query(F.data == "profile")
async def profile_callback(call: types.CallbackQuery, repo: Repository, config: Config):
    user = await repo.get_or_create_user(call.from_user.id, call.from_user.username)
    total_stars_bought = await repo.get_total_stars_bought(user['telegram_id'])
    reg_date_obj = datetime.fromisoformat(user['created_at'])
    reg_date_formatted = reg_date_obj.strftime('%d.%m.%Y')

    text = (
        f"👤 Ваш профиль\n\n"
        f"🆔 ID: <code>{user['telegram_id']}</code>\n"
        f"💰 Баланс: <b>{user['balance']:.2f} ₽</b>\n"
        f"⭐️ Куплено звезд: <b>{total_stars_bought:,}</b>\n"
        f"📆 Первый запуск бота: <b>{reg_date_formatted}</b>"
    )
    
    await safe_delete_message(call)
    await safe_answer_photo(
        call,
        photo=config.img_url_profile,
        caption=text,
        reply_markup=user_kb.get_profile_kb()
    )

@router.callback_query(F.data == "profile_topup_menu")
async def profile_topup_menu_callback(call: types.CallbackQuery, config: Config):
    await safe_delete_message(call)
    await safe_answer_photo(
        call,
        photo=config.img_url_profile,
        caption="<b>💰 Выберите способ пополнения:</b>",
        reply_markup=user_kb.get_payment_method_kb()
    )

async def pre_topup_checks(call: types.CallbackQuery, repo: Repository, state: FSMContext) -> bool:
    if await repo.get_active_payment(call.from_user.id):
        await call.answer("У вас уже есть активный счет. Завершите или отмените его, чтобы создать новый.", show_alert=True)
        return False
    await state.clear()
    await repo.mark_old_payments_as_expired(call.from_user.id)
    return True

@router.callback_query(F.data == "topup_cryptobot")
async def topup_cryptobot_handler(call: types.CallbackQuery, state: FSMContext, repo: Repository):
    if not await pre_topup_checks(call, repo, state):
        return
        
    user = await repo.get_user(call.from_user.id)
    text = (
        f"<b>Пополнение через CryptoBot</b>\n\n"
        f"Ваш текущий баланс: <b>{user['balance']:.2f} ₽</b>\n\n"
        "Введите сумму пополнения в рублях (RUB):"
    )
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_topup_menu")]])
    await call.message.edit_caption(caption=text, reply_markup=kb)
    await state.set_state(TopupCryptoPayStates.waiting_for_amount)

@router.message(TopupCryptoPayStates.waiting_for_amount)
async def topup_cryptopay_amount(message: types.Message, state: FSMContext, repo: Repository, config: Config):
    try:
        amount_rub = float(message.text.replace(",", "."))
        if amount_rub < config.min_payment_amount:
            await message.answer(f"❗ Минимальная сумма пополнения — {config.min_payment_amount} ₽.")
            return
    except ValueError:
        await message.answer("❗ Введите корректную сумму.")
        return

    exchange_rate = await get_usdt_rub_rate(config)
    try:
        invoice_url, order_id = await create_cryptopay_invoice(config, message.from_user.id, amount_rub, exchange_rate)
    except Exception as e:
        await message.answer(f"Не удалось создать счет на оплату. Ошибка: {e}")
        return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Оплатить", url=invoice_url)],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_db_payment_{order_id}")]
    ])
    sent_message = await message.answer(f"Счёт на <b>{amount_rub:.2f} ₽</b> создан! Нажмите кнопку для оплаты через @CryptoBot.", reply_markup=kb)
    
    await repo.create_payment(order_id, message.from_user.id, sent_message.message_id, amount_rub, 'cryptobot', invoice_url=invoice_url)
    await state.clear()

@router.callback_query(F.data.startswith("cancel_db_payment_"))
async def cancel_db_payment_callback(call: types.CallbackQuery, repo: Repository):
    order_id = call.data.replace("cancel_db_payment_", "", 1)
    status_was_updated = await repo.update_payment_status(order_id, 'cancelled')
    
    if status_was_updated:
        await call.answer("Счет отменен.")
        try:
            await call.message.edit_text("✅ Счет успешно отменен.", reply_markup=None)
        except Exception:
            pass
    else:
        await call.answer("Этот счет уже недействителен.", show_alert=True)
        try:
            await call.message.edit_text("❌ Этот счет уже недействителен.", reply_markup=None)
        except Exception:
            pass

@router.callback_query(F.data == "topup_lzt")
async def topup_lzt_handler(call: types.CallbackQuery, state: FSMContext, config: Config, repo: Repository):
    if not await pre_topup_checks(call, repo, state):
        return
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_topup_menu")]])
    await call.message.edit_caption(caption=f"<b>Пополнение через LolzTeam</b>\n\nВведите сумму пополнения в рублях (минимум {config.min_payment_amount}₽):", reply_markup=kb)
    await state.set_state(TopupLztStates.waiting_for_amount)

@router.message(TopupLztStates.waiting_for_amount)
async def process_lzt_amount(message: types.Message, state: FSMContext, config: Config, payment_manager: PaymentManager, repo: Repository):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount < config.min_payment_amount:
            await message.answer(f"❌ Минимальная сумма: {config.min_payment_amount}₽")
            return
    except ValueError:
        await message.answer("❌ Введите корректную сумму.")
        return

    order_id = payment_manager.generate_order_id()
    payment_link = create_lzt_payment_link(config, amount, order_id)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔗 Перейти к оплате", url=payment_link)],
        [types.InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_db_payment_{order_id}")]
    ])
    
    sent_message = await message.answer(f"💰 Ваш счёт на {amount:.2f}₽ через LolzTeam.\n\n`ID: {order_id}`\n\nНажмите кнопку для перехода к оплате.", reply_markup=kb)
    await repo.create_payment(order_id, message.from_user.id, sent_message.message_id, amount, 'lzt', invoice_url=payment_link)
    await state.clear()

@router.callback_query(F.data == "topup_crystalpay")
async def topup_crystalpay_handler(call: types.CallbackQuery, state: FSMContext, config: Config, repo: Repository):
    if not await pre_topup_checks(call, repo, state):
        return
        
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_topup_menu")]])
    await call.message.edit_caption(caption=f"<b>Пополнение через CrystalPay</b>\n\nВведите сумму пополнения в рублях (минимум {config.min_payment_amount}₽):", reply_markup=kb)
    await state.set_state(TopupCrystalPayStates.waiting_for_amount)
    
@router.message(TopupCrystalPayStates.waiting_for_amount)
async def process_crystalpay_amount(message: types.Message, state: FSMContext, config: Config, payment_manager: PaymentManager, repo: Repository):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount < config.min_payment_amount:
            await message.answer(f"❌ Минимальная сумма: {config.min_payment_amount}₽")
            return
    except ValueError:
        await message.answer("❌ Введите корректную сумму.")
        return

    order_id = payment_manager.generate_order_id()
    payment_url, invoice_id = await create_crystalpay_invoice(config, amount, order_id)

    if not payment_url:
        await message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔮 Оплатить через CrystalPay", url=payment_url)],
        [types.InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_db_payment_{order_id}")]
    ])
    
    sent_message = await message.answer(f"💎 Ваш счёт на {amount:.2f}₽ через CrystalPay.\n\n`ID: {order_id}`\n\nНажмите кнопку для перехода к оплате.", reply_markup=kb)
    await repo.create_payment(order_id, message.from_user.id, sent_message.message_id, amount, 'crystalpay', invoice_url=payment_url, external_invoice_id=invoice_id)
    await state.clear()

@router.callback_query(F.data == "profile_activate_promo")
async def profile_activate_promo_callback(call: types.CallbackQuery, state: FSMContext):
    await safe_delete_message(call)
    cancel_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="❌ Отменить", callback_data="profile")]
    ])
    await safe_answer(call, "<b>Активация промокода</b>\n\nВведите промокод:", reply_markup=cancel_kb)
    await state.set_state(PromoUserStates.waiting_for_code)

@router.message(PromoUserStates.waiting_for_code)
async def promo_user_enter_code(message: types.Message, state: FSMContext, repo: Repository, config: Config):
    code = message.text.strip().upper()
    user_id = message.from_user.id
    promo = await repo.get_promo_by_code(code)
    
    if not promo or (promo['expires_at'] and datetime.fromisoformat(promo['expires_at']) < datetime.now()) or (promo['max_uses'] and promo['current_uses'] >= promo['max_uses']):
        await message.answer("❗ Промокод не найден или неактивен.")
        return

    if await repo.check_promo_usage_by_user(user_id, promo['id']):
        await message.answer("❗ Вы уже использовали этот промокод.")
        return

    await repo.activate_promo_for_user(user_id, promo)
    if promo['promo_type'] == 'discount':
        await message.answer(f"🎉 Промокод <code>{code}</code> активирован! Ваша скидка: <b>{promo['value']}%</b> на следующую покупку.")
    else:
        await message.answer(f"🎉 Промокод <code>{code}</code> активирован! Баланс пополнен на <b>{promo['value']} ₽</b>.")
    
    await state.clear()
    await show_main_menu(message, repo, config, message.from_user)