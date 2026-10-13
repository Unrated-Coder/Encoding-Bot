

import asyncio
import json
import math
import os
import re
import subprocess
import time

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .. import LOGGER, download_dir, encode_dir
from .database.access_db import db
from .display_progress import TimeFormatter
from .ui import card, sc


async def _read_stderr(proc, stderr_lines, max_lines=100):
    try:
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            line_str = line.decode('utf-8', errors='ignore').strip()
            if line_str:
                stderr_lines.append(line_str)
                if len(stderr_lines) > max_lines:
                    stderr_lines.pop(0)
    except Exception:
        pass


def extract_ffmpeg_error(stderr_lines):
    if isinstance(stderr_lines, str):
        stderr_lines = stderr_lines.splitlines()
    error_candidates = []
    for line in stderr_lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        if re.match(r'^(x265|x264|libx265|libx264)\s*\[info\]:', line_clean, re.IGNORECASE):
            continue
        if re.match(r'^(ffmpeg|ffprobe) version', line_clean, re.IGNORECASE):
            continue
        if re.match(r'^(built with|configuration:)', line_clean, re.IGNORECASE):
            continue
        error_candidates.append(line_clean)

    if error_candidates:
        specific_critical = [
            l for l in error_candidates
            if any(k in l.lower() for k in ['error', 'failed', 'invalid', 'cannot', 'no such', 'denied', 'corrupt', 'unknown'])
            and l.strip().lower() not in ['conversion failed!', 'conversion failed']
        ]
        if specific_critical:
            return specific_critical[-1]
        return error_candidates[-1]
    return "Unknown FFmpeg Error"


def get_codec(filepath, channel='v:0'):
    try:
        output = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', channel,
                                          '-show_entries', 'stream=codec_name,codec_tag_string', '-of',
                                          'default=nokey=1:noprint_wrappers=1', filepath])
        return output.decode('utf-8').split()
    except subprocess.CalledProcessError as e:
        LOGGER.error(f"ffprobe failed for {filepath}: {e}")
        return []
    except Exception as e:
        LOGGER.error(f"ffprobe exception for {filepath}: {e}")
        return []

def get_media_streams(filepath):
    try:
        cmd = ['ffprobe', '-hide_banner', '-print_format', 'json', '-show_streams', filepath]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return json.loads(output.decode('utf-8')).get('streams', [])
    except Exception as e:
        LOGGER.error(f"Failed to get media streams: {e}")
        return []

async def extract_subs(filepath, msg, user_id):

    path, extension = os.path.splitext(filepath)
    name = os.path.basename(path)
    check = get_codec(filepath, channel='s:0')
    if check == []:
        return None
    elif check == 'pgs':
        return None
    else:
        output = os.path.join(encode_dir, str(msg.id) + '.ass')

    try:
        subprocess.call(['ffmpeg', '-y', '-i', filepath, '-map', 's:0', output])
        # mkvextract might not be in PATH on Windows, handle gracefully
        try:
            subprocess.call(['mkvextract', 'attachments', filepath, '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16',
                            '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40'])
        except FileNotFoundError:
            LOGGER.warning("mkvextract not found, skipping attachments extraction.")
        except Exception as e:
            LOGGER.error(f"mkvextract failed: {e}")

        # Moving fonts is Linux specific and dangerous on Windows to assume /usr/share/fonts/
        # We will only attempt this on Linux-like environments or skip if it fails
        try:
            if os.name != 'nt':
                subprocess.run([f"mv -f *.JFPROJ *.FNT *.PFA *.ETX *.WOFF *.FOT *.TTF *.SFD *.VLW *.VFB *.PFB *.OTF *.GXF *.WOFF2 *.ODTTF *.BF *.CHR *.TTC *.BDF *.FON *.GF *.PMT *.AMFM  *.MF *.PFM *.COMPOSITEFONT *.PF2 *.GDR *.ABF *.VNF *.PCF *.SFP *.MXF *.DFONT *.UFO *.PFR *.TFM *.GLIF *.XFN *.AFM *.TTE *.XFT *.ACFM *.EOT *.FFIL *.PK *.SUIT *.NFTR *.EUF *.TXF *.CHA *.LWFN *.T65 *.MCF *.YTF *.F3F *.FEA *.SFT *.PFT /usr/share/fonts/"], shell=True)
                subprocess.run([f"mv -f *.jfproj *.fnt *.pfa *.etx *.woff *.fot *.ttf *.sfd *.vlw *.vfb *.pfb *.otf *.gxf *.woff2 *.odttf *.bf *.chr *.ttc *.bdf *.fon *.gf *.pmt *.amfm  *.mf *.pfm *.compositefont *.pf2 *.gdr *.abf *.vnf *.pcf *.sfp *.mxf *.dfont *.ufo *.pfr *.tfm *.glif *.xfn *.afm *.tte *.xft *.acfm *.eot *.ffil *.pk *.suit *.nftr *.euf *.txf *.cha *.lwfn *.t65 *.mcf *.ytf *.f3f *.fea *.sft *.pft /usr/share/fonts/ && fc-cache -f"], shell=True)
        except Exception as e:
            LOGGER.warning(f"Font moving failed (likely not supported on this OS): {e}")

        return output
    except Exception as e:
        LOGGER.error(f"Extract subs failed: {e}")
        return None


async def encode(filepath, message, msg, audio_map=None):

    ex = await db.get_extensions(message.from_user.id)
    path, extension = os.path.splitext(filepath)
    name = os.path.basename(path)
    name = re.sub(r'\s*\(\d+\)$', '', name)

    if ex == 'MP4':
        output_filepathh = os.path.join(encode_dir, name + '.mp4')
    elif ex == 'AVI':
        output_filepathh = os.path.join(encode_dir, name + '.avi')
    else:
        output_filepathh = os.path.join(encode_dir, name + '.mkv')

    output_filepath = output_filepathh
    subtitles_path = os.path.join(encode_dir, str(msg.id) + '.ass')

    progress = os.path.join(download_dir, "process.txt")
    with open(progress, 'w') as f:
        pass

    assert(output_filepath != filepath)

    # Check Path
    if os.path.isfile(output_filepath):
        LOGGER.warning(f'"{output_filepath}": file already exists')
    else:
        LOGGER.info(filepath)

    # HEVC Encode
    x265 = await db.get_hevc(message.from_user.id)
    video_i = get_codec(filepath, channel='v:0')
    if video_i == []:
        codec = ''
    else:
        if x265:
            codec = '-c:v libx265 -x265-params frame-threads=0:pools=*:no-sao=1'
        else:
            codec = '-c:v libx264 -x264opts threads=0'

    # Tune Encode
    tune = await db.get_tune(message.from_user.id)
    if tune:
        tunevideo = '-tune animation'
    else:
        tunevideo = '-tune film'

    # CABAC
    cbb = await db.get_cabac(message.from_user.id)
    if cbb:
        cabac = '-coder 1'
    else:
        cabac = '-coder 0'

    # Reframe
    rf = await db.get_reframe(message.from_user.id)
    if rf == '4':
        reframe = '-refs 4'
    elif rf == '8':
        reframe = '-refs 8'
    elif rf == '16':
        reframe = '-refs 16'
    else:
        reframe = ''

    # Bits
    b = await db.get_bits(message.from_user.id)
    if not b:
        codec += ' -pix_fmt yuv420p'
    else:
        codec += ' -pix_fmt yuv420p10le'

    # CRF
    crf = await db.get_crf(message.from_user.id)
    if crf:
        Crf = f'-crf {crf}'
    else:
        await db.set_crf(message.from_user.id, crf=26)
        Crf = '-crf 26'

    # Frame
    fr = await db.get_frame(message.from_user.id)
    if fr == 'ntsc':
        frame = '-r ntsc'
    elif fr == 'pal':
        frame = '-r pal'
    elif fr == 'film':
        frame = '-r film'
    elif fr == '23.976':
        frame = '-r 24000/1001'
    elif fr == '30':
        frame = '-r 30'
    elif fr == '60':
        frame = '-r 60'
    else:
        frame = ''

    # Aspect ratio
    ap = await db.get_aspect(message.from_user.id)
    if ap:
        aspect = '-aspect 16:9'
    else:
        aspect = ''

    # Preset
    p = await db.get_preset(message.from_user.id)
    if p == 'uf':
        preset = '-preset ultrafast'
    elif p == 'sf':
        preset = '-preset superfast'
    elif p == 'vf':
        preset = '-preset veryfast'
    elif p == 'f':
        preset = '-preset fast'
    elif p == 'm':
        preset = '-preset medium'
    else:
        preset = '-preset slow'

    # Some Optional Things
    x265 = await db.get_hevc(message.from_user.id)
    if x265:
        video_opts = f'-profile:v main  -map 0:v? -map_chapters 0 -map_metadata 0'
    else:
        video_opts = f'{cabac} {reframe} -profile:v main  -map 0:v? -map_chapters 0 -map_metadata 0'

    # Metadata Watermark
    m = await db.get_metadata_w(message.from_user.id)
    if m:
        metadata = '-metadata title=Cantarellabots -metadata:s:v title=Cantarellabots -metadata:s:a title=Cantarellabots'
    else:
        metadata = ''

    # Copy Subtitles
    h = await db.get_hardsub(message.from_user.id)
    s = await db.get_subtitles(message.from_user.id)
    subs_i = get_codec(filepath, channel='s:0')
    if subs_i == []:
        subtitles = ''
    else:
        if s:
            if h:
                subtitles = ''
            else:
                if ex == 'MP4':
                    subtitles = '-c:s mov_text -c:t copy -map 0:t? -map 0:s?'
                elif ex == 'AVI':
                    subtitles = ''
                else:
                    subtitles = '-c:s copy -c:t copy -map 0:t? -map 0:s?'
        else:
            subtitles = ''


#    ffmpeg_filter = ':'.join([
#        'drawtext=fontfile=/app/bot/utils/watermark/font.ttf',
#        f"text='Cantarellabots'",
#        f'fontcolor=white',
#        'fontsize=main_h/20',
#        f'x=40:y=40'
#    ])

    # Watermark and Resolution
    r = str(await db.get_resolution(message.from_user.id))
    w = await db.get_watermark(message.from_user.id)
    if r == 'OG':
        watermark = ''
    elif r in ['1080', '720', '576', '540', '480', '360']:
        watermark = f"-vf scale=-2:'min({r}\\,ih)':flags=fast_bilinear"
    else:
        watermark = "-vf scale=-2:'min(480\\,ih)':flags=fast_bilinear"
    if w:
        if r == 'OG':
            watermark += '-vf '
        else:
            watermark += ','
        watermark += 'subtitles=VideoEncoder/utils/extras/watermark.ass'

    # Hard Subs
    if h:
        if r == 'OG':
            if w:
                watermark += ','
            else:
                watermark += '-vf '
        else:
            watermark += ','
        watermark += f'subtitles={subtitles_path}'

    # Motion Watermark
    m_watermark = await db.get_motion_watermark(message.from_user.id)
    if m_watermark:
        m_opacity = await db.get_motion_opacity(message.from_user.id)
        if m_opacity == '50':
            alpha = '80'
        elif m_opacity == '75':
            alpha = '40'
        elif m_opacity == '100':
            alpha = '00'
        else:
            alpha = '80'

        motion_text = "Watermark"
        ass_file = 'VideoEncoder/utils/extras/watermark.ass'
        if os.path.exists(ass_file):
            with open(ass_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('Title:'):
                        motion_text = line.replace('Title:', '').strip()
                        break
        
        motion_ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: MotionStyle,Arial,48,&H{alpha}FFFFFF,&H000000FF,&H{alpha}000000,&H{alpha}000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,9:59:59.99,MotionStyle,,0,0,0,Banner;10;0;50,{motion_text}
"""
        motion_ass_file = 'VideoEncoder/utils/extras/motion.ass'
        with open(motion_ass_file, 'w', encoding='utf-8') as f:
            f.write(motion_ass_content)
            
        m_filter = f"subtitles={motion_ass_file}"
        
        if watermark == '':
            watermark = f"-vf {m_filter}"
        else:
            watermark += f",{m_filter}"

    # Sample rate
    sr = await db.get_samplerate(message.from_user.id)
    if sr == '44.1K':
        sample = '-ar 44100'
    elif sr == '48K':
        sample = '-ar 48000'
    else:
        sample = ''

    # bit rate
    bit = await db.get_bitrate(message.from_user.id)
    if bit == '400':
        bitrate = '-b:a 400k'
    elif bit == '320':
        bitrate = '-b:a 320k'
    elif bit == '256':
        bitrate = '-b:a 256k'
    elif bit == '224':
        bitrate = '-b:a 224k'
    elif bit == '192':
        bitrate = '-b:a 192k'
    elif bit == '160':
        bitrate = '-b:a 160k'
    elif bit == '128':
        bitrate = '-b:a 128k'
    else:
        bitrate = ''

    # Audio
    a = await db.get_audio(message.from_user.id)
    a_i = get_codec(filepath, channel='a:0')
    if a_i == []:
        audio_opts = ''
    else:
        if a == 'dd':
            audio_opts = f'-c:a ac3 {sample} {bitrate}'
        elif a == 'aac':
            audio_opts = f'-c:a aac {sample} {bitrate}'
        elif a == 'vorbis':
            audio_opts = f'-c:a libvorbis {sample} {bitrate}'
        elif a == 'alac':
            audio_opts = f'-c:a alac {sample} {bitrate}'
        elif a == 'opus':
            audio_opts = f'-c:a libopus -vbr on {sample} {bitrate}'
        else:
            audio_opts = '-c:a copy'

        if audio_map:
            # If audio_map is provided (e.g. [0:1, 0:2]), we use it to map audio streams.
            # We need to make sure we map all audio streams in the desired order.
            # The audio_opts above sets the codec for all audio streams.
            # We need to construct the map part.
            # Note: The previous code had `-map 0:a?` attached to audio_opts.
            # If we have specific mapping, we shouldn't use generic `-map 0:a?`.

            # The `audio_map` contains indices of audio streams in the original file.
            # e.g. [1, 2] means map 0:1 then map 0:2.

            map_opts = ""
            for idx in audio_map:
                map_opts += f" -map 0:{idx}"

            # Explicitly set the default disposition for the first audio stream in the new order
            # This ensures the first audio track in the list is the default one
            disposition_opts = " -disposition:a:0 default"

            audio_opts = f"{audio_opts} {map_opts} {disposition_opts}"
        else:
             audio_opts += " -map 0:a?"


    # Audio Channel
    c = await db.get_channels(message.from_user.id)
    if '-c:a copy' in audio_opts:
        channels = ''
    elif c == '1.0':
        channels = '-rematrix_maxval 1.0 -ac 1'
    elif c == '2.0':
        channels = '-rematrix_maxval 1.0 -ac 2'
    elif c == '2.1':
        channels = '-rematrix_maxval 1.0 -ac 3'
    elif c == '5.1':
        channels = '-rematrix_maxval 1.0 -ac 6'
    elif c == '7.1':
        channels = '-rematrix_maxval 1.0 -ac 8'
    else:
        channels = ''

    finish = '-threads 0 -filter_threads 0'

    # Finally
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error',
               '-progress', progress, '-hwaccel', 'auto', '-y', '-i', filepath]
    command.extend((codec.split() + preset.split() + frame.split() + tunevideo.split() + aspect.split() + video_opts.split() + Crf.split() +
                   watermark.split() + metadata.split() + subtitles.split() + audio_opts.split() + channels.split() + finish.split()))
    proc = await asyncio.create_subprocess_exec(*command, output_filepath, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    stderr_lines = []
    drain_task = asyncio.create_task(_read_stderr(proc, stderr_lines))

    # Progress Bar
    await handle_progress(proc, msg, message, filepath)
    await proc.wait()
    await drain_task

    if proc.returncode != 0 and proc.returncode != -9:
        err_msg = extract_ffmpeg_error(stderr_lines)
        LOGGER.error(f"FFmpeg encoding failed with code {proc.returncode}: {err_msg}")

    if not os.path.isfile(output_filepath) or os.path.getsize(output_filepath) == 0:
        LOGGER.error(f"Encoding failed: {output_filepath} not created or is 0 bytes.")
        if os.path.isfile(output_filepath):
            os.remove(output_filepath)
        return None

    return output_filepath


def get_thumbnail(in_filename, path, ttl):
    out_filename = os.path.join(path, str(time.time()) + ".jpg")
    try:
        # ffmpeg -ss <ttl> -i <in_filename> -vframes 1 -y <out_filename>
        command = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-ss', str(ttl),
            '-i', in_filename,
            '-vframes', '1',
            '-y', out_filename
        ]
        subprocess.run(command, check=True, capture_output=True)
        if os.path.isfile(out_filename):
            return out_filename
        else:
            LOGGER.warning(f"Thumbnail file not created: {out_filename}")
            return None
    except subprocess.CalledProcessError as e:
        LOGGER.warning(f"Thumbnail generation failed (CalledProcessError): {e.stderr.decode().strip() if e.stderr else e}")
        return None
    except Exception as e:
        LOGGER.warning(f"Thumbnail generation failed: {e}")
        return None


def get_duration(filepath):
    try:
        # Try using ffprobe first
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of',
            'default=noprint_wrappers=1:nokey=1', filepath
        ]
        output = subprocess.check_output(cmd).decode('utf-8').strip()
        return int(float(output))
    except Exception as e:
        LOGGER.warning(f"ffprobe duration failed: {e}, falling back to hachoir")
        try:
            metadata = extractMetadata(createParser(filepath))
            if metadata and metadata.has("duration"):
                return metadata.get('duration').seconds
        except Exception as e:
            LOGGER.error(f"hachoir duration failed: {e}")
    return 0


def get_width_height(filepath):
    try:
        # Try using ffprobe first
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of',
            'csv=s=x:p=0', filepath
        ]
        output = subprocess.check_output(cmd).decode('utf-8').strip()
        width, height = map(int, output.split('x'))
        return width, height
    except Exception as e:
        LOGGER.warning(f"ffprobe width/height failed: {e}, falling back to hachoir")
        try:
            metadata = extractMetadata(createParser(filepath))
            if metadata and metadata.has("width") and metadata.has("height"):
                return metadata.get("width"), metadata.get("height")
        except Exception as e:
            LOGGER.error(f"hachoir width/height failed: {e}")
    return (1280, 720)


async def media_info(saved_file_path):
    process = subprocess.Popen(
        [
            'ffmpeg',
            "-hide_banner",
            '-i',
            saved_file_path
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    stdout, stderr = process.communicate()
    output = stdout.decode().strip()
    duration = re.search(r"Duration:\s*(\d*):(\d*):(\d+\.?\d*)[\s\w*$]", output)
    bitrates = re.search(r"bitrate:\s*(\d+)[\s\w*$]", output)

    if duration is not None:
        hours = int(duration.group(1))
        minutes = int(duration.group(2))
        seconds = math.floor(float(duration.group(3)))
        total_seconds = (hours * 60 * 60) + (minutes * 60) + seconds
    else:
        total_seconds = None
    if bitrates is not None:
        bitrate = bitrates.group(1)
    else:
        bitrate = None
    return total_seconds, bitrate


async def handle_progress(proc, msg, message, filepath):
    name = os.path.basename(filepath)
    # Progress Bar
    COMPRESSION_START_TIME = time.time()
    LOGGER.info("ffmpeg_process: "+str(proc.pid))
    status = download_dir + "status.json"
    with open(status, 'w') as f:
        statusMsg = {
            'running': True,
            'message': msg.id,
            'user': message.from_user.id
        }
        json.dump(statusMsg, f, indent=2)
    with open(status, 'r+') as f:
        statusMsg = json.load(f)
        statusMsg['pid'] = proc.pid
        statusMsg['message'] = msg.id
        statusMsg['user'] = message.from_user.id
        f.seek(0)
        json.dump(statusMsg, f, indent=2)
    while proc.returncode == None:
        await asyncio.sleep(5)
        with open(download_dir + 'process.txt', 'r+') as file:
            text = file.read()
            frame = re.findall(r"frame=(\d+)", text)
            time_in_us = re.findall(r"out_time_ms=(\d+)", text)
            progress = re.findall(r"progress=(\w+)", text)
            speed = re.findall(r"speed=(\d+\.?\d*)", text)
            if len(frame):
                frame = int(frame[-1])
            else:
                frame = 1
            if len(speed):
                speed = speed[-1]
            else:
                speed = 1
            if len(time_in_us):
                time_in_us = time_in_us[-1]
            else:
                time_in_us = 1
            if len(progress):
                if progress[-1] == "end":
                    LOGGER.info(progress[-1])
                    break
            elapsed_str = TimeFormatter(
                (time.time() - COMPRESSION_START_TIME)) or "0s"
            elapsed_time = int(time_in_us)/1000000
            total_time, bitrate = await media_info(filepath)
            difference = math.floor((total_time - elapsed_time) / float(speed))
            ETA = "-"
            if difference > 0:
                ETA = TimeFormatter(difference)
            percentage = math.floor(elapsed_time * 100 / total_time)
            stats = card(
                "encoding video",
                rows=[
                    ("speed", f"{speed}x"),
                    ("frame", frame),
                    ("elapsed", elapsed_str),
                    ("eta", ETA),
                ],
                percent=percentage,
                icon="⚡",
            )
            try:
                await msg.edit(
                    text=stats,
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(sc('cancel'), callback_data='cancel'), InlineKeyboardButton(
                                    sc('stats'), callback_data='stats')
                            ]
                        ]
                    )
                )
            except:
                pass
