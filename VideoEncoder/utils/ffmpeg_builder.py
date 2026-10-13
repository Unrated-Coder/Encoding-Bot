import os
import re
import logging
import subprocess
import json

LOGGER = logging.getLogger(__name__)

ISO_LANG_MAP = {
    'eng': 'English', 'en': 'English',
    'hin': 'Hindi', 'hi': 'Hindi',
    'tam': 'Tamil', 'ta': 'Tamil',
    'tel': 'Telugu', 'te': 'Telugu',
    'mal': 'Malayalam', 'ml': 'Malayalam',
    'kan': 'Kannada', 'kn': 'Kannada',
    'mar': 'Marathi', 'mr': 'Marathi',
    'ben': 'Bengali', 'bn': 'Bengali',
    'guj': 'Gujarati', 'gu': 'Gujarati',
    'pan': 'Punjabi', 'pa': 'Punjabi',
    'urd': 'Urdu', 'ur': 'Urdu',
    'jpn': 'Japanese', 'ja': 'Japanese',
    'zho': 'Chinese', 'chi': 'Chinese', 'zh': 'Chinese',
    'kor': 'Korean', 'ko': 'Korean',
    'fre': 'French', 'fra': 'French', 'fr': 'French',
    'ger': 'German', 'deu': 'German', 'de': 'German',
    'spa': 'Spanish', 'es': 'Spanish',
    'ita': 'Italian', 'it': 'Italian',
    'rus': 'Russian', 'ru': 'Russian',
    'por': 'Portuguese', 'pt': 'Portuguese',
    'ara': 'Arabic', 'ar': 'Arabic',
    'tur': 'Turkish', 'tr': 'Turkish',
    'vie': 'Vietnamese', 'vi': 'Vietnamese',
    'tha': 'Thai', 'th': 'Thai',
    'ind': 'Indonesian', 'id': 'Indonesian',
    'msa': 'Malay', 'may': 'Malay', 'ms': 'Malay',
    'fil': 'Filipino', 'tl': 'Tagalog',
    'swe': 'Swedish', 'sv': 'Swedish',
    'nor': 'Norwegian', 'no': 'Norwegian',
    'dan': 'Danish', 'da': 'Danish',
    'fin': 'Finnish', 'fi': 'Finnish',
    'pol': 'Polish', 'pl': 'Polish', 'pob': 'Portuguese (Brazil)',
    'ukr': 'Ukrainian', 'uk': 'Ukrainian',
    'ces': 'Czech', 'cze': 'Czech', 'cs': 'Czech',
    'hun': 'Hungarian', 'hu': 'Hungarian',
    'ron': 'Romanian', 'rum': 'Romanian', 'ro': 'Romanian',
    'nld': 'Dutch', 'dut': 'Dutch', 'nl': 'Dutch',
    'ell': 'Greek', 'gre': 'Greek', 'el': 'Greek',
    'heb': 'Hebrew', 'he': 'Hebrew',
    'per': 'Persian', 'fas': 'Persian', 'fa': 'Persian',
    'lat': 'Latin', 'la': 'Latin',
    'und': 'Unknown', 'unk': 'Unknown'
}

def resolve_language_name(lang_code: str) -> str:
    """
    Converts 2/3-letter ISO language codes to human readable language names.
    Falls back to capitalized raw code if full name mapping is missing.
    """
    if not lang_code or not isinstance(lang_code, str):
        return ""
    code = lang_code.strip().lower()
    if code in ISO_LANG_MAP:
        name = ISO_LANG_MAP[code]
        return "" if name == "Unknown" else name
    return code.capitalize()


def extract_stream_language(stream: dict) -> tuple:
    """
    Extracts (lang_code, lang_name) from stream probed dictionary.
    Returns (lang_code, lang_name).
    """
    tags = stream.get('tags') or {}
    tags_lower = {str(k).lower(): str(v) for k, v in tags.items() if v is not None}

    lang_code = tags_lower.get('language', '').strip().lower()

    if not lang_code or lang_code in ['und', 'unk', 'unknown']:
        title = tags_lower.get('title', '').strip()
        if title:
            title_lower = title.lower()
            if title_lower in ISO_LANG_MAP:
                return (title_lower, ISO_LANG_MAP[title_lower])
            resolved = resolve_language_name(title)
            if resolved and resolved.lower() not in ['unknown', title_lower]:
                return (lang_code, resolved)
        return ('', '')

    lang_name = resolve_language_name(lang_code)
    return (lang_code, lang_name)


def generate_stream_metadata_title(stream_type: str, index: int, custom_tag: str, stream_dict: dict = None) -> tuple:
    """
    Generates dynamic custom track title string and language code for audio or subtitle stream.
    Audio Tracks:
      - If language detected: {user_custom_tag} - {Language_Name}
      - If language unknown: {user_custom_tag} - Audio {index+1}
    Subtitle Tracks:
      - If language detected: {user_custom_tag} - {Language_Name}
      - If language unknown: {user_custom_tag}
    """
    stream_dict = stream_dict or {}
    lang_code, lang_name = extract_stream_language(stream_dict)
    tag = custom_tag.strip() if custom_tag else ""

    if not tag:
        return ("", lang_code)

    if stream_type == 'audio':
        if lang_name:
            title = f"{tag} - {lang_name}"
        else:
            title = f"{tag} - Audio {index + 1}"
    elif stream_type == 'subtitle':
        if lang_name:
            title = f"{tag} - {lang_name}"
        else:
            title = f"{tag}"
    else:
        title = tag

    return (title, lang_code)

def sanitize_filename(filename: str) -> str:
    """
    Cleans invalid characters for Linux/Windows file systems.
    Replaces illegal characters with underscores.
    """
    if not filename:
        return "output"
    # Remove control characters and invalid chars: \ / : * ? " < > |
    sanitized = re.sub(r'[\x00-\x1f\x7f\\/:\*\?"<>\|]', '_', filename)
    # Strip leading/trailing spaces or dots
    sanitized = sanitized.strip(' .')
    return sanitized if sanitized else "output"


def format_renamed_file(
    original_filename: str,
    template: str,
    resolution: str = "OG",
    codec: str = "H264",
    crf: int = 22,
    extension: str = "mkv"
) -> str:
    """
    Formats custom file name based on placeholders:
    {filename}, {resolution}, {codec}, {quality}, {ext}
    Smartly replaces existing quality tag in filename with target resolution!
    """
    base_name, orig_ext = os.path.splitext(original_filename)
    if orig_ext.startswith('.'):
        orig_ext = orig_ext[1:]

    # Strip Telegram/Download collision suffixes like (1), (2), (3)
    base_name = re.sub(r'\s*\(\d+\)$', '', base_name)

    target_ext = extension.lower() if extension else (orig_ext.lower() if orig_ext else 'mkv')
    quality_str = f"CRF{crf}" if crf else "HQ"
    res_str = f"{resolution}p" if resolution and resolution != "OG" and not str(resolution).endswith("p") else (resolution or "OG")

    # Smart quality tag replacement in original filename
    if res_str != "OG":
        quality_pattern = r'\b(2160p|1080p|720p|576p|540p|480p|360p|240p|4k|2k)\b'
        if re.search(quality_pattern, base_name, flags=re.IGNORECASE):
            base_name = re.sub(quality_pattern, res_str, base_name, flags=re.IGNORECASE)

    if not template or template.strip() == "{filename}":
        out_name = f"{base_name}.{target_ext}"
    else:
        try:
            formatted = template.format(
                filename=base_name,
                resolution=res_str,
                codec=codec,
                quality=quality_str,
                ext=target_ext
            )
        except Exception as e:
            LOGGER.warning(f"Failed to format rename template '{template}': {e}, falling back to safe replacement.")
            formatted = template.replace('{filename}', base_name) \
                                .replace('{resolution}', res_str) \
                                .replace('{codec}', codec) \
                                .replace('{quality}', quality_str) \
                                .replace('{ext}', target_ext)

        if not formatted.endswith(f".{target_ext}"):
            formatted = f"{formatted}.{target_ext}"
        out_name = formatted

    return sanitize_filename(out_name)


def build_ffmpeg_command(
    input_filepath: str,
    output_filepath: str,
    progress_filepath: str,
    config: dict
) -> list:
    """
    Constructs a dynamic single-pass FFmpeg command array combining:
    - Input streams (-i input)
    - Optional thumbnail stream (-i thumb)
    - Video encoding (codec, crf, preset, scale filters, frame rate, pix_fmt, tune, aspect)
    - Audio encoding (codec, sample rate, bitrate, channels, stream re-ordering/mapping)
    - Subtitle handling (soft/hard subs)
    - Metadata injection (-metadata, -metadata:s:a, -map_metadata -1)
    - Thumbnail embedding (-disposition:v:1 attached_pic)
    """
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-hwaccel', 'auto', '-y', '-threads', '0', '-filter_threads', '0']

    if progress_filepath:
        cmd.extend(['-progress', progress_filepath])

    cmd.extend(['-thread_queue_size', '4096', '-i', input_filepath])

    thumb_filepath = config.get('thumb_filepath')
    has_thumb_file = bool(thumb_filepath and os.path.isfile(thumb_filepath))

    if has_thumb_file:
        cmd.extend(['-thread_queue_size', '2048', '-i', thumb_filepath])

    # 1. Video Stream Mapping & Filters
    cmd.extend(['-map', '0:v:0'])

    # Video Codec with max thread optimizations
    hevc = config.get('hevc', False)
    if hevc:
        cmd.extend(['-c:v', 'libx265', '-x265-params', 'frame-threads=0:pools=*:no-sao=1'])
    else:
        cmd.extend(['-c:v', 'libx264', '-x264opts', 'threads=0'])

    # Bit depth (yuv420p vs yuv420p10le)
    bits = config.get('bits', False)
    if bits and hevc:
        cmd.extend(['-pix_fmt', 'yuv420p10le'])
    else:
        cmd.extend(['-pix_fmt', 'yuv420p'])

    # CRF & Preset
    crf = config.get('crf', 22)
    cmd.extend(['-crf', str(crf)])

    preset_map = {
        'uf': 'ultrafast', 'sf': 'superfast', 'vf': 'veryfast',
        'f': 'fast', 'm': 'medium', 's': 'slow'
    }
    preset_val = config.get('preset', 'sf')
    preset_str = preset_map.get(preset_val, preset_val)
    cmd.extend(['-preset', preset_str])

    # Tune
    tune = config.get('tune', False)
    if tune:
        cmd.extend(['-tune', 'animation'])

    # Frame Rate
    frame = config.get('frame', 'source')
    if frame == 'ntsc':
        cmd.extend(['-r', 'ntsc'])
    elif frame == 'pal':
        cmd.extend(['-r', 'pal'])
    elif frame == 'film':
        cmd.extend(['-r', 'film'])
    elif frame == '23.976':
        cmd.extend(['-r', '24000/1001'])
    elif frame == '30':
        cmd.extend(['-r', '30'])
    elif frame == '60':
        cmd.extend(['-r', '60'])

    # Aspect Ratio
    if config.get('aspect', False):
        cmd.extend(['-aspect', '16:9'])

    # Video Filters (Fast Scaling with bicubic flags)
    vf_filters = []
    res = str(config.get('resolution', 'OG'))
    if res in ['1080', '720', '576', '540', '480', '360']:
        vf_filters.append(f"scale=-2:'min({res}\\,ih)':flags=fast_bilinear")

    def escape_filter_path(p: str) -> str:
        # Escape colons and backslashes for FFmpeg filter syntax
        escaped = str(p).replace('\\', '/').replace(':', '\\:')
        return f"'{escaped}'"

    if config.get('watermark', False):
        watermark_ass = 'VideoEncoder/utils/extras/watermark.ass'
        if os.path.exists(watermark_ass):
            vf_filters.append(f'subtitles={escape_filter_path(watermark_ass)}')

    subtitles_path = config.get('subtitles_path')
    if config.get('hardsub', False) and subtitles_path and os.path.exists(subtitles_path):
        vf_filters.append(f'subtitles={escape_filter_path(subtitles_path)}')

    if config.get('motion_watermark', False):
        motion_ass = 'VideoEncoder/utils/extras/motion.ass'
        if os.path.exists(motion_ass):
            vf_filters.append(f'subtitles={escape_filter_path(motion_ass)}')

    if vf_filters:
        cmd.extend(['-vf', ','.join(vf_filters)])

    # 2. Audio Stream Mapping & Options
    audio_map = config.get('audio_map')
    if audio_map and isinstance(audio_map, list):
        for idx in audio_map:
            cmd.extend(['-map', f'0:{idx}'])
        # Set first mapped audio stream as default disposition
        cmd.extend(['-disposition:a:0', 'default'])
    else:
        cmd.extend(['-map', '0:a?'])

    audio_codec = config.get('audio', 'aac')
    if audio_codec == 'dd':
        cmd.extend(['-c:a', 'ac3'])
    elif audio_codec == 'aac':
        cmd.extend(['-c:a', 'aac'])
    elif audio_codec == 'vorbis':
        cmd.extend(['-c:a', 'libvorbis'])
    elif audio_codec == 'alac':
        cmd.extend(['-c:a', 'alac'])
    elif audio_codec == 'opus':
        cmd.extend(['-c:a', 'libopus', '-vbr', 'on'])
    elif audio_codec == 'copy':
        cmd.extend(['-c:a', 'copy'])
    else:
        cmd.extend(['-c:a', 'aac'])

    if audio_codec != 'copy':
        sr = config.get('sample', 'source')
        if sr == '44.1K':
            cmd.extend(['-ar', '44100'])
        elif sr == '48K':
            cmd.extend(['-ar', '48000'])

        bit = config.get('bitrate', 'source')
        if bit in ['400', '320', '256', '224', '192', '160', '128']:
            cmd.extend(['-b:a', f'{bit}k'])

        channels = config.get('channels', 'source')
        if channels == '1.0':
            cmd.extend(['-rematrix_maxval', '1.0', '-ac', '1'])
        elif channels == '2.0':
            cmd.extend(['-rematrix_maxval', '1.0', '-ac', '2'])
        elif channels == '2.1':
            cmd.extend(['-rematrix_maxval', '1.0', '-ac', '3'])
        elif channels == '5.1':
            cmd.extend(['-rematrix_maxval', '1.0', '-ac', '6'])
        elif channels == '7.1':
            cmd.extend(['-rematrix_maxval', '1.0', '-ac', '8'])

    # 3. Subtitle Stream Mapping
    sub_map = config.get('sub_map')
    has_subs = config.get('has_subtitles', False)
    if sub_map and isinstance(sub_map, list):
        for idx in sub_map:
            cmd.extend(['-map', f'0:{idx}'])
        cmd.extend(['-c:s', 'copy'])
    elif has_subs and config.get('subtitles', False) and not config.get('hardsub', False):
        ext = config.get('extensions', 'MKV').upper()
        if ext == 'MP4':
            cmd.extend(['-c:s', 'mov_text', '-map', '0:s?'])
        elif ext == 'MKV':
            cmd.extend(['-c:s', 'copy', '-map', '0:s?'])

    # 4. Thumbnail Attachment in Container (MKV / MP4)
    if has_thumb_file:
        ext = config.get('extensions', 'MKV').upper()
        if ext == 'MKV':
            cmd.extend(['-attach', thumb_filepath, '-metadata:s:t', 'mimetype=image/jpeg', '-metadata:s:t', 'filename=cover.jpg'])
        else:
            cmd.extend(['-map', '1:v'])
            cmd.extend(['-c:v:1', 'mjpeg', '-disposition:v:1', 'attached_pic'])

    # 5. Metadata Mapping & Injection
    if config.get('clear_metadata', False):
        cmd.extend(['-map_metadata', '-1'])
    else:
        cmd.extend(['-map_chapters', '0'])

    # Video title metadata
    meta_title = config.get('metadata_title')
    if meta_title:
        cmd.extend(['-metadata', f'title={meta_title}'])
        cmd.extend(['-metadata:s:v', f'title={meta_title}'])

    # Author/Artist metadata
    meta_author = config.get('metadata_author')
    if meta_author:
        cmd.extend(['-metadata', f'author={meta_author}'])
        cmd.extend(['-metadata', f'artist={meta_author}'])
        cmd.extend(['-metadata', f'copyright={meta_author}'])

    # Dynamic Audio & Subtitle Stream Metadata Customization
    user_audio_tag = config.get('metadata_audio_title') or config.get('user_custom_audio_tag') or config.get('user_custom_tag') or config.get('metadata_title') or ""
    user_sub_tag = config.get('metadata_sub_title') or config.get('user_custom_sub_tag') or config.get('user_custom_tag') or config.get('metadata_title') or ""

    streams = config.get('streams')
    if streams is None and os.path.isfile(input_filepath):
        try:
            cmd_probe = ['ffprobe', '-hide_banner', '-print_format', 'json', '-show_streams', input_filepath]
            out_probe = subprocess.check_output(cmd_probe, stderr=subprocess.DEVNULL)
            streams = json.loads(out_probe.decode('utf-8')).get('streams', [])
        except Exception:
            streams = []

    if streams:
        audio_streams_all = [s for s in streams if s.get('codec_type') == 'audio']
        sub_streams_all = [s for s in streams if s.get('codec_type') == 'subtitle']

        # Determine mapped audio streams
        audio_map = config.get('audio_map')
        if audio_map and isinstance(audio_map, list):
            mapped_audio = [s for idx in audio_map for s in audio_streams_all if s.get('index') == idx]
        else:
            mapped_audio = audio_streams_all

        for out_idx, s in enumerate(mapped_audio):
            title_str, lang_code = generate_stream_metadata_title('audio', out_idx, user_audio_tag, s)
            if title_str:
                cmd.extend(['-metadata:s:a:' + str(out_idx), f'title={title_str}'])
            if lang_code:
                cmd.extend(['-metadata:s:a:' + str(out_idx), f'language={lang_code}'])

        # Determine mapped subtitle streams
        sub_map = config.get('sub_map')
        if sub_map and isinstance(sub_map, list):
            mapped_subs = [s for idx in sub_map for s in sub_streams_all if s.get('index') == idx]
        elif config.get('has_subtitles', False) or (config.get('subtitles', False) and not config.get('hardsub', False)):
            mapped_subs = sub_streams_all
        else:
            mapped_subs = []

        for out_idx, s in enumerate(mapped_subs):
            title_str, lang_code = generate_stream_metadata_title('subtitle', out_idx, user_sub_tag, s)
            if title_str:
                cmd.extend(['-metadata:s:s:' + str(out_idx), f'title={title_str}'])
            if lang_code:
                cmd.extend(['-metadata:s:s:' + str(out_idx), f'language={lang_code}'])
    else:
        # Fallback if stream probing info unavailable
        if user_audio_tag:
            cmd.extend(['-metadata:s:a', f'title={user_audio_tag}'])
        if user_sub_tag:
            cmd.extend(['-metadata:s:s', f'title={user_sub_tag}'])

    cmd.extend(['-threads', '0', str(output_filepath)])
    return [str(x) for x in cmd]
