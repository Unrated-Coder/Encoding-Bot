

import os
from urllib.parse import unquote_plus

from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import data
from ..utils.database.add_user import AddUserToDatabase
from ..utils.helper import check_chat, StyledButton
from ..utils.ui import card, sc, title_only

queue_callback_filter = filters.create(
    lambda _, __, query: query.data.startswith('queue+'))


async def get_title(i):
    try:
        if data[i].video:
            return data[i].video.file_name
        elif data[i].document:
            return data[i].document.file_name
        else:
            url = data[i].command[1]
            return str(unquote_plus(os.path.basename(url)))
    except:
        return None


def map(pos):
    if pos == 0:
        if len(data) > 1:
            button = [[StyledButton(
                text='ɴᴇxᴛ', callback_data="queue+1", style="primary")]]
        else:
            button = [[StyledButton(
                text='ɴᴏ ᴏᴛʜᴇʀ ᴛᴀꜱᴋ', callback_data="queue+-1", style="primary")]]
    else:
        try:
            if data[pos+1]:
                button = [
                    [
                        StyledButton(
                            text='ᴘʀᴇᴠɪᴏᴜꜱ', callback_data=f"queue+{pos-1}", style="primary"),
                        StyledButton(
                            text='ɴᴇxᴛ', callback_data=f"queue+{pos+1}", style="primary")
                    ],
                ]
        except Exception as e:
            button = [
                [
                    StyledButton(
                        text='ᴘʀᴇᴠɪᴏᴜꜱ', callback_data=f"queue+{pos-1}", style="primary")
                ],
            ]
    return button


async def queue_answer(app, callback_query):
    chatid = callback_query.from_user.id
    messageid = callback_query.message.id
    pos = int(callback_query.data.split('+')[1])
    if pos == -1:
        await callback_query.answer(sc("no task"), show_alert=True)
        return
    taskpos = pos+1
    size = len(data)
    tasktitle = await get_title(pos)
    await callback_query.edit_message_text(card(f"queue position {taskpos} of {size}", rows=[("file", tasktitle)], icon="📋"), reply_markup=InlineKeyboardMarkup(map(pos)))


@Client.on_message(filters.command(['queue']))
async def queue_message(app, message):
    c = await check_chat(message, chat='Both')
    if not c:
        return
    await AddUserToDatabase(app, message)
    msg = await message.reply_text(title_only("hold tight babe, checking queue...", "⏳"))
    size = len(data)
    if size >= 1:
        for i in range(1, size):
            pos = i-1
            taskpos = i
            tasktitle = await get_title(pos)
            await msg.edit(
                text=card(f"queue position {taskpos} of {size}", rows=[("file", tasktitle)], icon="📋"), reply_markup=InlineKeyboardMarkup(map(0)))
    else:
        await msg.edit(title_only('no active tasks right now darling!', '🥱'))


@Client.on_message(filters.command('clear'))
async def clear(app, message):
    c = await check_chat(message, chat='Sudo')
    if not c:
        return
    await AddUserToDatabase(app, message)
    if len(data) >= 1:
        current = data[0]
        data.clear()
        data.append(current)
        await message.reply(title_only('cleaned up the whole queue for you babe!', '🧹'))
    else:
        await message.reply(title_only("no active tasks right now darling!", "🥱"))
