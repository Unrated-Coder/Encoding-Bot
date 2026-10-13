from asyncio import gather
from psutil import cpu_percent, virtual_memory, disk_usage, net_io_counters
from hydrogram import filters
from hydrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from time import time
import os

from .. import app, botStartTime, download_dir, data, sudo_users, owner
from ..utils.display_progress import humanbytes, TimeFormatter
from ..utils.helper import check_chat, StyledButton
from ..utils.ui import card, esc, sc, title_only

# Helper function for readable time
def get_readable_time(seconds):
    return TimeFormatter(seconds)

def get_readable_file_size(size):
    return humanbytes(size)

def get_task_info(task_msg):
    user = task_msg.from_user.first_name if task_msg.from_user else "Unknown User"
    user_id = task_msg.from_user.id if task_msg.from_user else "No ID"

    task_type = "unknown task"
    filename = "unknown file"

    text_content = task_msg.text or task_msg.caption
    if text_content:
        parts = text_content.split(None, 1)
        cmd = parts[0].lower()
        if '/dl' in cmd:
            task_type = "telegram download"
        elif '/af' in cmd:
            task_type = "audio processing"
        elif '/ddl' in cmd:
            task_type = "direct download"
        elif '/batch' in cmd:
            task_type = "batch process"

    if task_msg.document:
        filename = task_msg.document.file_name or "document"
        if task_type == "unknown task": task_type = "telegram download"
    elif task_msg.video:
        filename = task_msg.video.file_name or "video"
        if task_type == "unknown task": task_type = "telegram download"
    elif text_content and ('/ddl' in text_content or '/batch' in text_content):
        # Attempt to extract filename or url
        filename = "url task"

    return (f"<b>{sc(task_type)}</b> › <code>{esc(filename)}</code>\n"
            f"   ╰ {sc('user')} › <a href='tg://user?id={user_id}'>{esc(user)}</a>")


def build_status_text():
    count = len(data)
    cpu = cpu_percent()
    mem = virtual_memory().percent
    disk = disk_usage(download_dir).free
    upload_speed = humanbytes(net_io_counters().bytes_sent)
    download_speed = humanbytes(net_io_counters().bytes_recv)
    uptime = get_readable_time(time() - botStartTime)

    msg = card(
        "engine status",
        rows=[
            ("cpu", f"{cpu}%"),
            ("ram", f"{mem}%"),
            ("free disk", get_readable_file_size(disk)),
            ("traffic", f"⬆️ {upload_speed} | ⬇️ {download_speed}"),
            ("uptime", uptime or "0s"),
        ],
        icon="🔥",
    )

    if count:
        msg += f"\n<b>⚡ {sc('active tasks')} ({count})</b>"
        for i, task_msg in enumerate(data):
            msg += f"\n{i+1}. {get_task_info(task_msg)}"
    else:
        msg += f"\n✨ {sc('no active downloads right now, babe!')}"
    return msg


@app.on_message(filters.command("status"))
async def mirror_status(client, message: Message):
    c = await check_chat(message, chat='Both')
    if not c:
        return

    msg = build_status_text()
    buttons = InlineKeyboardMarkup([
        [StyledButton("ʀᴇꜰʀᴇꜱʜ ꜱᴛᴀᴛᴜꜱ", callback_data="status ref", style="primary")]
    ])

    await message.reply(msg, reply_markup=buttons, disable_web_page_preview=True)


@app.on_callback_query(filters.regex('^status'))
async def status_pages(client, query: CallbackQuery):
    data_split = query.data.split()
    cmd = data_split[1]

    if cmd == 'ref':
        msg = build_status_text()
        buttons = InlineKeyboardMarkup([
            [StyledButton("ʀᴇꜰʀᴇꜱʜ ꜱᴛᴀᴛᴜꜱ", callback_data="status ref", style="primary")]
        ])

        try:
            await query.message.edit(text=msg, reply_markup=buttons, disable_web_page_preview=True)
            await query.answer(sc("refreshed!"))
        except Exception as e:
            await query.answer(sc(f"error: {e}"))
    else:
        await query.answer(sc("unknown command"))
