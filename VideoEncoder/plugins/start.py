

import os
import shutil
import time
from os import execl as osexecl
from subprocess import run as srun
from sys import executable
from time import time

from psutil import (boot_time, cpu_count, cpu_percent, disk_usage,
                    net_io_counters, swap_memory, virtual_memory)
from hydrogram import Client, filters
from hydrogram.types import Message

from .. import botStartTime, download_dir, encode_dir
from ..utils.database.access_db import db
from ..utils.database.add_user import AddUserToDatabase
from ..utils.display_progress import TimeFormatter, humanbytes
from ..utils.helper import check_chat, delete_downloads, start_but
from ..utils.ui import card, sc, title_only, tree

import random

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

START_IMAGES = [
    "https://imgyx.pages.dev/0DQNi",
    "https://imgyx.pages.dev/wdnkl",
    "https://imgyx.pages.dev/ie3RW",
    "https://imgyx.pages.dev/q0yyF",
    "https://imgyx.pages.dev/031KP"
]

_last_start_img = None


def get_random_start_image():
    global _last_start_img
    available = [img for img in START_IMAGES if img != _last_start_img]
    chosen = random.choice(available)
    _last_start_img = chosen
    return chosen


def uptime():
    """ returns uptime """
    return TimeFormatter(time.time() - botStartTime)


def build_start_text(mention):
    tagline = sc("i've been waiting for you, babe! send me your heavy videos and let me handle them with care ~ 🔥")
    return (
        f"<b>{sc('hey gorgeous')} {mention}... ✨</b>\n"
        f"<i>{tagline}</i>\n"
        f"├ <b>{sc('speed')}</b> › ⚡ {sc('ultra fast')}\n"
        f"├ <b>{sc('quality')}</b> › 🎯 {sc('unmatched')}\n"
        f"╰ <b>{sc('mode')}</b> › 😈 {sc('ready for action')}"
    )


_HELP_USER = [
    "send any video or media file directly",
    "/360p, /480p, /540p, /576p, /720p, /1080p › compress directly (optional: `-crf23` or `-crf 23`)",
    "/fetch › encode url / magnet / torrent (`/fetch [url] | [filename]`)",
    "/batch › encode links in batch",
    "/queue › check current queue status",
    "/settings › customize your video & auto-rename options",
    "/stats › check my engine condition",
]

_HELP_ADMIN = [
    "/clean › clear junk files",
    "/clear › clear processing queue",
    "/update › pull fresh updates",
    "/restart › reboot the bot",
]


def build_help_text(with_support=True):
    text = (
        f"<b>✨ {sc('hey babe, here is everything i can do for you ~ 🔥')}</b>\n"
        f"<b>📌 {sc('user menu')}</b>\n"
        f"{tree(_HELP_USER)}\n"
        f"<b>⚡ {sc('admin controls')}</b>\n"
        f"{tree(_HELP_ADMIN)}"
    )
    if with_support:
        text += (
            f"\n<b>💬 {sc('main channel')}</b> › <a href='https://t.me/Unrated_Coder'>{sc('click here')}</a>"
            f"\n<b>💖 {sc('support')}</b> › <a href='https://t.me/anireal_support'>@anireal_support</a>"
        )
    return text


def build_about_text():
    return (
        f"<b>ℹ️ {sc('about this bot ~ ✨')}</b>\n"
        f"<i>⚡ {sc('a high-performance asynchronous video processing, compression & encoding bot.')}</i>\n"
        f"├ <b>{sc('developer')}</b> › <a href='https://t.me/Og_Luffytaro'>@Og_Luffytaro</a>\n"
        f"├ <b>{sc('main channel')}</b> › <a href='https://t.me/Unrated_Coder'>@Unrated_Coder</a>\n"
        f"├ <b>{sc('support group')}</b> › <a href='https://t.me/anireal_support'>@anireal_support</a>\n"
        f"╰ <b>{sc('library')}</b> › <code>Hydrogram + Python + FFmpeg</code>"
    )


@Client.on_message(filters.command('start'))
async def start_message(app, message):
    c = await check_chat(message, chat='Both')
    if not c:
        return
    await AddUserToDatabase(app, message)
    img = get_random_start_image()
    text = build_start_text(message.from_user.mention())
    try:
        await message.reply_photo(photo=img, caption=text, reply_markup=start_but)
    except Exception:
        text_with_img = f"<a href='{img}'>&#8203;</a>" + text
        await message.reply_text(text=text_with_img, reply_markup=start_but, disable_web_page_preview=False)


@Client.on_message(filters.command('help'))
async def help_message(app, message):
    c = await check_chat(message, chat='Both')
    if not c:
        return
    await AddUserToDatabase(app, message)
    from hydrogram.types import InlineKeyboardMarkup
    from ..utils.helper import StyledButton
    help_but = InlineKeyboardMarkup([
        [StyledButton("ꜱᴇᴛᴛɪɴɢꜱ", callback_data="OpenSettings", style="success")]
    ])
    await message.reply(text=build_help_text(), disable_web_page_preview=True, reply_markup=help_but)


@Client.on_message(filters.command('stats'))
async def show_status_count(_, event: Message):
    c = await check_chat(event, chat='Both')
    if not c:
        return
    await AddUserToDatabase(_, event)
    text = await show_status(_)
    await event.reply_text(text)


async def show_status(_):
    currentTime = TimeFormatter(time() - botStartTime)
    osUptime = TimeFormatter(time() - boot_time())
    total, used, free, disk = disk_usage('/')
    total = humanbytes(total)
    used = humanbytes(used)
    free = humanbytes(free)
    sent = humanbytes(net_io_counters().bytes_sent)
    recv = humanbytes(net_io_counters().bytes_recv)
    cpuUsage = cpu_percent(interval=0.5)
    mem = virtual_memory()
    mem_t = humanbytes(mem.total)
    mem_a = humanbytes(mem.available)
    mem_u = humanbytes(mem.used)
    total_users = await db.total_users_count()

    return card(
        "engine status & health",
        rows=[
            ("bot uptime", currentTime or "0s"),
            ("os uptime", osUptime or "0s"),
            ("storage", f"{used} / {total} ({free} free)"),
            ("cpu load", f"{cpuUsage}%"),
            ("ram", f"{mem_u} / {mem_t} ({mem_a} free)"),
            ("traffic", f"⬆️ {sent} | ⬇️ {recv}"),
            ("users", total_users),
        ],
        icon="🔥",
    )


async def showw_status(_):
    return await show_status(_)


@Client.on_message(filters.command('clean'))
async def delete_files(_, message):
    c = await check_chat(message, chat='Sudo')
    if not c:
        return
    msg = await message.reply_text(title_only("cleaning junk, wait a bit", "🧹"))
    cleaned = delete_downloads()
    if cleaned:
        await msg.edit_text(title_only("cleaned up all junk files", "🧹"))
    else:
        await msg.edit_text(title_only("no junk found", "✨"))


@Client.on_message(filters.command('restart'))
async def font_message(app, message):
    c = await check_chat(message, chat='Sudo')
    if not c:
        return
    await AddUserToDatabase(app, message)
    reply = await message.reply_text(card('rebooting engines', rows=[('status', 'hold tight babe')], icon='🔄'))
    textx = card("restart done", rows=[("status", "ready for action")], icon="✅")
    await reply.edit_text(textx)
    try:
        exit()
    finally:
        osexecl(executable, executable, "-m", "VideoEncoder")


@Client.on_message(filters.command('update'))
async def update_message(app, message):
    c = await check_chat(message, chat='Sudo')
    if not c:
        return
    await AddUserToDatabase(app, message)
    reply = await message.reply_text(card('fetching fresh updates', rows=[('status', 'getting ready for you')], icon='📶'))
    textx = card("updated successfully", rows=[("status", "everything is up to date")], icon="✅")
    await reply.edit_text(textx)
    try:
        await app.stop()
    finally:
        srun([f"bash run.sh"], shell=True)
