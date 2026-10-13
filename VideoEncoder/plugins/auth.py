

from hydrogram import Client, filters

from .. import everyone, sudo_users
from ..utils.database.access_db import db
from ..utils.helper import check_chat, output
from ..utils.ui import card, title_only


@Client.on_message(filters.command('addchat'))
async def addchat(client, message):
    c = await check_chat(message, chat='Owner')
    if not c:
        return
    user_id = get_id(message)
    auth = await db.get_chat()
    if user_id in everyone:
        await reply_already_auth(message)
        return
    elif str(user_id) in auth:
        await reply_already_auth(message)
        return
    else:
        auth += ' ' + str(user_id)
        await db.set_chat(auth)
        await message.reply_text(card('added to auth chats', rows=[('id', user_id)], icon='✅'))


@Client.on_message(filters.command('addsudo'))
async def addsudo(client, message):
    c = await check_chat(message, chat='Owner')
    if not c:
        return
    user_id = get_id(message)
    auth = await db.get_sudo()
    if user_id in sudo_users:
        await reply_already_auth(message)
        return
    elif str(user_id) in auth:
        await reply_already_auth(message)
        return
    else:
        auth += ' ' + str(user_id)
        await db.set_sudo(auth)
        await message.reply_text(card('added to sudo chats', rows=[('id', user_id)], icon='✅'))


@Client.on_message(filters.command('rmchat'))
async def rmchat(client, message):
    c = await check_chat(message, chat='Owner')
    if not c:
        return
    user_id = get_id(message)
    check = await db.get_chat()
    if str(user_id) in check:
        user_id = ' ' + str(user_id)
        auth = check.replace(user_id, '')
        await db.set_chat(auth)
        await message.reply_text(card('removed from auth chats', rows=[('id', str(user_id).strip())], icon='🗑'))
        return
    elif user_id in everyone:
        await message.reply_text(title_only('config auth removal is not supported yet', '⚠️'))
        return
    else:
        await message.reply_text(title_only('chat is not auth yet', '⚠️'))


@Client.on_message(filters.command('rmsudo'))
async def rmsudo(client, message):
    c = await check_chat(message, chat='Owner')
    if not c:
        return
    user_id = get_id(message)
    check = await db.get_sudo()
    if str(user_id) in check:
        user_id = ' ' + str(user_id)
        auth = check.replace(user_id, '')
        await db.set_sudo(auth)
        await message.reply_text(card('removed from sudo chats', rows=[('id', str(user_id).strip())], icon='🗑'))
        return
    elif user_id in everyone:
        await message.reply_text(title_only('config sudo removal is not supported yet', '⚠️'))
        return
    else:
        await message.reply_text(title_only('chat is not sudo yet', '⚠️'))


async def reply_already_auth(message):
    if message.reply_to_message:
        await message.reply(text=title_only('they are already in auth users', 'ℹ️'))
        return
    elif not message.reply_to_message and len(message.command) != 1:
        await message.reply(text=title_only('they are already in auth users/groups', 'ℹ️'))
        return
    else:
        await message.reply(text=title_only('this chat is already in auth users/groups', 'ℹ️'))
        return


def get_id(message):
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    elif not message.reply_to_message and len(message.command) != 1:
        user_id = message.text.split(None, 1)[1]
    else:
        user_id = message.chat.id
    return user_id
