import os
import re
import time
import asyncio
import logging
from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from hydrogram.errors import MessageNotModified, FloodWait

from ..utils.database.access_db import db
from ..utils.encoding import get_media_streams, get_thumbnail, get_width_height, get_duration, extract_subs, _read_stderr, extract_ffmpeg_error
from ..utils.ffmpeg_builder import format_renamed_file, build_ffmpeg_command, sanitize_filename
from ..utils.helper import StyledButton
from ..utils.uploads import upload_worker
from ..utils.display_progress import TimeFormatter
from ..utils.ui import card, esc, sc, title_only
from .. import download_dir, encode_dir, LOGGER

# In-memory dictionary for active task sessions
# Key: (chat_id, message_id) -> session data
task_sessions = {}

# Active prompt listeners for rename/metadata input
# Key: (chat_id, user_id) -> dict(type='rename'|'meta_title'|'meta_author'|'meta_audio', session_key=(chat_id, msg_id))
active_prompts = {}


async def build_main_dashboard(user_id, session):
    cfg = session['config']
    filename = session['filename']
    res = cfg.get('resolution', 'OG')
    codec = "H.265 (HEVC)" if cfg.get('hevc') else "H.264 (AVC)"
    crf = cfg.get('crf', 22)
    preset = cfg.get('preset', 'sf')
    acodec = cfg.get('audio', 'aac').upper()
    rename_tmpl = cfg.get('rename_template', '{filename}')
    meta_title = cfg.get('metadata_title') or "Default"
    meta_author = cfg.get('metadata_author') or "Default"
    clear_meta = "ON" if cfg.get('clear_metadata') else "OFF"
    thumb_mode = cfg.get('thumb_mode', 'custom').upper()

    audio_map = session.get('audio_map', [])
    audio_count = len(audio_map) if audio_map is not None else "Default"

    text = card(
        "processing dashboard",
        rows=[
            ("file", filename),
            ("encoder", codec),
            ("resolution", res),
            ("crf", crf),
            ("preset", preset),
            ("pattern", rename_tmpl),
            ("title", meta_title),
            ("author", meta_author),
            ("thumb", thumb_mode),
            ("audio tracks", audio_count),
        ],
        icon="🎬",
        note="customize settings using the controls below",
    )

    buttons = [
        [
            StyledButton("ᴇɴᴄᴏᴅᴇ ꜱᴇᴛᴛɪɴɢꜱ", callback_data="p_menu_encode", style="primary"),
            StyledButton("ᴄᴏᴍᴘʀᴇꜱꜱ ꜰɪʟᴇ", callback_data="p_menu_compress", style="primary")
        ],
        [
            StyledButton("ʀᴇɴᴀᴍᴇ ꜰɪʟᴇ", callback_data="p_menu_rename", style="primary"),
            StyledButton("ᴄᴜꜱᴛᴏᴍ ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="p_menu_meta", style="primary")
        ],
        [
            StyledButton("ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="p_menu_thumb", style="primary"),
            StyledButton("ᴀᴜᴅɪᴏ/ꜱᴜʙ ꜱᴛʀᴇᴀᴍꜱ", callback_data="p_menu_streams", style="primary")
        ],
        [
            StyledButton("ꜱᴛᴀʀᴛ ᴘʀᴏᴄᴇꜱꜱɪɴɢ", callback_data="p_action_start", style="success")
        ],
        [
            StyledButton("ᴄᴀɴᴄᴇʟ ᴛᴀꜱᴋ", callback_data="p_action_cancel", style="danger")
        ]
    ]

    return text, InlineKeyboardMarkup(buttons)


async def start_direct_processing(client: Client, chat_id: int, message_id: int, user_id: int, filepath: str, status_msg: Message, override_res: str = None, override_crf: int = None):
    """
    Initializes session configuration from user DB defaults and immediately starts execution without showing per-file menu.
    """
    filename = os.path.basename(filepath)
    streams = get_media_streams(filepath)

    # Load user default preferences from MongoDB
    user_db = await db._get_user(user_id)
    config = {
        'hevc': user_db.get('hevc', False),
        'crf': override_crf if override_crf is not None else user_db.get('crf', 22),
        'preset': user_db.get('preset', 'sf'),
        'resolution': override_res if override_res else user_db.get('resolution', 'OG'),
        'frame': user_db.get('frame', 'source'),
        'tune': user_db.get('tune', False),
        'aspect': user_db.get('aspect', False),
        'bits': user_db.get('bits', False),
        'audio': user_db.get('audio', 'aac'),
        'sample': user_db.get('sample', 'source'),
        'bitrate': user_db.get('bitrate', 'source'),
        'channels': user_db.get('channels', 'source'),
        'watermark': user_db.get('watermark', False),
        'motion_watermark': user_db.get('motion_watermark', False),
        'hardsub': user_db.get('hardsub', False),
        'subtitles': user_db.get('subtitles', True),
        'extensions': user_db.get('extensions', 'MKV'),
        'rename_template': user_db.get('rename_template', '{filename}'),
        'metadata_title': user_db.get('metadata_title', ''),
        'metadata_author': user_db.get('metadata_author', ''),
        'metadata_audio_title': user_db.get('metadata_audio_title', ''),
        'metadata_sub_title': user_db.get('metadata_sub_title', ''),
        'clear_metadata': user_db.get('clear_metadata', False),
        'thumb_mode': user_db.get('thumb_mode', 'custom'),
    }

    # Extract original audio/subtitle stream indices
    audio_streams = [s['index'] for s in streams if s.get('codec_type') == 'audio']
    sub_streams = [s['index'] for s in streams if s.get('codec_type') == 'subtitle']

    config['has_subtitles'] = len(sub_streams) > 0

    session_key = (chat_id, status_msg.id)
    session = {
        'user_id': user_id,
        'filepath': filepath,
        'filename': filename,
        'streams': streams,
        'audio_streams': audio_streams,
        'sub_streams': sub_streams,
        'audio_map': audio_streams.copy() if audio_streams else None,
        'sub_map': sub_streams.copy() if sub_streams else None,
        'config': config,
        'status': 'processing'
    }
    task_sessions[session_key] = session

    try:
        await status_msg.edit_text(card("starting processing", rows=[("engine", "single-pass ffmpeg")], icon="🚀"))
    except Exception as e:
        LOGGER.error(f"Failed to edit status message panel: {e}")

    await execute_single_pass_task(client, status_msg, session, session_key)


async def show_processing_panel(client: Client, chat_id: int, message_id: int, user_id: int, filepath: str, status_msg: Message, override_res: str = None, override_crf: int = None):
    await start_direct_processing(client, chat_id, message_id, user_id, filepath, status_msg, override_res=override_res, override_crf=override_crf)


@Client.on_callback_query(filters.regex("^p_"))
async def panel_callback_handler(client: Client, cb: CallbackQuery):
    # Immediate answer to dismiss button spinner instantly
    try:
        await cb.answer()
    except Exception:
        pass

    data = cb.data
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    msg_id = cb.message.id
    session_key = (chat_id, msg_id)

    session = task_sessions.get(session_key)
    if not session:
        try:
            await cb.answer(sc("⚠️ session expired or invalid."), show_alert=True)
        except Exception:
            pass
        return

    if session['user_id'] != user_id:
        try:
            await cb.answer(sc("⛔ controlled by another user."), show_alert=True)
        except Exception:
            pass
        return

    # Clean active prompt if user clicks menu navigation buttons
    active_prompts.pop((chat_id, user_id), None)

    cfg = session['config']

    try:
        # --- MAIN DASHBOARD & MENUS ---
        if data == "p_menu_main":
            text, markup = await build_main_dashboard(user_id, session)
            await cb.message.edit_text(text, reply_markup=markup)

        # --- ENCODE SETTINGS MENU ---
        elif data == "p_menu_encode":
            codec_lbl = "H.265 (HEVC)" if cfg.get('hevc') else "H.264 (AVC)"
            res_lbl = cfg.get('resolution', 'OG')
            crf_val = cfg.get('crf', 22)
            preset_val = cfg.get('preset', 'sf')
            acodec_val = cfg.get('audio', 'aac').upper()

            text = card(
                "encoding settings",
                rows=[
                    ("codec", codec_lbl),
                    ("resolution", res_lbl),
                    ("crf quality", crf_val),
                    ("preset", preset_val),
                    ("audio codec", acodec_val),
                ],
                icon="🎬",
                note="lower crf = higher quality",
            )
            buttons = [
                [
                    StyledButton(f"ᴄᴏᴅᴇᴄ: {codec_lbl}", callback_data="p_set_codec", style="primary"),
                    StyledButton(f"ʀᴇꜱ: {res_lbl}", callback_data="p_set_res", style="primary")
                ],
                [
                    StyledButton("ᴄʀꜰ -1", callback_data="p_set_crf_down", style="primary"),
                    StyledButton(f"ᴄʀꜰ ({crf_val})", callback_data="p_set_crf_show", style="success"),
                    StyledButton("ᴄʀꜰ +1", callback_data="p_set_crf_up", style="primary")
                ],
                [
                    StyledButton(f"ᴘʀᴇꜱᴇᴛ: {preset_val}", callback_data="p_set_preset", style="primary"),
                    StyledButton(f"ᴀᴜᴅɪᴏ: {acodec_val}", callback_data="p_set_acodec", style="primary")
                ],
                [
                    StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɴᴇʟ", callback_data="p_menu_main", style="danger")
                ]
            ]
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await cb.answer()

        elif data == "p_set_codec":
            cfg['hevc'] = not cfg.get('hevc', False)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_encode', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_set_res":
            res_cycle = ['OG', '1080', '720', '576', '540', '480', '360']
            curr = str(cfg.get('resolution', 'OG'))
            idx = (res_cycle.index(curr) + 1) % len(res_cycle) if curr in res_cycle else 0
            cfg['resolution'] = res_cycle[idx]
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_encode', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        # --- COMPRESS FILE MENU ---
        elif data == "p_menu_compress":
            curr_res = str(cfg.get('resolution', 'OG'))
            curr_crf = cfg.get('crf', 22)
            curr_codec = "x265 (HEVC)" if cfg.get('hevc') else "x264 (AVC)"

            text = card(
                "compression engine",
                rows=[
                    ("target", f"{curr_res}p"),
                    ("crf quality", curr_crf),
                    ("encoder", curr_codec),
                ],
                icon="🗜",
                note="pick a resolution or compression mode below",
            )
            buttons = [
                [
                    StyledButton("360ᴘ", callback_data="p_comp_res_360", style="primary"),
                    StyledButton("480ᴘ", callback_data="p_comp_res_480", style="primary"),
                    StyledButton("540ᴘ", callback_data="p_comp_res_540", style="primary")
                ],
                [
                    StyledButton("576ᴘ", callback_data="p_comp_res_576", style="primary"),
                    StyledButton("720ᴘ", callback_data="p_comp_res_720", style="primary"),
                    StyledButton("1080ᴘ", callback_data="p_comp_res_1080", style="primary")
                ],
                [
                    StyledButton("ʜɪɢʜ ᴄᴏᴍᴘʀᴇꜱꜱ (x265 + ᴄʀꜰ 28)", callback_data="p_comp_preset_high", style="success"),
                    StyledButton("ʙᴀʟᴀɴᴄᴇᴅ (x265 + ᴄʀꜰ 24)", callback_data="p_comp_preset_bal", style="success")
                ],
                [
                    StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɴᴇʟ", callback_data="p_menu_main", style="danger")
                ]
            ]
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await cb.answer()

        elif data.startswith("p_comp_res_"):
            target_res = data.split("p_comp_res_")[1]
            cfg['resolution'] = target_res
            await cb.answer(sc(f"resolution set to {target_res}p!"), show_alert=True)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_compress', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_comp_preset_high":
            cfg['hevc'] = True
            cfg['crf'] = 28
            cfg['preset'] = 'sf'
            await cb.answer(sc("high compression enabled (x265, crf 28)!"), show_alert=True)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_compress', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_comp_preset_bal":
            cfg['hevc'] = True
            cfg['crf'] = 24
            cfg['preset'] = 'sf'
            await cb.answer(sc("balanced compression enabled (x265, crf 24)!"), show_alert=True)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_compress', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_set_crf_down":
            cfg['crf'] = max(14, cfg.get('crf', 22) - 1)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_encode', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_set_crf_up":
            cfg['crf'] = min(32, cfg.get('crf', 22) + 1)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_encode', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_set_crf_show":
            await cb.answer(sc(f"current crf: {cfg.get('crf', 22)}"), show_alert=True)

        elif data == "p_set_preset":
            presets = ['uf', 'sf', 'vf', 'f', 'm', 's']
            curr = cfg.get('preset', 'sf')
            idx = (presets.index(curr) + 1) % len(presets) if curr in presets else 0
            cfg['preset'] = presets[idx]
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_encode', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_set_acodec":
            acodecs = ['aac', 'dd', 'opus', 'copy', 'vorbis', 'alac']
            curr = cfg.get('audio', 'aac')
            idx = (acodecs.index(curr) + 1) % len(acodecs) if curr in acodecs else 0
            cfg['audio'] = acodecs[idx]
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_encode', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        # --- RENAME FILE MENU ---
        elif data == "p_menu_rename":
            rename_tmpl = cfg.get('rename_template', '{filename}')
            ext_val = cfg.get('extensions', 'MKV')
            text = card(
                "file renaming",
                rows=[
                    ("pattern", rename_tmpl),
                    ("extension", ext_val),
                ],
                icon="✏️",
                footer="\n".join([
                    f"<b>💡 {sc('placeholders')}</b>",
                    f"├ <code>{{filename}}</code> › {sc('original filename')}",
                    f"├ <code>{{resolution}}</code> › {sc('output resolution')}",
                    f"├ <code>{{codec}}</code> › {sc('video codec')}",
                    f"├ <code>{{quality}}</code> › {sc('crf quality')}",
                    f"╰ <code>{{ext}}</code> › {sc('target extension')}",
                ]),
            )
            buttons = [
                [
                    StyledButton("ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ɴᴀᴍᴇ / ᴘᴀᴛᴛᴇʀɴ", callback_data="p_prompt_rename", style="primary"),
                    StyledButton(f"ᴇxᴛ: {ext_val}", callback_data="p_set_ext", style="primary")
                ],
                [
                    StyledButton("ʀᴇꜱᴇᴛ ᴛᴏ ᴏʀɪɢɪɴᴀʟ ɴᴀᴍᴇ", callback_data="p_reset_rename", style="danger")
                ],
                [
                    StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɴᴇʟ", callback_data="p_menu_main", style="danger")
                ]
            ]
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await cb.answer()

        elif data == "p_set_ext":
            exts = ['MKV', 'MP4', 'AVI']
            curr = cfg.get('extensions', 'MKV')
            idx = (exts.index(curr) + 1) % len(exts)
            cfg['extensions'] = exts[idx]
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_rename', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_reset_rename":
            cfg['rename_template'] = '{filename}'
            await cb.answer(sc("renaming reset to original filename!"), show_alert=True)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_rename', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_prompt_rename":
            active_prompts[(chat_id, user_id)] = {'type': 'rename', 'session_key': session_key, 'msg_id': msg_id}
            await cb.message.edit_text(
                card("send your custom name or pattern", rows=[("example", "[MyBot] {filename} - {resolution}.{ext}")], icon="✏️"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="p_menu_rename", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif data == "p_prompt_meta_title":
            active_prompts[(chat_id, user_id)] = {'type': 'meta_title', 'session_key': session_key, 'msg_id': msg_id}
            await cb.message.edit_text(
                title_only("send your custom video title", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="p_menu_meta", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif data == "p_prompt_meta_author":
            active_prompts[(chat_id, user_id)] = {'type': 'meta_author', 'session_key': session_key, 'msg_id': msg_id}
            await cb.message.edit_text(
                title_only("send your custom author name / copyright", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="p_menu_meta", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif data == "p_prompt_meta_audio":
            active_prompts[(chat_id, user_id)] = {'type': 'meta_audio', 'session_key': session_key, 'msg_id': msg_id}
            await cb.message.edit_text(
                title_only("send your custom audio track title", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="p_menu_meta", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif data == "p_cancel_prompt":
            active_prompts.pop((chat_id, user_id), None)
            text, markup = await build_main_dashboard(user_id, session)
            try:
                await cb.message.edit_text(text, reply_markup=markup)
            except Exception:
                pass

        # --- CUSTOM METADATA MENU ---
        elif data == "p_menu_meta":
            title = cfg.get('metadata_title') or "Not Set"
            author = cfg.get('metadata_author') or "Not Set"
            audio_title = cfg.get('metadata_audio_title') or "Not Set"
            clear_flag = "ENABLED" if cfg.get('clear_metadata') else "DISABLED"

            text = card(
                "custom metadata",
                rows=[
                    ("video title", title),
                    ("author / copyright", author),
                    ("audio stream title", audio_title),
                    ("clear original metadata", clear_flag),
                ],
                icon="🏷",
            )
            buttons = [
                [
                    StyledButton("ꜱᴇᴛ ᴛɪᴛʟᴇ", callback_data="p_prompt_meta_title", style="primary"),
                    StyledButton("ꜱᴇᴛ ᴀᴜᴛʜᴏʀ", callback_data="p_prompt_meta_author", style="primary")
                ],
                [
                    StyledButton("ꜱᴇᴛ ᴀᴜᴅɪᴏ ɴᴀᴍᴇ", callback_data="p_prompt_meta_audio", style="primary"),
                    StyledButton(f"ᴄʟᴇᴀʀ ᴍᴇᴛᴀ: {clear_flag}", callback_data="p_toggle_clear_meta", style="success")
                ],
                [
                    StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɴᴇʟ", callback_data="p_menu_main", style="danger")
                ]
            ]
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await cb.answer()

        elif data == "p_toggle_clear_meta":
            cfg['clear_metadata'] = not cfg.get('clear_metadata', False)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_meta', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_prompt_meta_title":
            active_prompts[(chat_id, user_id)] = {'type': 'meta_title', 'session_key': session_key}
            await cb.answer(sc("reply with your custom video title."), show_alert=True)
            await cb.message.reply_text(
                title_only("send your custom video title", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ᴄᴀɴᴄᴇʟ ᴘʀᴏᴍᴘᴛ", callback_data="p_cancel_prompt", style="danger")]])
            )

        elif data == "p_prompt_meta_author":
            active_prompts[(chat_id, user_id)] = {'type': 'meta_author', 'session_key': session_key}
            await cb.answer(sc("reply with your custom author/copyright."), show_alert=True)
            await cb.message.reply_text(
                title_only("send your custom author name / copyright", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ᴄᴀɴᴄᴇʟ ᴘʀᴏᴍᴘᴛ", callback_data="p_cancel_prompt", style="danger")]])
            )

        elif data == "p_prompt_meta_audio":
            active_prompts[(chat_id, user_id)] = {'type': 'meta_audio', 'session_key': session_key}
            await cb.answer(sc("reply with your custom audio track title."), show_alert=True)
            await cb.message.reply_text(
                title_only("send your custom audio track title", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ᴄᴀɴᴄᴇʟ ᴘʀᴏᴍᴘᴛ", callback_data="p_cancel_prompt", style="danger")]])
            )

        # --- THUMBNAIL MENU ---
        elif data == "p_menu_thumb":
            mode = cfg.get('thumb_mode', 'custom')
            thumb_id = await db.get_thumbnail(user_id)
            thumb_status = "saved ✅" if thumb_id else "none saved ❌"

            text = card(
                "thumbnail settings",
                rows=[
                    ("current mode", mode.upper()),
                    ("saved custom thumb", thumb_status),
                ],
                icon="🖼",
                footer="\n".join([
                    f"<b>{sc('modes')}</b>",
                    f"├ <code>CUSTOM</code> › {sc('use your custom thumbnail')}",
                    f"├ <code>FRAME</code> › {sc('capture a frame from video')}",
                    f"├ <code>DEFAULT</code> › {sc('use default video cover')}",
                    f"╰ <code>NONE</code> › {sc('disable thumbnail')}",
                ]),
            )
            buttons = [
                [
                    StyledButton("ᴍᴏᴅᴇ: " + mode.upper(), callback_data="p_cycle_thumb_mode", style="primary")
                ],
                [
                    StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɴᴇʟ", callback_data="p_menu_main", style="danger")
                ]
            ]
            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await cb.answer()

        elif data == "p_cycle_thumb_mode":
            modes = ['custom', 'frame', 'default', 'none']
            curr = cfg.get('thumb_mode', 'custom')
            idx = (modes.index(curr) + 1) % len(modes)
            cfg['thumb_mode'] = modes[idx]
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_thumb', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        # --- STREAM SELECTOR MENU ---
        elif data == "p_menu_streams":
            audio_map = session.get('audio_map') or []
            audio_st = session.get('audio_streams') or []

            text = card(
                "audio & subtitle streams",
                rows=[
                    ("total audio streams", len(audio_st)),
                    ("mapped order", audio_map),
                ],
                icon="🔊",
                note="tap below to reverse or reset the audio order",
            )
            buttons = []
            if audio_st:
                buttons.append([StyledButton("ʀᴇᴠᴇʀꜱᴇ ᴀᴜᴅɪᴏ ꜱᴛʀᴇᴀᴍꜱ ᴏʀᴅᴇʀ", callback_data="p_stream_reverse_audio", style="primary")])
                buttons.append([StyledButton("ʀᴇꜱᴇᴛ ᴀᴜᴅɪᴏ ꜱᴛʀᴇᴀᴍꜱ", callback_data="p_stream_reset_audio", style="danger")])
            buttons.append([StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɴᴇʟ", callback_data="p_menu_main", style="danger")])

            await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            await cb.answer()

        elif data == "p_stream_reverse_audio":
            if session.get('audio_map'):
                session['audio_map'].reverse()
                await cb.answer(sc("audio streams order reversed!"), show_alert=True)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_streams', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        elif data == "p_stream_reset_audio":
            session['audio_map'] = session.get('audio_streams', []).copy()
            await cb.answer(sc("audio streams order reset to default!"), show_alert=True)
            await panel_callback_handler(client, type('CB', (), {'data': 'p_menu_streams', 'from_user': cb.from_user, 'message': cb.message, 'answer': cb.answer})())

        # --- ACTIONS: START & CANCEL ---
        elif data == "p_action_cancel":
            session['status'] = 'cancelled'
            proc = session.get('proc')
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            task_sessions.pop(session_key, None)
            try:
                await cb.answer(sc("task cancelled and process killed."), show_alert=True)
            except Exception:
                pass
            await cb.message.edit_text(card("task cancelled", rows=[("status", "process killed")], icon="❌"))

            # Cleanup input, output, thumb, and progress files immediately
            for p in [session.get('filepath'), session.get('output_filepath'), session.get('thumb_filepath'), session.get('progress_filepath')]:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

        elif data == "p_action_start":
            session['status'] = 'processing'
            await cb.answer(sc("🚀 starting single-pass ffmpeg execution!"), show_alert=False)
            await cb.message.edit_text(card("starting processing", rows=[("engine", "single-pass ffmpeg")], icon="🚀"))

            # Run background task execution
            asyncio.create_task(execute_single_pass_task(client, cb.message, session, session_key))

    except Exception as e:
        LOGGER.error(f"Error in panel_callback_handler: {e}", exc_info=True)
        try:
            await cb.answer(f"Error: {str(e)}", show_alert=True)
        except Exception:
            pass


@Client.on_message(filters.private & filters.text & ~filters.command([]), group=2)
async def prompt_text_handler(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    prompt_info = active_prompts.get((chat_id, user_id))

    if not prompt_info:
        return

    p_type = prompt_info['type']
    val = message.text.strip()
    session_key = prompt_info.get('session_key')
    msg_id = prompt_info.get('msg_id')

    # Try to delete user input message to keep chat clean
    try:
        await message.delete()
    except Exception:
        pass

    if p_type.startswith('s_'):
        if p_type == 's_rename':
            await db.set_rename_template(user_id, val)
        elif p_type == 's_meta_title':
            await db.set_metadata_title(user_id, val)
        elif p_type == 's_meta_author':
            await db.set_metadata_author(user_id, val)
        elif p_type == 's_meta_audio':
            await db.set_metadata_audio_title(user_id, val)
        elif p_type == 's_meta_sub':
            await db.set_metadata_sub_title(user_id, val)

        active_prompts.pop((chat_id, user_id), None)

        if msg_id:
            try:
                from ..utils.settings import RenameMetadataSettings
                async def _edit(text, reply_markup=None):
                    return await client.edit_message_text(chat_id, msg_id, text, reply_markup=reply_markup)
                dummy_msg = type('DummyMsg', (), {
                    'chat': type('Chat', (), {'id': chat_id})(),
                    'id': msg_id,
                    'edit': _edit,
                    'edit_text': _edit
                })()
                await RenameMetadataSettings(dummy_msg, user_id=user_id)
            except Exception as e:
                LOGGER.error(f"Failed to edit settings message: {e}")
        return

    session = task_sessions.get(session_key) if session_key else None
    if not session:
        active_prompts.pop((chat_id, user_id), None)
        return

    cfg = session['config']

    if p_type == 'rename':
        cfg['rename_template'] = val
        await db.set_rename_template(user_id, val)
    elif p_type == 'meta_title':
        cfg['metadata_title'] = val
        await db.set_metadata_title(user_id, val)
    elif p_type == 'meta_author':
        cfg['metadata_author'] = val
        await db.set_metadata_author(user_id, val)
    elif p_type == 'meta_audio':
        cfg['metadata_audio_title'] = val
        await db.set_metadata_audio_title(user_id, val)

    active_prompts.pop((chat_id, user_id), None)

    if msg_id:
        try:
            text, markup = await build_main_dashboard(user_id, session)
            await client.edit_message_text(chat_id, msg_id, text, reply_markup=markup)
        except Exception as e:
            LOGGER.error(f"Failed to edit panel message: {e}")


async def execute_single_pass_task(client: Client, status_msg: Message, session: dict, session_key: tuple):
    input_filepath = session.get('filepath')
    user_id = session.get('user_id')
    cfg = session.get('config', {})
    progress_file = None
    output_filepath = None
    thumb_filepath = None

    try:
        if not input_filepath or not os.path.exists(input_filepath):
            LOGGER.error(f"Input file missing or not found: {input_filepath}")
            await status_msg.edit_text(card("input file missing", rows=[("error", "file not found on server")], note="please resend the file command", icon="❌"))
            return

        # 1. Determine Output Filename and Path
        ext = cfg.get('extensions', 'MKV').lower()
        renamed_filename = format_renamed_file(
            original_filename=session['filename'],
            template=cfg.get('rename_template', '{filename}'),
            resolution=cfg.get('resolution', 'OG'),
            codec="HEVC" if cfg.get('hevc') else "H264",
            crf=cfg.get('crf', 22),
            extension=ext
        )

        output_filepath = os.path.join(encode_dir, renamed_filename)
        progress_file = os.path.join(download_dir, f"progress_{status_msg.id}.txt")
        with open(progress_file, 'w') as f:
            pass

        session['output_filepath'] = output_filepath
        session['progress_filepath'] = progress_file

        # 2. Handle Thumbnail
        thumb_mode = cfg.get('thumb_mode', 'custom')

        if thumb_mode == 'custom':
            thumb_file_id = await db.get_thumbnail(user_id)
            if thumb_file_id:
                try:
                    thumb_filepath = await client.download_media(thumb_file_id, file_name=os.path.join(encode_dir, f"thumb_{status_msg.id}.jpg"))
                except Exception as e:
                    LOGGER.error(f"Failed to download user custom thumbnail: {e}")
        elif thumb_mode == 'frame':
            duration = get_duration(input_filepath)
            ttl = max(1, int(duration / 2)) if duration else 5
            frame_path = get_thumbnail(input_filepath, encode_dir, ttl)
            if frame_path:
                thumb_filepath = frame_path

        if thumb_filepath:
            thumb_filepath = str(thumb_filepath)
            cfg['thumb_filepath'] = thumb_filepath
            session['thumb_filepath'] = thumb_filepath

        # Handle Hardsub extraction if enabled
        if cfg.get('hardsub', False):
            try:
                sub_path = await extract_subs(input_filepath, status_msg, user_id)
                if sub_path and os.path.exists(sub_path):
                    cfg['subtitles_path'] = sub_path
            except Exception as e:
                LOGGER.error(f"Error extracting hardsub subtitles: {e}")

        # Add stream maps and probed streams to config
        if session.get('streams'):
            cfg['streams'] = session['streams']
        if session.get('audio_map'):
            cfg['audio_map'] = session['audio_map']
        if session.get('sub_map'):
            cfg['sub_map'] = session['sub_map']

        # 3. Build Single-Pass FFmpeg Command
        cmd = build_ffmpeg_command(input_filepath, output_filepath, progress_file, cfg)
        LOGGER.info(f"Executing Single-Pass FFmpeg Command: {' '.join(cmd)}")

        start_time = time.time()
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        session['proc'] = proc

        stderr_lines = []
        drain_task = asyncio.create_task(_read_stderr(proc, stderr_lines))

        # 4. Live Monitoring Task with Rate-limiting
        last_edit_time = 0

        while proc.returncode is None:
            if session.get('status') == 'cancelled':
                try:
                    proc.kill()
                except Exception:
                    pass
                break
            await asyncio.sleep(3)
            if not os.path.exists(progress_file):
                continue

            try:
                with open(progress_file, 'r') as f:
                    content = f.read()
                out_time_ms = re.findall(r"out_time_ms=(\d+)", content)
                speed_match = re.findall(r"speed=(\d+\.?\d*)", content)

                if out_time_ms:
                    elapsed_sec = int(out_time_ms[-1]) / 1000000
                    total_duration = get_duration(input_filepath) or 1
                    percent = min(100, max(0, int((elapsed_sec / total_duration) * 100)))
                    speed = speed_match[-1] if speed_match else "1"

                    now = time.time()
                    if now - last_edit_time >= 3.5:
                        last_edit_time = now
                        try:
                            speed_f = float(speed)
                        except ValueError:
                            speed_f = 0
                        eta_s = int((total_duration - elapsed_sec) / speed_f) if speed_f > 0 else 0
                        p_text = card(
                            "processing your video",
                            rows=[
                                ("speed", f"{speed}x"),
                                ("elapsed", TimeFormatter(now - start_time) or "0s"),
                                ("eta", TimeFormatter(eta_s) if eta_s > 0 else "-"),
                            ],
                            percent=percent,
                            icon="🚀",
                        )
                        try:
                            await status_msg.edit_text(
                                p_text,
                                reply_markup=InlineKeyboardMarkup([[StyledButton("ᴄᴀɴᴄᴇʟ ᴛᴀꜱᴋ", callback_data="p_action_cancel", style="danger")]])
                            )
                        except (MessageNotModified, FloodWait):
                            pass
            except Exception as e:
                LOGGER.error(f"Error reading progress file: {e}")

        await proc.wait()
        await drain_task

        if proc.returncode != 0 and proc.returncode != -9:
            err_msg = extract_ffmpeg_error(stderr_lines)
            LOGGER.error(f"FFmpeg process failed with return code {proc.returncode}: {err_msg}")
            await status_msg.edit_text(card("processing failed", rows=[("ffmpeg", err_msg)], icon="❌"))
            return
        elif proc.returncode == -9:
            # Task was killed/cancelled
            return

        # 5. Uploading Output
        await status_msg.edit_text(card("processing finished", rows=[("status", "uploading file")], icon="⬆️"))
        try:
            class UserCtxMsg:
                def __init__(self, msg, uid):
                    self._msg = msg
                    self.from_user = type('User', (), {'id': uid})()
                def __getattr__(self, item):
                    return getattr(self._msg, item)

            user_msg = UserCtxMsg(status_msg, user_id)
            link = await upload_worker(output_filepath, user_msg, status_msg)
            await status_msg.edit_text(
                card("processing completed",
                     rows=[("file", os.path.basename(output_filepath)),
                           ("link", f"<a href='{link}'>{sc('open file')}</a>", True)],
                     icon="✅"),
                disable_web_page_preview=True)
        except Exception as e:
            LOGGER.error(f"Upload failed: {e}")
            await status_msg.edit_text(card("upload failed", rows=[("reason", e)], note="processing finished successfully", icon="⚠️"))

    except Exception as e:
        LOGGER.error(f"Unhandled error in execute_single_pass_task: {e}", exc_info=True)
        try:
            await status_msg.edit_text(card("processing error", rows=[("reason", e)], icon="❌"))
        except Exception:
            pass
    finally:
        # 6. Cleanup Temporary Files
        for p in [input_filepath, output_filepath, progress_file, thumb_filepath]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        task_sessions.pop(session_key, None)
        try:
            from ..utils.tasks import on_task_complete
            await on_task_complete()
        except Exception as e:
            LOGGER.error(f"Error calling on_task_complete in execute_single_pass_task: {e}")
