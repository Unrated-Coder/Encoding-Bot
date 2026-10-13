

import datetime
import json
import os
import re

from hydrogram import Client, ContinuePropagation
from hydrogram.types import CallbackQuery

from .. import app, download_dir, log, owner, sudo_users, LOGGER
from ..plugins.queue import queue_answer
from ..utils.database.access_db import db
from ..utils.settings import (AudioSettings, ExtraSettings, OpenSettings,
                              VideoSettings, RenameMetadataSettings)
from ..plugins.panel import active_prompts, StyledButton
from hydrogram.types import InlineKeyboardMarkup
from .start import showw_status, build_start_text, build_help_text, build_about_text
from ..utils.ui import card, sc, title_only
from ..video_utils.audio_selector import sessions


@app.on_callback_query()
async def callback_handlers(bot: Client, cb: CallbackQuery):
    try:
        # Clear any active prompt listener whenever user interacts with navigation/menu buttons
        if cb.data not in ["s_prompt_rename", "s_prompt_meta_title", "s_prompt_meta_author", "s_prompt_meta_audio", "s_prompt_meta_sub"]:
            active_prompts.pop((cb.message.chat.id, cb.from_user.id), None)

        # Close Button

        if cb.data == "closeMeh":
            active_prompts.pop((cb.message.chat.id, cb.from_user.id), None)
            await cb.message.delete(True)

        elif cb.data == "about_menu":
            text = build_about_text()
            buttons = [
                [StyledButton("ʙᴀᴄᴋ", callback_data="start_menu", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]
            ]
            await cb.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(buttons))

        elif cb.data == "help_menu":
            msg = build_help_text(with_support=False)
            buttons = [
                [StyledButton("ʙᴀᴄᴋ", callback_data="start_menu", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]
            ]
            await cb.message.edit_text(msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(buttons))

        elif cb.data == "start_menu":
            text = build_start_text(cb.from_user.mention())
            from ..utils.helper import start_but
            await cb.message.edit_text(text, reply_markup=start_but)

        # Settings

        elif cb.data == "VideoSettings":
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "OpenSettings":
            await OpenSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "AudioSettings":
            await AudioSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "ExtraSettings":
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "RenameMetadataSettings":
            await RenameMetadataSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "s_toggle_clear_meta":
            curr = await db.get_clear_metadata(cb.from_user.id)
            await db.set_clear_metadata(cb.from_user.id, not curr)
            await RenameMetadataSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "s_prompt_rename":
            active_prompts[(cb.message.chat.id, cb.from_user.id)] = {'type': 's_rename', 'session_key': None, 'msg_id': cb.message.id}
            await cb.message.edit_text(
                card("send your default rename pattern", rows=[("example", "[MyBot] {filename} - {resolution}.{ext}")], icon="✏️"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="RenameMetadataSettings", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif cb.data == "s_prompt_meta_title":
            active_prompts[(cb.message.chat.id, cb.from_user.id)] = {'type': 's_meta_title', 'session_key': None, 'msg_id': cb.message.id}
            await cb.message.edit_text(
                title_only("send your default video title", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="RenameMetadataSettings", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif cb.data == "s_prompt_meta_author":
            active_prompts[(cb.message.chat.id, cb.from_user.id)] = {'type': 's_meta_author', 'session_key': None, 'msg_id': cb.message.id}
            await cb.message.edit_text(
                title_only("send your default author / copyright", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="RenameMetadataSettings", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif cb.data == "s_prompt_meta_audio":
            active_prompts[(cb.message.chat.id, cb.from_user.id)] = {'type': 's_meta_audio', 'session_key': None, 'msg_id': cb.message.id}
            await cb.message.edit_text(
                title_only("send your default audio track title", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="RenameMetadataSettings", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif cb.data == "s_prompt_meta_sub":
            active_prompts[(cb.message.chat.id, cb.from_user.id)] = {'type': 's_meta_sub', 'session_key': None, 'msg_id': cb.message.id}
            await cb.message.edit_text(
                title_only("send your default subtitle track title", "🏷"),
                reply_markup=InlineKeyboardMarkup([[StyledButton("ʙᴀᴄᴋ", callback_data="RenameMetadataSettings", style="primary"), StyledButton("ᴄʟᴏꜱᴇ", callback_data="closeMeh", style="danger")]])
            )

        elif cb.data == "triggerMode":
            if await db.get_drive(cb.from_user.id) is True:
                await db.set_drive(cb.from_user.id, drive=False)
            else:
                await db.set_drive(cb.from_user.id, drive=True)
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "triggerUploadMode":
            if await db.get_upload_as_doc(cb.from_user.id) is True:
                await db.set_upload_as_doc(cb.from_user.id, upload_as_doc=False)
            else:
                await db.set_upload_as_doc(cb.from_user.id, upload_as_doc=True)
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "triggerResize":
            if await db.get_resize(cb.from_user.id) is True:
                await db.set_resize(cb.from_user.id, resize=False)
            else:
                await db.set_resize(cb.from_user.id, resize=True)
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        # Watermark
        elif cb.data == "Watermark":
            await cb.answer(sc("this is just a label, press the buttons below."), show_alert=True)

        # Metadata
        elif cb.data == "triggerMetadata":
            if await db.get_metadata_w(cb.from_user.id):
                await db.set_metadata_w(cb.from_user.id, metadata=False)
            else:
                await db.set_metadata_w(cb.from_user.id, metadata=True)
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        # Watermark
        elif cb.data == "triggerVideo":
            if await db.get_watermark(cb.from_user.id):
                await db.set_watermark(cb.from_user.id, watermark=False)
            else:
                await db.set_watermark(cb.from_user.id, watermark=True)
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        # Motion Watermark
        elif cb.data == "triggerMotion":
            if await db.get_motion_watermark(cb.from_user.id):
                await db.set_motion_watermark(cb.from_user.id, motion=False)
            else:
                await db.set_motion_watermark(cb.from_user.id, motion=True)
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        # Motion Opacity
        elif cb.data == "triggerOpacity":
            op = await db.get_motion_opacity(cb.from_user.id)
            if op == '50':
                await db.set_motion_opacity(cb.from_user.id, opacity='75')
            elif op == '75':
                await db.set_motion_opacity(cb.from_user.id, opacity='100')
            else:
                await db.set_motion_opacity(cb.from_user.id, opacity='50')
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        # Thumb Mode
        elif cb.data == "triggerThumbMode":
            curr = await db.get_thumb_mode(cb.from_user.id)
            modes = ['custom', 'frame', 'default', 'none']
            idx = (modes.index(curr) + 1) % len(modes) if curr in modes else 0
            await db.set_thumb_mode(cb.from_user.id, thumb_mode=modes[idx])
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        # Subtitles
        elif cb.data == "triggerHardsub":
            if await db.get_hardsub(cb.from_user.id):
                await db.set_hardsub(cb.from_user.id, hardsub=False)
            else:
                await db.set_hardsub(cb.from_user.id, hardsub=True)
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "triggerSubtitles":
            if await db.get_subtitles(cb.from_user.id):
                await db.set_subtitles(cb.from_user.id, subtitles=False)
            else:
                await db.set_subtitles(cb.from_user.id, subtitles=True)
            await ExtraSettings(cb.message, user_id=cb.from_user.id)

        # Extension
        elif cb.data == "triggerextensions":
            ex = await db.get_extensions(cb.from_user.id)
            if ex == 'MP4':
                await db.set_extensions(cb.from_user.id, extensions='MKV')
            elif ex == 'MKV':
                await db.set_extensions(cb.from_user.id, extensions='AVI')
            else:
                await db.set_extensions(cb.from_user.id, extensions='MP4')
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # Frame
        elif cb.data == "triggerframe":
            fr = await db.get_frame(cb.from_user.id)
            if fr == 'ntsc':
                await db.set_frame(cb.from_user.id, frame='source')
            elif fr == 'source':
                await db.set_frame(cb.from_user.id, frame='pal')
            elif fr == 'pal':
                await db.set_frame(cb.from_user.id, frame='film')
            elif fr == 'film':
                await db.set_frame(cb.from_user.id, frame='23.976')
            elif fr == '23.976':
                await db.set_frame(cb.from_user.id, frame='30')
            elif fr == '30':
                await db.set_frame(cb.from_user.id, frame='60')
            else:
                await db.set_frame(cb.from_user.id, frame='ntsc')
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # Preset
        elif cb.data == "triggerPreset":
            p = await db.get_preset(cb.from_user.id)
            if p == 'uf':
                await db.set_preset(cb.from_user.id, preset='sf')
            elif p == 'sf':
                await db.set_preset(cb.from_user.id, preset='vf')
            elif p == 'vf':
                await db.set_preset(cb.from_user.id, preset='f')
            elif p == 'f':
                await db.set_preset(cb.from_user.id, preset='m')
            elif p == 'm':
                await db.set_preset(cb.from_user.id, preset='s')
            else:
                await db.set_preset(cb.from_user.id, preset='uf')
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # sample rate
        elif cb.data == "triggersamplerate":
            sr = await db.get_samplerate(cb.from_user.id)
            if sr == '44.1K':
                await db.set_samplerate(cb.from_user.id, sample='48K')
            elif sr == '48K':
                await db.set_samplerate(cb.from_user.id, sample='source')
            else:
                await db.set_samplerate(cb.from_user.id, sample='44.1K')
            await AudioSettings(cb.message, user_id=cb.from_user.id)

        # bitrate
        elif cb.data == "triggerbitrate":
            bit = await db.get_bitrate(cb.from_user.id)
            if bit == '400':
                await db.set_bitrate(cb.from_user.id, bitrate='320')
            elif bit == '320':
                await db.set_bitrate(cb.from_user.id, bitrate='256')
            elif bit == '256':
                await db.set_bitrate(cb.from_user.id, bitrate='224')
            elif bit == '224':
                await db.set_bitrate(cb.from_user.id, bitrate='192')
            elif bit == '192':
                await db.set_bitrate(cb.from_user.id, bitrate='160')
            elif bit == '160':
                await db.set_bitrate(cb.from_user.id, bitrate='128')
            elif bit == '128':
                await db.set_bitrate(cb.from_user.id, bitrate='source')
            else:
                await db.set_bitrate(cb.from_user.id, bitrate='400')
            await AudioSettings(cb.message, user_id=cb.from_user.id)

        # Audio Codec
        elif cb.data == "triggerAudioCodec":
            a = await db.get_audio(cb.from_user.id)
            if a == 'dd':
                await db.set_audio(cb.from_user.id, audio='copy')
            elif a == 'copy':
                await db.set_audio(cb.from_user.id, audio='aac')
            elif a == 'aac':
                await db.set_audio(cb.from_user.id, audio='opus')
            elif a == 'opus':
                await db.set_audio(cb.from_user.id, audio='alac')
            elif a == 'alac':
                await db.set_audio(cb.from_user.id, audio='vorbis')
            else:
                await db.set_audio(cb.from_user.id, audio='dd')
            await AudioSettings(cb.message, user_id=cb.from_user.id)

        # Audio Channel
        elif cb.data == "triggerAudioChannels":
            c = await db.get_channels(cb.from_user.id)
            if c == 'source':
                await db.set_channels(cb.from_user.id, channels='1.0')
            elif c == '1.0':
                await db.set_channels(cb.from_user.id, channels='2.0')
            elif c == '2.0':
                await db.set_channels(cb.from_user.id, channels='2.1')
            elif c == '2.1':
                await db.set_channels(cb.from_user.id, channels='5.1')
            elif c == '5.1':
                await cb.answer(sc("7.1 is for bluray only."), show_alert=True)
                await db.set_channels(cb.from_user.id, channels='7.1')
            else:
                await db.set_channels(cb.from_user.id, channels='source')
            await AudioSettings(cb.message, user_id=cb.from_user.id)

        # Resolution
        elif cb.data == "triggerResolution":
            r = str(await db.get_resolution(cb.from_user.id))
            if r == 'OG':
                await db.set_resolution(cb.from_user.id, resolution='1080')
            elif r == '1080':
                await db.set_resolution(cb.from_user.id, resolution='720')
            elif r == '720':
                await db.set_resolution(cb.from_user.id, resolution='576')
            elif r == '576':
                await db.set_resolution(cb.from_user.id, resolution='540')
            elif r == '540':
                await db.set_resolution(cb.from_user.id, resolution='480')
            elif r == '480':
                await db.set_resolution(cb.from_user.id, resolution='360')
            else:
                await db.set_resolution(cb.from_user.id, resolution='OG')
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # Video Bits
        elif cb.data == "triggerBits":
            b = await db.get_bits(cb.from_user.id)
            if await db.get_hevc(cb.from_user.id):
                if b:
                    await db.set_bits(cb.from_user.id, bits=False)
                else:
                    await db.set_bits(cb.from_user.id, bits=True)
            else:
                if b:
                    await db.set_bits(cb.from_user.id, bits=False)
                else:
                    await cb.answer(sc("h264 doesn't support 10 bits in this bot."),
                                    show_alert=True)
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # HEVC
        elif cb.data == "triggerHevc":
            if await db.get_hevc(cb.from_user.id):
                await db.set_hevc(cb.from_user.id, hevc=False)
            else:
                await db.set_hevc(cb.from_user.id, hevc=True)
                await cb.answer(sc("h265 needs more time for encoding video"), show_alert=True)
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # Quick Compression Presets
        elif cb.data == "triggerCompHigh":
            await db.set_hevc(cb.from_user.id, hevc=True)
            await db.set_crf(cb.from_user.id, crf=28)
            await db.set_preset(cb.from_user.id, preset='sf')
            await cb.answer(sc("high compression preset applied (x265 + crf 28)!"), show_alert=True)
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "triggerCompBal":
            await db.set_hevc(cb.from_user.id, hevc=True)
            await db.set_crf(cb.from_user.id, crf=24)
            await db.set_preset(cb.from_user.id, preset='sf')
            await cb.answer(sc("balanced compression preset applied (x265 + crf 24)!"), show_alert=True)
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # Tune
        elif cb.data == "triggertune":
            if await db.get_tune(cb.from_user.id):
                await db.set_tune(cb.from_user.id, tune=False)
            else:
                await db.set_tune(cb.from_user.id, tune=True)
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # Reframe
        elif cb.data == "triggerreframe":
            rf = await db.get_reframe(cb.from_user.id)
            if rf == '4':
                await db.set_reframe(cb.from_user.id, reframe='8')
            elif rf == '8':
                await db.set_reframe(cb.from_user.id, reframe='16')
                await cb.answer(sc("reframe 16 may not be supported"), show_alert=True)
            elif rf == '16':
                await db.set_reframe(cb.from_user.id, reframe='pass')
            else:
                await db.set_reframe(cb.from_user.id, reframe='4')
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # CABAC
        elif cb.data == "triggercabac":
            if await db.get_cabac(cb.from_user.id):
                await db.set_cabac(cb.from_user.id, cabac=False)
            else:
                await db.set_cabac(cb.from_user.id, cabac=True)
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # Aspect
        elif cb.data == "triggeraspect":
            if await db.get_aspect(cb.from_user.id):
                await db.set_aspect(cb.from_user.id, aspect=False)
            else:
                await db.set_aspect(cb.from_user.id, aspect=True)
                await cb.answer(sc("this will force the video to 16:9"), show_alert=True)
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        elif cb.data == "triggerCRF":
            crf = await db.get_crf(cb.from_user.id)
            nextcrf = int(crf) + 1
            if nextcrf > 30:
                await db.set_crf(cb.from_user.id, crf=18)
            else:
                await db.set_crf(cb.from_user.id, crf=nextcrf)
            await VideoSettings(cb.message, user_id=cb.from_user.id)

        # Audio Selector Callbacks
        elif "audiosel" in cb.data:
            user_id = cb.from_user.id
            if user_id in sessions:
                await sessions[user_id].resolve_callback(cb)
            else:
                await cb.answer(sc("session expired. please try again."), show_alert=True)

        # Cancel

        elif cb.data == "cancel":
            status = download_dir + "status.json"
            try:
                with open(status, 'r+') as f:
                    statusMsg = json.load(f)
                    user = cb.from_user.id
                    if user != statusMsg['user']:
                        if user == 885190545:
                            pass
                        elif user in sudo_users or user in owner:
                            pass
                        else:
                            return
                    statusMsg['running'] = False
                    f.seek(0)
                    json.dump(statusMsg, f, indent=2)
                    os.remove('VideoEncoder/utils/extras/downloads/process.txt')
                    try:
                        await cb.message.edit_text(card("process cancelled", rows=[("status", "encoding stopped")], icon="🚦"))
                        chat_id = log
                        utc_now = datetime.datetime.utcnow()
                        ist_now = utc_now + \
                            datetime.timedelta(minutes=30, hours=5)
                        ist = ist_now.strftime("%d/%m/%Y, %H:%M:%S")
                        bst_now = utc_now + \
                            datetime.timedelta(minutes=00, hours=6)
                        bst = bst_now.strftime("%d/%m/%Y, %H:%M:%S")
                        now = f"\n{ist} (GMT+05:30)`\n`{bst} (GMT+06:00)"
                        await bot.send_message(chat_id, card("last process cancelled", rows=[("status", "bot is free now"), ("time", now.replace("`", "").strip())], icon="🚦"))
                    except:
                        pass
            except FileNotFoundError:
                 await cb.answer(sc("nothing to cancel or process already finished!"), show_alert=True)

        # Stats
        elif 'stats' in cb.data:
            stats = await showw_status(bot)
            clean_stats = re.sub(r'<[^>]+>', '', stats).replace('├ ', '').replace('╰ ', '')
            clean_stats = '\n'.join(clean_stats.splitlines()[1:])
            if len(clean_stats) > 200:
                clean_stats = clean_stats[:197] + "..."
            await cb.answer(clean_stats, show_alert=True)

        # Queue
        elif "queue+" in cb.data:
            await queue_answer(app, cb)

        else:
            cb.continue_propagation()
    except ContinuePropagation:
        raise
    except Exception as e:
        LOGGER.error(f"Error in callback_handlers: {e}")
        try:
            await cb.answer(sc("an error occurred. please try again later."), show_alert=True)
        except:
            pass
