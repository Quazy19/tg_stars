import logging
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from services.repository import Repository
from services.ton_api import get_ton_balance
from services.profit_calculator import ProfitCalculator
from keyboards.admin_kb import get_admin_panel_kb
from utils.safe_message import safe_answer, safe_answer_document, safe_delete_message
from config import Config

router = Router()

@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(call: types.CallbackQuery, state: FSMContext, repo: Repository, config: Config):
    await state.clear()
    is_maintenance = await repo.get_setting('maintenance_mode') == '1'
    
    balance, error = await get_ton_balance(config.ton_wallet_address)
    balance_text = f"💎 Баланс TON: `{balance:.4f} TON`" if not error else f"💎 Баланс TON: `Ошибка: {error}`"

    await safe_delete_message(call)
    
    await safe_answer(
        call,
        text=f"<b>⚙️ Админ панель</b>\n\n{balance_text}\n\nВыберите действие:",
        reply_markup=get_admin_panel_kb(is_maintenance)
    )

@router.callback_query(F.data == "admin_stats")
async def show_statistics(call: types.CallbackQuery, repo: Repository):
    stats = await repo.get_bot_statistics()
    profit_stats = await repo.get_profit_statistics()
    
    stats_text = (
        f"<b>📊 Статистика бота</b>\n\n"
        f"<b>Пользователи:</b>\n"
        f"› Всего: <code>{stats['total_users']}</code>\n"
        f"› За месяц: <code>{stats['month_users']}</code>\n\n"
        f"<b>Куплено звёзд ⭐:</b>\n"
        f"› За сегодня: <code>{stats['day_stars']:,}</code>\n"
        f"› За месяц: <code>{stats['month_stars']:,}</code>\n"
        f"› За всё время: <code>{stats['total_stars']:,}</code>\n\n"
        f"<b>💰 Финансы:</b>\n"
        f"› Выручка сегодня: <code>{profit_stats['day_revenue']:.2f}₽</code>\n"
        f"› Прибыль сегодня: <code>{profit_stats['day_profit']:.2f}₽</code>\n"
        f"› Выручка за месяц: <code>{profit_stats['month_revenue']:.2f}₽</code>\n"
        f"› Прибыль за месяц: <code>{profit_stats['month_profit']:.2f}₽</code>\n"
        f"› Общая выручка: <code>{profit_stats['total_revenue']:.2f}₽</code>\n"
        f"› Общая прибыль: <code>{profit_stats['total_profit']:.2f}₽</code>"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📈 Детальная статистика", callback_data="admin_detailed_stats")],
        [types.InlineKeyboardButton(text="💾 Выгрузить базу данных", callback_data="admin_export_db")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
    ])
    
    try:
        await call.message.edit_text(stats_text, reply_markup=kb)
    except Exception as e:
        if "message is not modified" in str(e):
            await call.answer("Статистика уже актуальна", show_alert=False)
        else:
            logging.error(f"Failed to edit statistics message: {e}")
            await call.answer("Ошибка обновления статистики", show_alert=True)

@router.callback_query(F.data == "admin_detailed_stats")
async def show_detailed_statistics(call: types.CallbackQuery, repo: Repository):
    profit_stats = await repo.get_profit_statistics()
    profit_calc = ProfitCalculator()
    
    day_margin = profit_calc.get_profit_margin(
        profit_stats['day_revenue'] - profit_stats['day_profit'], 
        profit_stats['day_revenue']
    ) if profit_stats['day_revenue'] > 0 else 0
    
    month_margin = profit_calc.get_profit_margin(
        profit_stats['month_revenue'] - profit_stats['month_profit'], 
        profit_stats['month_revenue']
    ) if profit_stats['month_revenue'] > 0 else 0
    
    total_margin = profit_calc.get_profit_margin(
        profit_stats['total_revenue'] - profit_stats['total_profit'], 
        profit_stats['total_revenue']
    ) if profit_stats['total_revenue'] > 0 else 0
    
    ton_rate = await profit_calc.get_ton_rub_rate()
    
    detailed_text = (
        f"<b>📈 Детальная статистика</b>\n\n"
        f"<b>💹 Маржинальность:</b>\n"
        f"› Сегодня: <code>{day_margin:.1f}%</code>\n"
        f"› За месяц: <code>{month_margin:.1f}%</code>\n"
        f"› Общая: <code>{total_margin:.1f}%</code>\n\n"
        f"<b>💱 Курсы:</b>\n"
        f"› TON/RUB: <code>{ton_rate:.2f}₽</code>\n\n"
        f"<b>📊 Средние чеки:</b>\n"
        f"› Сегодня: <code>{profit_stats['day_revenue'] / max(1, profit_stats.get('day_orders', 1)):.2f}₽</code>\n"
        f"› За месяц: <code>{profit_stats['month_revenue'] / max(1, profit_stats.get('month_orders', 1)):.2f}₽</code>\n\n"
        f"<b>🎯 Эффективность:</b>\n"
        f"› Прибыль на пользователя: <code>{profit_stats['total_profit'] / max(1, profit_stats.get('total_users', 1)):.2f}₽</code>"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ К статистике", callback_data="admin_stats")]
    ])
    
    try:
        await call.message.edit_text(detailed_text, reply_markup=kb)
    except Exception as e:
        if "message is not modified" in str(e):
            await call.answer("Детальная статистика уже актуальна", show_alert=False)
        else:
            logging.error(f"Failed to edit detailed statistics message: {e}")
            await call.answer("Ошибка обновления детальной статистики", show_alert=True)

@router.callback_query(F.data == "admin_export_db")
async def export_database(call: types.CallbackQuery, config: Config):
    import os
    import shutil
    from datetime import datetime
    import pytz
    from aiogram.types import FSInputFile
    
    if not os.path.exists(config.database_path):
        await call.answer("База данных не найдена", show_alert=True)
        return
    
    try:
        timestamp = datetime.now(pytz.timezone('Europe/Moscow')).strftime("%Y-%m-%d_%H-%M-%S")
        backup_filename = f"database_export_{timestamp}.db"
        
        shutil.copy(config.database_path, backup_filename)

        document = FSInputFile(backup_filename)
        caption = f"📊 Экспорт базы данных\n🕐 {timestamp} МСК"
        
        await safe_answer_document(
            call,
            document=document,
            caption=caption
        )

        os.remove(backup_filename)
        
        await call.answer("База данных выгружена", show_alert=False)
        
    except Exception as e:
        logging.error(f"Failed to export database: {e}")
        await call.answer("Ошибка при выгрузке базы данных", show_alert=True)
    except Exception as e:
        if "message is not modified" in str(e):
            await call.answer("Детальная статистика уже актуальна", show_alert=False)
        else:
            logging.error(f"Failed to edit detailed statistics message: {e}")

            await call.answer("Ошибка обновления детальной статистики", show_alert=True)
