

import asyncio
import html
import os
import re
import shutil
import time
import requests
import urllib.parse
from datetime import datetime
from urllib.parse import unquote_plus

from httpx import delete
from hydrogram.errors.exceptions.bad_request_400 import (MessageIdInvalid,
                                                        MessageNotModified)
from hydrogram.parser import html as hydrogram_html
from hydrogram.types import Message
from requests.utils import unquote

from .. import LOGGER, data, download_dir, video_mimetype
from .database.access_db import db
from .direct_link_generator import direct_link_generator
from .display_progress import progress_for_hydrogram
from .helper import delete_downloads, get_zip_folder, handle_encode, handle_extract, handle_url
from .ui import card, esc, sc, title_only
from .uploads.drive import _get_file_id
from .uploads.drive.download import Downloader
from .encoding import get_media_streams
from .ffmpeg_builder import sanitize_filename
from ..video_utils.audio_selector import AudioSelect
from ..plugins.panel import show_processing_panel, start_direct_processing

MAX_CONCURRENT_TASKS = 3
active_tasks_count = 0

async def on_task_complete():
    try:
        delete_downloads()
    except Exception as e:
        LOGGER.error(f"Error in delete_downloads: {e}")
    await start_next_tasks()

async def start_next_tasks():
    global active_tasks_count
    while active_tasks_count < MAX_CONCURRENT_TASKS and data:
        next_msg = None
        for msg in list(data):
            if not getattr(msg, '_is_active', False):
                next_msg = msg
                break
        if not next_msg:
            break

        next_msg._is_active = True
        active_tasks_count += 1

        text_content = next_msg.text or next_msg.caption or ""
        cmd = text_content.split()[0].lower() if text_content else ""
        if '/fetch' in cmd or '/ddl' in cmd:
            mode = 'url'
        elif '/batch' in cmd:
            mode = 'batch'
        elif '/af' in cmd:
            mode = 'af'
        else:
            mode = 'tg'

        asyncio.create_task(run_task_runner(next_msg, mode))

async def run_task_runner(message, mode):
    global active_tasks_count
    try:
        await handle_tasks(message, mode)
    except Exception as e:
        LOGGER.error(f"Error in run_task_runner: {e}", exc_info=True)
    finally:
        if message in data:
            data.remove(message)
        active_tasks_count = max(0, active_tasks_count - 1)
        await on_task_complete()


async def handle_tasks(message, mode):
    try:
        msg = await message.reply_text(card("starting download", rows=[("status", "preparing your file")], icon="💠"))
        if mode == 'tg':
            await tg_task(message, msg)
        elif mode == 'url':
            await url_task(message, msg)
        elif mode == 'af':
            await af_task(message, msg)
        else:
            await batch_task(message, msg)
    except MessageNotModified:
        pass
    except IndexError:
        return
    except MessageIdInvalid:
        await msg.edit(title_only('download cancelled', '🚫'))
    except FileNotFoundError:
        LOGGER.error('[FileNotFoundError]: Maybe due to cancel, hmm')
        import traceback
        LOGGER.error(traceback.format_exc())
    except Exception as e:
        import traceback
        LOGGER.error(traceback.format_exc())
        await message.reply(text=card("something went wrong", rows=[("error", e)], icon="❌"))


async def tg_task(message, msg):
    filepath = await handle_tg_down(message, msg)
    if not filepath:
        await msg.edit(title_only("download failed or no file found", "❌"))
        return

    raw_text = message.text or message.caption or ""
    cmd_res = None
    for res in ['360p', '480p', '540p', '576p', '720p', '1080p']:
        if res in raw_text.lower():
            cmd_res = res.replace('p', '')
            break

    override_crf = None
    crf_match = re.search(r'-crf\s*(\d+)', raw_text, re.IGNORECASE)
    if crf_match:
        try:
            override_crf = int(crf_match.group(1))
        except ValueError:
            pass

    await start_direct_processing(message._client, message.chat.id, msg.id, message.from_user.id, filepath, msg, override_res=cmd_res, override_crf=override_crf)


async def af_task(message, msg):
    filepath = await handle_tg_down(message, msg)
    if not filepath:
        await msg.edit(title_only("download failed or no file found", "❌"))
        return

    # Probe for streams
    streams = get_media_streams(filepath)
    if not streams:
         await msg.edit(title_only("could not read media streams", "❌"))
         return

    selector = AudioSelect(message._client, message)
    await msg.delete() # Delete the downloading message as AudioSelect will send its own interface

    # AudioSelect expects streams list
    audio_map, _ = await selector.get_buttons(streams)

    if audio_map == -1:
        # Cancelled or error
        return

    # Proceed to encode with the new map
    msg = await message.reply(title_only("encoding with new audio order", "🔊"))
    await handle_encode(filepath, message, msg, audio_map)


async def url_task(message, msg):
    filepath = await handle_download_url(message, msg, False)
    if not filepath:
        # Error handled in handle_download_url logic or implicit failure
        return

    raw_text = message.text or message.caption or ""
    cmd_res = None
    for res in ['360p', '480p', '540p', '576p', '720p', '1080p']:
        if res in raw_text.lower():
            cmd_res = res.replace('p', '')
            break

    override_crf = None
    crf_match = re.search(r'-crf\s*(\d+)', raw_text, re.IGNORECASE)
    if crf_match:
        try:
            override_crf = int(crf_match.group(1))
        except ValueError:
            pass

    await start_direct_processing(message._client, message.chat.id, msg.id, message.from_user.id, filepath, msg, override_res=cmd_res, override_crf=override_crf)


async def batch_task(message, msg):
    if message.reply_to_message:
        filepath = await handle_tg_down(message, msg, mode='reply')
    else:
        filepath = await handle_download_url(message, msg, True)
    if not filepath:
        await msg.edit(title_only('no archive found', '❌'))
    if os.path.isfile(filepath):
        path = await get_zip_folder(filepath)
        await handle_extract(filepath)
        if not os.path.isdir(path):
            await msg.edit(title_only('extraction failed', '❌'))
            return
        filepath = path
    if os.path.isdir(filepath):
        path = filepath
    else:
        await msg.edit(title_only('something went wrong', '❌'))
        return
    await msg.edit(title_only('batch encode started', '📕'))
    sentfiles = []
    # Encode
    for dirpath, subdir, files_ in sorted(os.walk(path)):
        for i in sorted(files_):
            msg_ = await message.reply(title_only('queued for encoding', '⏳'))
            filepath = os.path.join(dirpath, i)
            await msg.edit(card('batch encode running', rows=[('current', i)], icon='📕'))
            try:
                url = await handle_encode(filepath, message, msg_)
            except Exception as e:
                await msg_.edit(card('file skipped', rows=[('reason', e)], note='continuing with the next file', icon='⚠️'))
                continue
            else:
                sentfiles.append((i, url))
    text = title_only('encoded files', '✨') + '\n'
    quote = None
    first_index = None
    all_amount = 1
    for filename, filelink in sentfiles:
        if filelink:
            atext = f'├ <a href="{filelink}">{html.escape(filename)}</a>'
        else:
            atext = f'├ {html.escape(filename)} ' + sc('(empty)')
        atext += '\n'
        futtext = text + atext
        if all_amount > 100:
            thing = await message.reply_text(text, quote=quote, disable_web_page_preview=True)
            if first_index is None:
                first_index = thing
            quote = False
            futtext = atext
            all_amount = 1
            await asyncio.sleep(3)
        all_amount += 1
        text = futtext
    if not sentfiles:
        text = title_only('no files were encoded', '📭')
    thing = await message.reply_text(text, quote=quote, disable_web_page_preview=True)
    if first_index is None:
        first_index = thing
    await msg.edit(card('batch finished', rows=[('links', f"<a href='{first_index.link}'>{sc('open list')}</a>", True)], icon='✅'), disable_web_page_preview=True)


async def _read_stream_lines(stream, output_list):
    if not stream:
        return
    while True:
        line = await stream.readline()
        if not line:
            break
        decoded = line.decode('utf-8', errors='ignore').strip()
        if decoded:
            output_list.append(decoded)


async def handle_torrent_download(url, download_dir, msg):
    if not shutil.which('aria2c'):
        await msg.edit(card("aria2c missing", rows=[("error", "aria2c is not installed on the system")], icon="❌"))
        LOGGER.error("aria2c binary not found on system path.")
        return None

    await msg.edit(card("torrent download", rows=[("status", "connecting to peers")], icon="🧲"))

    trackers = ",".join([
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://open.demonii.com:1337/announce",
        "udp://open.stealth.si:80/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.coppersurfer.tk:6969/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.cyberia.is:6969/announce",
        "udp://tracker.tiny-vps.com:6969/announce",
        "udp://open.stealth.si:1096/announce"
    ])

    cmd = [
        'aria2c',
        '--dir', download_dir,
        '--seed-time=0',
        '--summary-interval=1',
        '--console-log-level=warn',
        '--max-connection-per-server=16',
        '--split=16',
        '--min-split-size=1M',
        '--max-concurrent-downloads=5',
        '--enable-dht=true',
        '--enable-dht6=true',
        '--bt-enable-lpd=true',
        '--enable-peer-exchange=true',
        '--bt-seed-unverified=true',
        '--follow-torrent=mem',
        '--allow-overwrite=true',
        '--bt-stop-timeout=600',
        '--bt-tracker=' + trackers,
        url
    ]
    stdout_lines = []
    stderr_lines = []
    try:
        proc = await asyncio.create_subprocess_exec(
            *[str(x) for x in cmd],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        read_stdout_task = asyncio.create_task(_read_stream_lines(proc.stdout, stdout_lines))
        read_stderr_task = asyncio.create_task(_read_stream_lines(proc.stderr, stderr_lines))

        last_edit = 0
        while proc.returncode is None:
            try:
                await asyncio.wait_for(asyncio.shield(proc.wait()), timeout=5.0)
            except asyncio.TimeoutError:
                now = time.time()
                if now - last_edit >= 5.0:
                    last_edit = now
                    try:
                        await msg.edit(card("torrent download", rows=[("status", "fetching content via aria2")], icon="🧲"))
                    except Exception:
                        pass

        await asyncio.gather(read_stdout_task, read_stderr_task, return_exceptions=True)
    except Exception as e:
        LOGGER.error(f"Torrent process execution error: {e}", exc_info=True)
        await msg.edit(card("torrent download failed", rows=[("error", str(e))], icon="❌"))
        return None

    if proc.returncode != 0:
        err_output = "\n".join(stderr_lines or stdout_lines) or f"aria2c exited with return code {proc.returncode}"
        LOGGER.error(f"Torrent download failed (code {proc.returncode}): {err_output}")
        await msg.edit(card("torrent download failed", rows=[("code", proc.returncode), ("error", err_output[-1000:])], icon="❌"))
        return None

    # Find the largest downloaded file in download_dir
    files = []
    for root, _, filenames in os.walk(download_dir):
        for f in filenames:
            fp = os.path.join(root, f)
            if not f.endswith('.aria2') and not f.endswith('.torrent') and os.path.isfile(fp):
                files.append((os.path.getsize(fp), fp))
    if files:
        files.sort(key=lambda x: x[0], reverse=True)
        return files[0][1]

    err_output = "\n".join(stderr_lines or stdout_lines) or "No valid media files found in torrent"
    LOGGER.error(f"Torrent download completed but no valid files found: {err_output}")
    await msg.edit(card("torrent download failed", rows=[("error", err_output[-1000:])], icon="❌"))
    return None


def get_url_filename(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        path = unquote_plus(parsed.path)
        base = os.path.basename(path)
        if base and '.' in base and not base.startswith('.'):
            return sanitize_filename(base)

        r = requests.head(url, allow_redirects=True, timeout=5)
        cd = r.headers.get('content-disposition', '')
        if cd:
            filenames = re.findall(r'filename\*?=(?:["\']?([^"\';]+)["\']?|UTF-8\'\'(.+))', cd, flags=re.IGNORECASE)
            if filenames:
                fname = filenames[0][0] or filenames[0][1]
                if fname:
                    return sanitize_filename(unquote_plus(fname))
    except Exception as e:
        LOGGER.warning(f"Error auto-detecting URL filename: {e}")

    return sanitize_filename(unquote_plus(os.path.basename(url)) or "downloaded_video.mp4")


async def handle_download_url(message, msg, batch):
    raw_text = message.text.split(None, 1)[1].strip() if len(message.text.split()) > 1 else ""

    custom_file_name = None
    if "|" in raw_text and not batch:
        parts = raw_text.split("|", maxsplit=1)
        url = parts[0].strip()
        custom_file_name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    else:
        url = raw_text.strip()

    if url.startswith('magnet:') or url.endswith('.torrent') or '.torrent?' in url:
        filepath = await handle_torrent_download(url, download_dir, msg)
        return filepath

    direct = direct_link_generator(url)
    if direct:
        url = direct

    if 'drive.google.com' in url:
        file_id = _get_file_id(url)
        n = Downloader()
        if not custom_file_name:
            custom_file_name = n.name(file_id)
        path = os.path.join(download_dir, custom_file_name)
        await n.handle_drive(msg, url, custom_file_name, batch)
        return path

    if not custom_file_name:
        custom_file_name = await asyncio.to_thread(get_url_filename, url)

    path = os.path.join(download_dir, custom_file_name)
    filepath = path
    await handle_url(url, filepath, msg)
    return filepath


async def handle_tg_down(message, msg, mode='no_reply'):
    c_time = time.time()

    # Determine what to download
    target_msg = message
    if message.reply_to_message and (message.reply_to_message.video or message.reply_to_message.document):
        target_msg = message.reply_to_message
    elif message.video or message.document:
        target_msg = message
    elif mode == 'reply' and message.reply_to_message:
        target_msg = message.reply_to_message
    else:
        # If command was just /dl without reply and without attachment, and mode is not explicit reply
        if not (message.reply_to_message and (message.reply_to_message.video or message.reply_to_message.document)):
             return None
        target_msg = message.reply_to_message

    path = await target_msg.download(
        file_name=os.path.join(download_dir, ""),
        progress=progress_for_hydrogram,
        progress_args=("Downloading", msg, c_time))

    return path
