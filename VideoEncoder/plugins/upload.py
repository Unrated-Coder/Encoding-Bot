

import html
import os
import time

from hydrogram import Client, filters
from hydrogram.errors.exceptions.bad_request_400 import MessageIdInvalid

from .. import download_dir, sudo_users
from ..utils.encoding import get_duration, get_thumbnail, get_width_height
from ..utils.helper import check_chat
from ..utils.ui import card, sc, title_only
from ..utils.uploads.drive.upload import Uploader
from ..utils.uploads.telegram import upload_doc, upload_video


@Client.on_message(filters.command('dupload'))
async def docupload(client, message):
    c = await check_chat(message, chat='Sudo')
    if not c:
        return
    c_time = time.time()
    file = os.path.expanduser(' '.join(message.command[1:]))
    if not file:
        await message.reply(title_only('you forgot to mention the path', '⚠️'))
        return
    text = card('uploading', rows=[('file', file)], icon='⬆️')
    reply = await message.reply(text)
    filename = os.path.basename(file)
    duration = get_duration(file)
    thumb = get_thumbnail(file, download_dir, duration / 4)

    try:
        await upload_doc(message, reply, c_time, filename, file, thumb=thumb)
    except Exception as e:
        await reply.edit(card('upload failed', rows=[('error', e)], icon='❌'))
    else:
        await reply.delete()


@Client.on_message(filters.command('vupload'))
async def videoupload(client, message):
    c = await check_chat(message, chat='Sudo')
    if c is None:
        return
    c_time = time.time()
    file = os.path.expanduser(' '.join(message.command[1:]))
    if not file:
        await message.reply_text(title_only('you forgot to mention the filepath', '⚠️'))
        return
    filename = os.path.basename(file)
    duration = get_duration(file)
    thumb = get_thumbnail(file, download_dir, duration / 4)
    width, height = get_width_height(file)
    text = card('uploading', rows=[('file', file)], icon='⬆️')
    reply = await message.reply_text(text)
    try:
        await upload_video(message, reply, file, filename,
                           c_time, thumb, duration, width, height)
    except Exception as e:
        await reply.edit(card('upload failed', rows=[('error', e)], icon='❌'))
    else:
        await reply.delete()


@Client.on_message(filters.command('gupload'))
async def driveupload(client, message):
    c = await check_chat(message, chat='Sudo')
    if c is None:
        return
    new_file = os.path.expanduser(' '.join(message.command[1:]))
    if not new_file:
        await message.reply_text(title_only('you forgot to mention the path', '⚠️'))
        return
    text = card('uploading', rows=[('file', new_file)], icon='⬆️')
    reply = await message.reply_text(text)
    try:
        u = Uploader()
        await u.upload_to_drive(new_file, message, reply)
    except:
        await reply.edit(title_only('error while uploading', '❌'))
    else:
        await reply.delete()


@Client.on_message(filters.command('logs'))
async def logsup(client, message):
    c = await check_chat(message, chat='Sudo')
    if c is None:
        return
    file = 'VideoEncoder/utils/extras/logs.txt'
    caption = sc('#logs')
    try:
        await message.reply_document(
            file,
            caption=caption
        )
    except MessageIdInvalid:
        await message.reply(title_only('upload cancelled', '🚫'))
    except Exception as e:
        await message.reply(card('something went wrong', rows=[('error', e)], icon='❌'))
