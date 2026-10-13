
import dns.resolver
from hydrogram import idle
from hydrogram.types import BotCommand

from . import app, log

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = [
    '8.8.8.8']  # this is a google public dns


async def main():
    await app.start()
    try:
        commands = [
    BotCommand("start", "⚡ ᴄʜᴇᴄᴋ ʙᴏᴛ ᴀʟɪᴠᴇ ꜱᴛᴀᴛᴜꜱ"),
    BotCommand("help", "✨ ᴅɪꜱᴘʟᴀʏ ʜᴇʟᴘ ᴍᴇɴᴜ & ᴄᴏᴍᴍᴀɴᴅꜱ"),
    BotCommand("status", "🔥 ᴠɪᴇᴡ ꜱᴇʀᴠᴇʀ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ & ᴀᴄᴛɪᴠᴇ ᴛᴀꜱᴋꜱ"),
    BotCommand("fetch", "🌐 ᴅᴏᴡɴʟᴏᴀᴅ & ᴇɴᴄᴏᴅᴇ ᴜʀʟ / ᴛᴏʀʀᴇɴᴛ"),
    BotCommand("batch", "📦 ʙᴀᴛᴄʜ ᴇɴᴄᴏᴅᴇ ᴍᴜʟᴛɪᴘʟᴇ ʟɪɴᴋꜱ"),
    BotCommand("queue", "📋 ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ ᴛᴀꜱᴋ ǫᴜᴇᴜᴇ"),
    BotCommand("clear", "🗑 ᴄʟᴇᴀʀ ᴘʀᴏᴄᴇꜱ%ɪɴɢ ǫᴜᴇᴜᴇ"),
    BotCommand("360p", "⚡ ᴇɴᴄᴏᴅᴇ ᴠɪᴅᴇᴏ ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ 360ᴘ"),
    BotCommand("480p", "⚡ ᴇɴᴄᴏᴅᴇ ᴠɪᴅᴇᴏ ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ 480ᴘ"),
    BotCommand("540p", "⚡ ᴇɴᴄᴏᴅᴇ ᴠɪᴅᴇᴏ ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ 540ᴘ"),
    BotCommand("576p", "⚡ ᴇɴᴄᴏᴅᴇ ᴠɪᴅᴇᴏ ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ 576ᴘ"),
    BotCommand("720p", "⚡ ᴇɴᴄᴏᴅᴇ ᴠɪᴅᴇᴏ ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ 720ᴘ"),
    BotCommand("1080p", "⚡ ᴇɴᴄᴏᴅᴇ ᴠɪᴅᴇᴏ ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ 1080p"),
    BotCommand("settings", "⚙️ ᴍᴀɴᴀɢᴇ ᴇɴᴄᴏᴅɪɴɢ & ʀᴇɴᴀᴍᴇ ꜱᴇᴛᴛɪɴɢꜱ"),
    BotCommand("af", "🔊 ᴀᴜᴅɪᴏ ꜱᴛʀᴇᴀᴍ & ʟᴀɴɢᴜᴀɢᴇ ꜱᴇʟᴇᴄᴛᴏʀ"),
    BotCommand("setthumb", "🖼 ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ"),
    BotCommand("viewthumb", "👁 ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ"),
    BotCommand("delthumb", "🗑 ᴅᴇʟᴇᴛᴇ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ"),
    BotCommand("clean", "🧹 ᴄʟᴇᴀʀ ᴛᴇᴍᴘᴏʀᴀʀʏ ᴊᴜɴᴋ ꜰɪʟᴇꜱ"),
    BotCommand("update", "📶 ᴘᴜʟʟ ʟᴀᴛᴇꜱᴛ ʙᴏᴛ ᴜᴘᴅᴀᴛᴇꜱ"),
    BotCommand("restart", "🔄 ʀᴇʙᴏᴏᴛ ᴛʜᴇ ʙᴏᴛ ᴇɴɢɪɴᴇ")
]

        await app.set_bot_commands(commands)
    except Exception as e:
        pass
    await app.send_message(chat_id=log, text=f'<b>Bot Started! @{(await app.get_me()).username}</b>')
    await idle()
    await app.stop()

app.loop.run_until_complete(main())
