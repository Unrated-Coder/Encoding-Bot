import logging
from hydrogram import Client, filters
from hydrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from ..utils.database.access_db import db
from ..utils.helper import StyledButton
from ..utils.ui import card, sc, title_only

LOGGER = logging.getLogger(__name__)

@Client.on_message(filters.command(["thumb", "viewthumb"]))
async def view_thumb_command(client, message):
    try:
        user_id = message.from_user.id
        thumbnail = await db.get_thumbnail(user_id)
        buttons = [
            [
                StyledButton("ꜱᴇᴛ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="set_thumb", style="success"),
                StyledButton("ᴅᴇʟᴇᴛᴇ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="del_thumb", style="danger")
            ]
        ]
        if thumbnail:
            await message.reply_photo(
                photo=thumbnail,
                caption=title_only("your current custom thumbnail", "🖼"),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await message.reply_text(
                card("no custom thumbnail set", rows=[("how to", "send an image, or reply to one with /setthumb")], icon="❌"),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception as e:
        LOGGER.error(f"Error in view_thumb_command: {e}")
        await message.reply_text(card("something went wrong", rows=[("error", e)], icon="❌"))


@Client.on_message(filters.command("setthumb"))
async def set_thumb_command(client, message):
    try:
        user_id = message.from_user.id
        # Case 1: Reply to a photo or photo in current message
        photo = None
        if message.photo:
            photo = message.photo
        elif message.reply_to_message and message.reply_to_message.photo:
            photo = message.reply_to_message.photo

        if photo:
            await db.set_thumbnail(user_id, photo.file_id)
            await message.reply_text(title_only("yosh!! custom thumbnail saved successfully", "✅"))
        else:
            await message.reply_text(card("custom thumbnail", rows=[("how to", "reply to a photo with /setthumb")], icon="🖼"))
    except Exception as e:
        LOGGER.error(f"Error in set_thumb_command: {e}")
        await message.reply_text(card("something went wrong", rows=[("error", e)], icon="❌"))


@Client.on_message(filters.command("delthumb"))
async def del_thumb_command(client, message):
    try:
        user_id = message.from_user.id
        thumb = await db.get_thumbnail(user_id)
        if thumb:
            await db.set_thumbnail(user_id, None)
            await message.reply_text(title_only("your saved thumbnail has been removed", "✅"))
        else:
            await message.reply_text(title_only("you do not have any saved thumbnail to delete", "⚠️"))
    except Exception as e:
        LOGGER.error(f"Error in del_thumb_command: {e}")
        await message.reply_text(card("something went wrong", rows=[("error", e)], icon="❌"))


@Client.on_callback_query(filters.regex("^(set_thumb|del_thumb)$"))
async def thumb_cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    try:
        if data == "set_thumb":
            await query.answer(sc("please send an image now"), show_alert=False)
            await query.message.reply_text(
                title_only("send me a photo to set as your custom thumbnail", "🖼")
            )
        elif data == "del_thumb":
            thumb = await db.get_thumbnail(user_id)
            if thumb:
                await db.set_thumbnail(user_id, None)
                await query.answer(sc("thumbnail deleted!"), show_alert=True)
                msg_text = title_only("your saved thumbnail has been removed", "✅")
            else:
                await query.answer(sc("no saved thumbnail!"), show_alert=True)
                msg_text = title_only("you do not have any saved thumbnail to delete", "⚠️")

            try:
                await query.message.edit_text(msg_text)
            except Exception:
                try:
                    await client.send_message(chat_id=user_id, text=msg_text)
                except Exception:
                    pass
    except Exception as e:
        LOGGER.error(f"Error in thumb_cb_handler for {data}: {e}")
        try:
            await query.answer(sc(f"error: {str(e)}"), show_alert=True)
        except Exception:
            pass


@Client.on_message(filters.photo & filters.private)
async def save_photo_thumb(client, message):
    try:
        user_id = message.from_user.id
        file_id = message.photo.file_id
        
        # Check if set via caption or reply prompt
        if message.caption and message.caption.strip().lower() in ["/thumb", "/setthumb"]:
            await db.set_thumbnail(user_id, file_id)
            await message.reply_text(title_only("yosh!! custom thumbnail saved successfully", "✅"))
        elif message.reply_to_message and sc("send me a photo to set as your custom thumbnail") in (message.reply_to_message.text or ""):
            await db.set_thumbnail(user_id, file_id)
            await message.reply_text(title_only("yosh!! custom thumbnail saved successfully", "✅"))
    except Exception as e:
        LOGGER.error(f"Error in save_photo_thumb: {e}")
        await message.reply_text(card("something went wrong", rows=[("error", e)], icon="❌"))
