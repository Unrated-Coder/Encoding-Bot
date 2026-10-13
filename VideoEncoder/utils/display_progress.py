

import asyncio
import math
import time

from .ui import card


from hydrogram.errors import FloodWait, MessageNotModified

_last_edit_times = {}
_edit_tasks = {}


async def progress_for_hydrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = max(now - start, 0.001)
    msg_id = getattr(message, 'id', id(message))

    # Anti-FloodWait rate limiting: at least 4.0 seconds between edits unless complete
    if current != total and (now - _last_edit_times.get(msg_id, 0)) < 4.0:
        return

    _last_edit_times[msg_id] = now

    percentage = current * 100 / total if total else 0
    speed = current / diff
    elapsed_time = round(diff)
    time_to_completion = round((total - current) / speed) if speed > 0 else 0

    text_content = _transfer_card(
        ud_type, percentage, humanbytes(current), humanbytes(total),
        humanbytes(speed) + "/s", TimeFormatter(seconds=elapsed_time),
        TimeFormatter(seconds=time_to_completion))

    # Non-blocking edit: create task in background so upload/download stream is never throttled
    async def _do_edit():
        try:
            await message.edit(text=text_content)
        except FloodWait as e:
            await asyncio.sleep(e.x)
        except (MessageNotModified, Exception):
            pass

    existing_task = _edit_tasks.get(msg_id)
    if existing_task and not existing_task.done():
        existing_task.cancel()

    _edit_tasks[msg_id] = asyncio.create_task(_do_edit())


async def progress_for_url(downloader, msg):
    now = time.time()
    msg_id = getattr(msg, 'id', id(msg))

    if not downloader.isFinished() and (now - _last_edit_times.get(msg_id, 0)) < 4.0:
        return

    _last_edit_times[msg_id] = now

    total_length = downloader.filesize if downloader.filesize else 0
    downloaded = downloader.get_dl_size()
    speed = downloader.get_speed(human=True)
    eta = downloader.get_eta(human=True)
    percentage = downloader.get_progress() * 100
    progress_str = _transfer_card(
        "Downloading", percentage, humanbytes(downloaded),
        humanbytes(total_length), speed, downloader.get_dl_time(human=True), eta)
    try:
        await msg.edit_text(progress_str)
    except FloodWait as e:
        await asyncio.sleep(e.x)
    except (MessageNotModified, Exception):
        pass


def _transfer_card(ud_type, percentage, done, total, speed, elapsed, eta):
    """modern card used for every download / upload progress message"""
    label = str(ud_type).replace("...", "").strip().lower()
    if "upload" in label:
        title, icon = "uploading", "⬆️"
    elif "download" in label:
        title, icon = "downloading", "⬇️"
    else:
        title, icon = (label or "processing"), "⚡"
    return card(
        title,
        rows=[
            ("size", f"{done or '0 B'} / {total or '?'}"),
            ("speed", speed),
            ("elapsed", elapsed or "-"),
            ("eta", eta or "-"),
        ],
        percent=percentage,
        icon=icon,
    )


def humanbytes(size):
    """ humanize size """
    if not size:
        return ""
    power = 1024
    t_n = 0
    power_dict = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        t_n += 1
    return "{:.2f} {}B".format(size, power_dict[t_n])


def TimeFormatter(seconds: float) -> str:
    """ humanize time """
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "")
    return tmp[:-2]
