

import asyncio

from hydrogram import Client, filters

from .. import data, video_mimetype
from ..utils.database.add_user import AddUserToDatabase
from ..utils.helper import check_chat
from ..utils.tasks import start_next_tasks
from ..utils.ui import card, sc, title_only


@Client.on_message(filters.command(['360p', '480p', '540p', '576p', '720p', '1080p']))
async def quality_encode(app, message):
    c = await check_chat(message, chat='Both')
    if not c:
        return
    await AddUserToDatabase(app, message)

    # Check if replying to a file or file is attached
    if not (message.reply_to_message and (message.reply_to_message.video or message.reply_to_message.document)) and \
       not (message.video or message.document):
           await message.reply(card("reply needed", rows=[("how to", "reply to a video / document file")], icon="⚠️"))
           return

    data.append(message)
    await start_next_tasks()
    if not getattr(message, '_is_active', False):
        pos = data.index(message) + 1
        await message.reply(card("queued up", rows=[("position", f"#{pos}"), ("item", "your file")], note="i'll take care of it soon ~ 🔥", icon="⏳"))
    await asyncio.sleep(1)

@Client.on_message(filters.command('af'))
async def audio_features(app, message):
    c = await check_chat(message, chat='Both')
    if not c:
        return
    await AddUserToDatabase(app, message)

    # Check if replying to a file or file is attached
    if not (message.reply_to_message and (message.reply_to_message.video or message.reply_to_message.document)) and \
       not (message.video or message.document):
           await message.reply(card("reply needed", rows=[("how to", "reply to a video / document file")], icon="⚠️"))
           return

    data.append(message)
    await start_next_tasks()
    if not getattr(message, '_is_active', False):
        pos = data.index(message) + 1
        await message.reply(card("queued up", rows=[("position", f"#{pos}"), ("item", "your file")], note="i'll take care of it soon ~ 🔥", icon="⏳"))
    await asyncio.sleep(1)

@Client.on_message(filters.command('fetch'))
async def fetch_encode(app, message):
    c = await check_chat(message, chat='Both')
    if not c:
        return
    await AddUserToDatabase(app, message)
    if len(message.text.split()) == 1:
        await message.reply_text(card("wrong usage", rows=[("use", "/fetch [url] | [filename]")], icon="⚠️"))
        return
    data.append(message)
    await start_next_tasks()
    if not getattr(message, '_is_active', False):
        pos = data.index(message) + 1
        await message.reply(card("queued up", rows=[("position", f"#{pos}"), ("item", "your link")], note="i'll process it soon ~ 🔥", icon="⏳"))
    await asyncio.sleep(1)


@Client.on_message(filters.command('batch'))
async def batch_encode(app, message):
    c = await check_chat(message, chat='Both')
    if not c:
        return
    await AddUserToDatabase(app, message)
    if len(message.text.split()) == 1:
        await message.reply_text(card("wrong usage", rows=[("use", "/batch [url]")], icon="⚠️"))
        return
    data.append(message)
    await start_next_tasks()
    if not getattr(message, '_is_active', False):
        pos = data.index(message) + 1
        await message.reply(card("queued up", rows=[("position", f"#{pos}"), ("item", "batch links")], note="hold tight ~ 🔥", icon="⏳"))
    await asyncio.sleep(1)


@Client.on_message(filters.private & (filters.video | filters.document) & ~filters.command([]))
async def media_file_handler(app, message):
    c = await check_chat(message, chat='Both')
    if not c:
        return
    await AddUserToDatabase(app, message)

    if message.document and message.document.mime_type not in video_mimetype:
        return

    await message.reply_text(
        card(
            "file received",
            rows=[("next", sc("reply to this file with /480p, /720p or /1080p"), True),
                  ("optional", "-crf23 or -crf 23"),
                  ("uses", sc("your default /settings"), True)],
            icon="📥",
        )
    )
