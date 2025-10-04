from aiogram import types
from aiogram.exceptions import TelegramBadRequest
import logging
from config import Config

async def safe_delete_and_send_photo(call: types.CallbackQuery, config: Config, photo_url: str, text: str, reply_markup: types.InlineKeyboardMarkup = None):
    try:
        await call.message.delete()
    except Exception:
        pass
    try:
        await call.message.answer_photo(photo=photo_url, caption=text, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Failed to send photo after delete: {e}")
        await call.bot.send_photo(chat_id=call.from_user.id, photo=photo_url, caption=text, reply_markup=reply_markup)

async def safe_answer(call: types.CallbackQuery, text: str, reply_markup=None, **kwargs):
    try:
        return await call.message.answer(text=text, reply_markup=reply_markup, **kwargs)
    except AttributeError:
        return await call.bot.send_message(
            chat_id=call.from_user.id,
            text=text,
            reply_markup=reply_markup,
            **kwargs
        )
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        return None

async def safe_answer_photo(call: types.CallbackQuery, photo, caption=None, reply_markup=None, **kwargs):
    try:
        return await call.message.answer_photo(photo=photo, caption=caption, reply_markup=reply_markup, **kwargs)
    except AttributeError:
        return await call.bot.send_photo(
            chat_id=call.from_user.id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            **kwargs
        )
    except Exception as e:
        logging.error(f"Failed to send photo: {e}")
        return None

async def safe_answer_document(call: types.CallbackQuery, document, caption=None, reply_markup=None, **kwargs):
    try:
        return await call.message.answer_document(document=document, caption=caption, reply_markup=reply_markup, **kwargs)
    except AttributeError:
        return await call.bot.send_document(
            chat_id=call.from_user.id,
            document=document,
            caption=caption,
            reply_markup=reply_markup,
            **kwargs
        )
    except Exception as e:
        logging.error(f"Failed to send document: {e}")
        return None

async def safe_delete_message(call: types.CallbackQuery):
    try:
        await call.message.delete()
        return True
    except Exception:
        return False

async def safe_edit_message(call: types.CallbackQuery, text: str, reply_markup=None, **kwargs):
    try:
        if call.message.photo:
            await call.message.edit_caption(caption=text, reply_markup=reply_markup, **kwargs)
        else:
            await call.message.edit_text(text=text, reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            logging.warning(f"Failed to edit message, falling back to sending a new one. Error: {e}")
            await safe_delete_message(call)
            if call.message.photo:
                await safe_answer_photo(call, photo=call.message.photo[-1].file_id, caption=text, reply_markup=reply_markup, **kwargs)
            else:
                await safe_answer(call, text=text, reply_markup=reply_markup, **kwargs)
    except Exception as e:
        logging.error(f"An unexpected error occurred in safe_edit_message: {e}")
        await safe_delete_message(call)
        await safe_answer(call, text=text, reply_markup=reply_markup, **kwargs)
