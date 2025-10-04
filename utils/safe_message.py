from aiogram import types
import logging

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

async def safe_answer_photo(call: types.CallbackQuery, photo, caption=None, reply_markup=None, **kwargs)
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
