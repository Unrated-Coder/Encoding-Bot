

import asyncio

from hydrogram.errors import FloodWait, MessageNotModified
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import LOGGER
from .database.access_db import db
from .database.add_user import AddUserToDatabase
from .helper import StyledButton
from .ui import card, esc, sc, title_only


# Settings
async def OpenSettings(event: Message, user_id: int):
    try:
        await event.edit(
            text=card("video encoder settings", note="choose what you want to configure for your files", icon="⚙️"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [StyledButton("ᴠɪᴅᴇᴏ ꜱᴇᴛᴛɪɴɢꜱ", callback_data="VideoSettings", style="primary"), StyledButton(
                        "ᴀᴜᴅɪᴏ ꜱᴇᴛᴛɪɴɢꜱ", callback_data="AudioSettings", style="primary")],
                    [StyledButton("ʀᴇɴᴀᴍᴇ & ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="RenameMetadataSettings", style="primary"),
                     StyledButton("ᴇxᴛʀᴀ ꜱᴇᴛᴛɪɴɢꜱ", callback_data="ExtraSettings", style="primary")],
                    [StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]
                ]
            )
        )
    except FloodWait as e:
        await asyncio.sleep(e.x)
        await OpenSettings(event, user_id)
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER.error(f"Error in OpenSettings: {e}")
        try:
            await event.edit(card("settings error", rows=[("menu", "OpenSettings"), ("error", e)], icon="❌"))
        except:
            pass


# Video Settings
async def VideoSettings(event: Message, user_id: int):
    try:
        ex = await db.get_extensions(user_id)
        if ex == 'MP4':
            extensions = 'MP4'
        elif ex == 'MKV':
            extensions = 'MKV'
        elif ex == 'AVI':
            extensions = 'AVI'
        else:
            extensions = 'MP4'

        fr = await db.get_frame(user_id)
        if fr == 'ntsc':
            frame = 'NTSC'
        elif fr == 'pal':
            frame = 'PAL'
        elif fr == 'film':
            frame = 'FILM'
        elif fr == '23.976':
            frame = '23.976'
        elif fr == '30':
            frame = '30'
        elif fr == '60':
            frame = '60'
        elif fr == 'source':
            frame = 'Source'
        else:
            frame = 'Source'

        p = await db.get_preset(user_id)
        if p == 'uf':
            pre = 'UltraFast'
        elif p == 'sf':
            pre = 'SuperFast'
        elif p == 'vf':
            pre = 'VeryFast'
        elif p == 'f':
            pre = 'Fast'
        elif p == 'm':
            pre = 'Medium'
        elif p == 's':
            pre = 'Slow'
        else:
            pre = 'None'

        crf = await db.get_crf(user_id)

        r = await db.get_resolution(user_id)
        if r == 'OG':
            res = 'Source'
        elif r == '1080':
            res = '1080p'
        elif r == '720':
            res = '720p'
        elif r == '576':
            res = '576p'
        elif r == '480':
            res = '480p'
        else:
            res = 'Source'

        # Reframe
        rf = await db.get_reframe(user_id)
        if rf == '4':
            reframe = '4'
        elif rf == '8':
            reframe = '8'
        elif rf == '16':
            reframe = '16'
        elif rf == 'pass':
            reframe = 'Pass'
        else:
            reframe = 'Pass'

        fr = await db.get_frame(user_id)
        if fr == 'ntsc':
            frame = 'NTSC'
        elif fr == 'pal':
            frame = 'PAL'
        elif fr == 'film':
            frame = 'FILM'
        elif fr == '23.976':
            frame = '23.976'
        elif fr == '30':
            frame = '30'
        elif fr == '60':
            frame = '60'
        elif fr == 'source':
            frame = 'Source'
        else:
            frame = 'Source'

        await event.edit(
            text=card("video settings", note="tap any option to change it", icon="🎬"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [StyledButton("ʙᴀꜱɪᴄ ᴠɪᴅᴇᴏ ᴏᴘᴛɪᴏɴꜱ", callback_data="Watermark", style="primary")],
                    [StyledButton(f"ᴇxᴛ: {extensions}", callback_data="triggerextensions", style="primary"),
                     StyledButton(f"ʙɪᴛꜱ: {'10' if ((await db.get_bits(user_id)) is True) else '8'}", callback_data="triggerBits", style="primary")],
                    [StyledButton(f"ᴄᴏᴅᴇᴄ: {'ʜ265' if ((await db.get_hevc(user_id)) is True) else 'ʜ264'}", callback_data="triggerHevc", style="primary"),
                     StyledButton(f"ᴄʀꜰ: {crf}", callback_data="triggerCRF", style="primary")],
                    [StyledButton(f"ʀᴇꜱ: {res}", callback_data="triggerResolution", style="primary"),
                     StyledButton(f"ᴛᴜɴᴇ: {'ᴀɴɪᴍᴀᴛɪᴏɴ' if ((await db.get_tune(user_id)) is True) else 'ꜰɪʟᴍ'}", callback_data="triggertune", style="primary")],
                    [StyledButton("ǫᴜɪᴄᴋ ᴄᴏᴍᴘʀᴇꜱꜱɪᴏɴ ᴘʀᴇꜱᴇᴛꜱ", callback_data="Watermark", style="primary")],
                    [StyledButton("🗜 ʜɪɢʜ (x265 ᴄʀꜰ28)", callback_data="triggerCompHigh", style="primary"),
                     StyledButton("🗜 ʙᴀʟᴀɴᴄᴇᴅ (x265 ᴄʀꜰ24)", callback_data="triggerCompBal", style="primary")],
                    [StyledButton("ᴀᴅᴠᴀɴᴄᴇᴅ ᴠɪᴅᴇᴏ ᴏᴘᴛɪᴏɴꜱ", callback_data="Watermark", style="primary")],
                    [StyledButton(f"ᴘʀᴇꜱᴇᴛ: {pre}", callback_data="triggerPreset", style="primary"),
                     StyledButton(f"ꜰᴘꜱ: {frame}", callback_data="triggerframe", style="primary")],
                    [StyledButton(f"ᴀꜱᴘᴇᴄᴛ: {'16:9' if ((await db.get_aspect(user_id)) is True) else 'ꜱᴏᴜʀᴄᴇ'}", callback_data="triggeraspect", style="primary"),
                     StyledButton(f"ʀᴇꜰʀᴀᴍᴇ: {reframe}", callback_data="triggerreframe", style="primary")],
                    [StyledButton(f"ᴄᴀʙᴀᴄ {'☑️' if ((await db.get_cabac(user_id)) is True) else ''}", callback_data="triggercabac", style="success")],
                    [StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="OpenSettings", style="danger")]
                ]
            )
        )
    except FloodWait as e:
        await asyncio.sleep(e.x)
        await VideoSettings(event, user_id)
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER.error(f"Error in VideoSettings: {e}")
        try:
            await event.edit(card("settings error", rows=[("menu", "VideoSettings"), ("error", e)], icon="❌"))
        except:
            pass


async def AudioSettings(event: Message, user_id: int):
    try:

        a = await db.get_audio(user_id)
        if a == 'dd':
            audio = 'AC3'
        elif a == 'aac':
            audio = 'AAC'
        elif a == 'opus':
            audio = 'OPUS'
        elif a == 'vorbis':
            audio = 'VORBIS'
        elif a == 'alac':
            audio = 'ALAC'
        elif a == 'copy':
            audio = 'Source'
        else:
            audio = 'None'

        bit = await db.get_bitrate(user_id)
        if bit == '400':
            bitrate = '400k'
        elif bit == '320':
            bitrate = '320k'
        elif bit == '256':
            bitrate = '256k'
        elif bit == '224':
            bitrate = '224k'
        elif bit == '192':
            bitrate = '192k'
        elif bit == '160':
            bitrate = '160k'
        elif bit == '128':
            bitrate = '128k'
        elif bit == 'source':
            bitrate = 'Source'
        else:
            bitrate = 'Source'

        sr = await db.get_samplerate(user_id)
        if sr == '44.1K':
            sample = '44.1kHz'
        elif sr == '48K':
            sample = '48kHz'
        elif sr == 'source':
            sample = 'Source'
        else:
            sample = 'Source'

        c = await db.get_channels(user_id)
        if c == '1.0':
            channels = 'Mono'
        elif c == '2.0':
            channels = 'Stereo'
        elif c == '2.1':
            channels = '2.1'
        elif c == '5.1':
            channels = '5.1'
        elif c == '7.1':
            channels = '7.1'
        elif c == 'source':
            channels = 'Source'
        else:
            channels = 'Source'

        await event.edit(
            text=card("audio settings", note="tap any option to change it", icon="🔊"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [StyledButton(f"ᴄᴏᴅᴇᴄ: {audio}", callback_data="triggerAudioCodec", style="primary"),
                     StyledButton(f"ᴄʜᴀɴɴᴇʟꜱ: {channels}", callback_data="triggerAudioChannels", style="primary")],
                    [StyledButton(f"ꜱᴀᴍᴘʟᴇ: {sample}", callback_data="triggersamplerate", style="primary"),
                     StyledButton(f"ʙɪᴛʀᴀᴛᴇ: {bitrate}", callback_data="triggerbitrate", style="primary")],
                    [StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="OpenSettings", style="danger")]
                ]
            )
        )
    except FloodWait as e:
        await asyncio.sleep(e.x)
        await AudioSettings(event, user_id)
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER.error(f"Error in AudioSettings: {e}")
        try:
            await event.edit(card("settings error", rows=[("menu", "AudioSettings"), ("error", e)], icon="❌"))
        except:
            pass


async def ExtraSettings(event: Message, user_id: int):
    try:
        thumb_mode = await db.get_thumb_mode(user_id)
        await event.edit(
            text=card("extra settings", note="tap any option to change it", icon="✨"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [StyledButton("ꜱᴜʙᴛɪᴛʟᴇꜱ ᴏᴘᴛɪᴏɴꜱ", callback_data="Watermark", style="primary")],
                    [StyledButton(f"ʜᴀʀᴅꜱᴜʙ {'☑️' if ((await db.get_hardsub(user_id)) is True) else ''}", callback_data="triggerHardsub", style="success"),
                     StyledButton(f"ꜱᴜʙᴛɪᴛʟᴇꜱ {'☑️' if ((await db.get_subtitles(user_id)) is True) else ''}", callback_data="triggerSubtitles", style="success")],
                    [StyledButton("ᴜᴘʟᴏᴀᴅ ᴏᴘᴛɪᴏɴꜱ", callback_data="Watermark", style="primary")],
                    [StyledButton(f"ᴅᴇꜱᴛɪɴᴀᴛɪᴏɴ: {'ɢ-ᴅʀɪᴠᴇ' if ((await db.get_drive(user_id)) is True) else 'ᴛᴇʟᴇɢʀᴀᴍ'}", callback_data="triggerMode", style="primary"),
                     StyledButton(f"ᴍᴏᴅᴇ: {'ᴅᴏᴄᴜᴍᴇɴᴛ' if ((await db.get_upload_as_doc(user_id)) is True) else 'ᴠɪᴅᴇᴏ'}", callback_data="triggerUploadMode", style="primary")],
                    [StyledButton("ᴡᴀᴛᴇʀᴍᴀʀᴋ & ᴍᴇᴛᴀᴅᴀᴛᴀ ᴏᴘᴛɪᴏɴꜱ", callback_data="Watermark", style="primary")],
                    [StyledButton(f"ᴍᴇᴛᴀᴅᴀᴛᴀ {'☑️' if ((await db.get_metadata_w(user_id)) is True) else ''}", callback_data="triggerMetadata", style="success"),
                     StyledButton(f"ᴡᴀᴛᴇʀᴍᴀʀᴋ {'☑️' if ((await db.get_watermark(user_id)) is True) else ''}", callback_data="triggerVideo", style="success")],
                    [StyledButton(f"ᴍᴏᴛɪᴏɴ {'☑️' if ((await db.get_motion_watermark(user_id)) is True) else ''}", callback_data="triggerMotion", style="success"),
                     StyledButton(f"ᴏᴘᴀᴄɪᴛʏ: {await db.get_motion_opacity(user_id)}%", callback_data="triggerOpacity", style="primary")],
                    [StyledButton("ᴛʜᴜᴍʙɴᴀɪʟ ᴏᴘᴛɪᴏɴꜱ", callback_data="Watermark", style="primary")],
                    [StyledButton(f"ᴛʜᴜᴍʙ ᴍᴏᴅᴇ: {thumb_mode.upper()}", callback_data="triggerThumbMode", style="primary")],
                    [StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="OpenSettings", style="danger")]
                ]
            )
        )

    except FloodWait as e:
        await asyncio.sleep(e.x)
        await ExtraSettings(event, user_id)
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER.error(f"Error in ExtraSettings: {e}")
        try:
            await event.edit(card("settings error", rows=[("menu", "ExtraSettings"), ("error", e)], icon="❌"))
        except:
            pass


async def RenameMetadataSettings(event: Message, user_id: int):
    try:
        rename_tmpl = await db.get_rename_template(user_id)
        meta_title = await db.get_metadata_title(user_id) or "not set"
        meta_author = await db.get_metadata_author(user_id) or "not set"
        meta_audio = await db.get_metadata_audio_title(user_id) or "not set"
        meta_sub = await db.get_metadata_sub_title(user_id) or "not set"
        clear_meta = "ENABLED" if await db.get_clear_metadata(user_id) else "DISABLED"

        text = card(
            "rename & metadata settings",
            rows=[
                ("rename pattern", rename_tmpl),
                ("video title", meta_title),
                ("author / copyright", meta_author),
                ("audio metadata", meta_audio),
                ("subtitle metadata", meta_sub),
                ("clear original meta", clear_meta),
            ],
            note="tap any option below to update your default settings for future files",
            icon="✏️",
        )

        buttons = [
            [
                StyledButton("ꜱᴇᴛ ʀᴇɴᴀᴍᴇ ᴘᴀᴛᴛᴇʀɴ", callback_data="s_prompt_rename", style="primary"),
                StyledButton("ꜱᴇᴛ ᴠɪᴅᴇᴏ ᴛɪᴛʟᴇ", callback_data="s_prompt_meta_title", style="primary")
            ],
            [
                StyledButton("ꜱᴇᴛ ᴀᴜᴛʜᴏʀ", callback_data="s_prompt_meta_author", style="primary"),
                StyledButton("ᴀᴜᴅɪᴏ ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="s_prompt_meta_audio", style="primary")
            ],
            [
                StyledButton("ꜱᴜʙᴛɪᴛʟᴇ ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="s_prompt_meta_sub", style="primary"),
                StyledButton(f"ᴄʟᴇᴀʀ ᴍᴇᴛᴀ: {clear_meta}", callback_data="s_toggle_clear_meta", style="success")
            ],
            [
                StyledButton("ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="OpenSettings", style="danger")
            ]
        ]
        await event.edit(text, reply_markup=InlineKeyboardMarkup(buttons))
    except FloodWait as e:
        await asyncio.sleep(e.x)
        await RenameMetadataSettings(event, user_id)
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER.error(f"Error in RenameMetadataSettings: {e}")
        try:
            await event.edit(card("settings error", rows=[("menu", "RenameMetadataSettings"), ("error", e)], icon="❌"))
        except:
            pass
