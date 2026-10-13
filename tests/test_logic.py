import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from VideoEncoder.utils.database.database import Database
from VideoEncoder.utils.ffmpeg_builder import (
    build_ffmpeg_command, sanitize_filename, format_renamed_file,
    resolve_language_name, extract_stream_language, generate_stream_metadata_title
)
from VideoEncoder.utils.encoding import extract_ffmpeg_error, _read_stderr


class TestUserLogic(unittest.IsolatedAsyncioTestCase):

    def test_sanitize_and_format_renamed_file(self):
        self.assertEqual(sanitize_filename("invalid/file:name?.mp4"), "invalid_file_name_.mp4")

        formatted = format_renamed_file(
            original_filename="Sample.Video.1080p.mkv",
            template="[MyBot] {filename} - {resolution}.{ext}",
            resolution="720",
            codec="HEVC",
            crf=24,
            extension="mkv"
        )
        self.assertIn("[MyBot]", formatted)
        self.assertIn("720p", formatted)
        self.assertTrue(formatted.endswith(".mkv"))

        # Test duplicate counter (1) stripping
        formatted_collision = format_renamed_file(
            original_filename="Cats Eye (2025) HDRip(1).mkv",
            template="{filename}",
            resolution="OG",
            extension="mkv"
        )
        self.assertNotIn("(1)", formatted_collision)
        self.assertEqual(formatted_collision, "Cats Eye (2025) HDRip.mkv")

    async def test_database_user_defaults_and_settings(self):
        # Mock Motor client and database
        mock_client = MagicMock()
        mock_col = AsyncMock()

        db = Database("mongodb://localhost:27017", "testdb")
        db.col = mock_col

        user_data = {
            'id': 12345,
            'hevc': True,
            'crf': 24,
            'resolution': '720',
            'thumb_mode': 'frame',
            'rename_template': '[Enc] {filename}',
            'metadata_title': 'My Title',
            'metadata_author': 'My Author',
            'metadata_audio_title': 'My Audio',
            'metadata_sub_title': 'My Sub',
            'clear_metadata': True
        }
        mock_col.find_one.return_value = user_data

        user = await db._get_user(12345)
        self.assertEqual(user['hevc'], True)
        self.assertEqual(user['crf'], 24)
        self.assertEqual(user['resolution'], '720')
        self.assertEqual(user['thumb_mode'], 'frame')
        self.assertEqual(user['rename_template'], '[Enc] {filename}')
        self.assertEqual(user['metadata_title'], 'My Title')
        self.assertEqual(user['clear_metadata'], True)

        # Test cached field update
        await db.set_crf(12345, 18)
        self.assertEqual(db._user_cache[12345]['crf'], 18)

    @patch('VideoEncoder.plugins.panel.execute_single_pass_task', new_callable=AsyncMock)
    @patch('VideoEncoder.plugins.panel.get_media_streams')
    @patch('VideoEncoder.plugins.panel.db._get_user', new_callable=AsyncMock)
    async def test_start_direct_processing(self, mock_get_user, mock_get_streams, mock_execute_task):
        from VideoEncoder.plugins.panel import start_direct_processing, task_sessions

        mock_get_user.return_value = {
            'hevc': True,
            'crf': 20,
            'preset': 'sf',
            'resolution': '1080',
            'frame': 'source',
            'tune': False,
            'aspect': False,
            'bits': False,
            'audio': 'aac',
            'sample': 'source',
            'bitrate': 'source',
            'channels': 'source',
            'watermark': False,
            'motion_watermark': False,
            'hardsub': False,
            'subtitles': True,
            'extensions': 'MKV',
            'rename_template': '{filename}',
            'metadata_title': '',
            'metadata_author': '',
            'metadata_audio_title': '',
            'clear_metadata': False,
            'thumb_mode': 'custom'
        }
        mock_get_streams.return_value = [{'index': 0, 'codec_type': 'video'}, {'index': 1, 'codec_type': 'audio'}]

        mock_client = MagicMock()
        mock_status_msg = AsyncMock()
        mock_status_msg.id = 999

        await start_direct_processing(
            client=mock_client,
            chat_id=100,
            message_id=999,
            user_id=12345,
            filepath='/tmp/test_video.mkv',
            status_msg=mock_status_msg,
            override_res='720',
            override_crf=23
        )

        # Check session key registered and override_res & override_crf applied
        session_key = (100, 999)
        self.assertIn(session_key, task_sessions)
        session = task_sessions[session_key]
        self.assertEqual(session['config']['resolution'], '720')
        self.assertEqual(session['config']['crf'], 23)
        self.assertEqual(session['config']['hevc'], True)

    @patch('VideoEncoder.utils.tasks.start_direct_processing', new_callable=AsyncMock)
    @patch('VideoEncoder.utils.tasks.handle_tg_down', new_callable=AsyncMock)
    async def test_tg_task_crf_and_quality_parsing(self, mock_handle_tg_down, mock_start_direct):
        from VideoEncoder.utils.tasks import tg_task

        mock_handle_tg_down.return_value = "/tmp/test.mkv"
        mock_client = MagicMock()
        mock_msg = AsyncMock()
        mock_msg.id = 500

        # Test case 1: /720p -crf23
        user_msg1 = AsyncMock()
        user_msg1.text = "/720p -crf23"
        user_msg1.caption = None
        user_msg1._client = mock_client
        user_msg1.chat.id = 100
        user_msg1.from_user.id = 12345

        await tg_task(user_msg1, mock_msg)
        mock_start_direct.assert_called_with(mock_client, 100, 500, 12345, "/tmp/test.mkv", mock_msg, override_res='720', override_crf=23)

        # Test case 2: /480p -crf 18
        user_msg2 = AsyncMock()
        user_msg2.text = "/480p -crf 18"
        user_msg2.caption = None
        user_msg2._client = mock_client
        user_msg2.chat.id = 100
        user_msg2.from_user.id = 12345

        await tg_task(user_msg2, mock_msg)
        mock_start_direct.assert_called_with(mock_client, 100, 500, 12345, "/tmp/test.mkv", mock_msg, override_res='480', override_crf=18)

        # Test case 3: /1080p without -crf
        user_msg3 = AsyncMock()
        user_msg3.text = "/1080p"
        user_msg3.caption = None
        user_msg3._client = mock_client
        user_msg3.chat.id = 100
        user_msg3.from_user.id = 12345

        await tg_task(user_msg3, mock_msg)
        mock_start_direct.assert_called_with(mock_client, 100, 500, 12345, "/tmp/test.mkv", mock_msg, override_res='1080', override_crf=None)

    @patch('VideoEncoder.plugins.encode.check_chat', new_callable=AsyncMock)
    @patch('VideoEncoder.plugins.encode.AddUserToDatabase', new_callable=AsyncMock)
    async def test_media_file_handler(self, mock_add_user, mock_check_chat):
        from VideoEncoder.plugins.encode import media_file_handler

        mock_check_chat.return_value = True
        mock_app = MagicMock()
        mock_message = AsyncMock()
        mock_message.document = None
        mock_message.video = MagicMock()

        await media_file_handler(mock_app, mock_message)

        mock_message.reply_text.assert_called_once()
        args, _ = mock_message.reply_text.call_args
        self.assertIn("ꜰɪʟᴇ ʀᴇᴄᴇɪᴠᴇᴅ", args[0])
        self.assertIn("ʀᴇᴘʟʏ ᴛᴏ ᴛʜɪꜱ ꜰɪʟᴇ ᴡɪᴛʜ", args[0])

    def test_dynamic_stream_metadata_customization_helpers(self):
        # 1. ISO Language resolution
        self.assertEqual(resolve_language_name("hin"), "Hindi")
        self.assertEqual(resolve_language_name("eng"), "English")
        self.assertEqual(resolve_language_name("jpn"), "Japanese")
        self.assertEqual(resolve_language_name("xyz"), "Xyz")

        # 2. Extract stream language from probed stream dict
        audio_stream_hin = {'index': 1, 'codec_type': 'audio', 'tags': {'language': 'hin'}}
        lang_code, lang_name = extract_stream_language(audio_stream_hin)
        self.assertEqual(lang_code, "hin")
        self.assertEqual(lang_name, "Hindi")

        audio_stream_unknown = {'index': 2, 'codec_type': 'audio', 'tags': {}}
        lang_code_unk, lang_name_unk = extract_stream_language(audio_stream_unknown)
        self.assertEqual(lang_name_unk, "")

        # 3. Audio title generation
        # Known language: {user_custom_tag} - {Language_Name}
        title_aud_hin, _ = generate_stream_metadata_title('audio', 0, 'MyBot', audio_stream_hin)
        self.assertEqual(title_aud_hin, "MyBot - Hindi")

        # Unknown language: {user_custom_tag} - Audio {index+1}
        title_aud_unk, _ = generate_stream_metadata_title('audio', 1, 'MyBot', audio_stream_unknown)
        self.assertEqual(title_aud_unk, "MyBot - Audio 2")

        # 4. Subtitle title generation
        sub_stream_eng = {'index': 3, 'codec_type': 'subtitle', 'tags': {'language': 'eng'}}
        sub_stream_unk = {'index': 4, 'codec_type': 'subtitle', 'tags': {}}

        # Known language: {user_custom_tag} - {Language_Name}
        title_sub_eng, _ = generate_stream_metadata_title('subtitle', 0, 'MyBot', sub_stream_eng)
        self.assertEqual(title_sub_eng, "MyBot - English")

        # Unknown language: {user_custom_tag}
        title_sub_unk, _ = generate_stream_metadata_title('subtitle', 1, 'MyBot', sub_stream_unk)
        self.assertEqual(title_sub_unk, "MyBot")

    @patch('os.path.isfile', return_value=True)
    def test_build_ffmpeg_command_mkv_and_mp4(self, mock_isfile):
        cfg = {
            'hevc': True,
            'crf': 22,
            'preset': 'sf',
            'resolution': '720',
            'extensions': 'MKV',
            'subtitles': True,
            'has_subtitles': True,
            'thumb_filepath': '/tmp/thumb.jpg',
            'metadata_audio_title': 'AudioBot',
            'metadata_sub_title': 'SubBot',
            'streams': [
                {'index': 0, 'codec_type': 'video'},
                {'index': 1, 'codec_type': 'audio', 'tags': {'language': 'hin'}},
                {'index': 2, 'codec_type': 'audio', 'tags': {}},
                {'index': 3, 'codec_type': 'subtitle', 'tags': {'language': 'eng'}},
                {'index': 4, 'codec_type': 'subtitle', 'tags': {}}
            ]
        }
        cmd = build_ffmpeg_command('in.mkv', 'out.mkv', 'prog.txt', cfg)
        self.assertNotIn('-map 0:t?', ' '.join(cmd))
        self.assertIn('-attach', cmd)
        self.assertIn('threads=0', ' '.join(cmd))
        # Verify dynamic stream metadata
        cmd_str = ' '.join(cmd)
        self.assertIn('-metadata:s:a:0 title=AudioBot - Hindi', cmd_str)
        self.assertIn('-metadata:s:a:1 title=AudioBot - Audio 2', cmd_str)
        self.assertIn('-metadata:s:s:0 title=SubBot - English', cmd_str)
        self.assertIn('-metadata:s:s:1 title=SubBot', cmd_str)

        cfg['extensions'] = 'MP4'
        cmd_mp4 = build_ffmpeg_command('in.mkv', 'out.mp4', 'prog.txt', cfg)
        self.assertNotIn('-map 0:t?', ' '.join(cmd_mp4))
        self.assertIn('-disposition:v:1', cmd_mp4)
        self.assertIn('-hwaccel', cmd_mp4)

    def test_extract_ffmpeg_error_parsing(self):
        sample_stderr = [
            "ffmpeg version 5.1.2 Copyright (c) 2000-2022 the FFmpeg developers",
            "built with gcc 11 (Ubuntu 11.3.0-1ubuntu1~22.04)",
            "x265 [info]: tools: fast-intra strong-intra-smoothing deblock(tC=1:B=1)",
            "x265 [info]: frame I:1     KB: 12.00  PSNR Y:45.00",
            "[libx264 @ 0x555] Invalid option or error: Invalid argument for scaling",
            "Conversion failed!"
        ]
        err = extract_ffmpeg_error(sample_stderr)
        self.assertNotIn("x265 [info]", err)
        self.assertIn("Invalid argument for scaling", err)

    async def test_stderr_draining_task(self):
        mock_proc = MagicMock()
        mock_stream = AsyncMock()
        mock_proc.stderr = mock_stream

        mock_stream.readline.side_effect = [
            b"x265 [info]: tools: fast-intra\n",
            b"Error opening input file test.mkv: No such file or directory\n",
            b""
        ]

        lines = []
        await _read_stderr(mock_proc, lines)
        self.assertEqual(len(lines), 2)
        self.assertIn("Error opening input file", lines[1])

    @patch('VideoEncoder.utils.tasks.handle_tasks', new_callable=AsyncMock)
    async def test_concurrent_tasks_queue(self, mock_handle_tasks):
        from VideoEncoder.utils.tasks import start_next_tasks, data
        import VideoEncoder.utils.tasks as tasks_module

        data.clear()
        tasks_module.active_tasks_count = 0

        class SimpleMsg:
            def __init__(self, txt):
                self.text = txt
                self.caption = None
                self._is_active = False
                self.reply_text = AsyncMock()
                self.reply = AsyncMock()
                self.reply_to_message = None
                self.video = None
                self.document = None

        m1 = SimpleMsg("/720p")
        m2 = SimpleMsg("/480p")
        m3 = SimpleMsg("/360p")
        m4 = SimpleMsg("/1080p")

        data.extend([m1, m2, m3, m4])

        await start_next_tasks()

        self.assertTrue(getattr(m1, '_is_active', False))
        self.assertTrue(getattr(m2, '_is_active', False))
        self.assertTrue(getattr(m3, '_is_active', False))
        self.assertFalse(getattr(m4, '_is_active', False))

        data.clear()
        tasks_module.active_tasks_count = 0

    @patch('shutil.which')
    async def test_handle_torrent_download_missing_aria2c(self, mock_which):
        from VideoEncoder.utils.tasks import handle_torrent_download
        mock_which.return_value = None
        mock_msg = AsyncMock()

        res = await handle_torrent_download("magnet:?xt=urn:btih:test", "/tmp", mock_msg)
        self.assertIsNone(res)
        self.assertIn("aria2c is not installed on the system", mock_msg.edit.call_args[0][0])

    @patch('asyncio.create_subprocess_exec', new_callable=AsyncMock)
    @patch('shutil.which')
    @patch('os.walk')
    @patch('os.path.isfile', return_value=True)
    @patch('os.path.getsize', return_value=1024)
    async def test_handle_torrent_download_success(self, mock_getsize, mock_isfile, mock_walk, mock_which, mock_exec):
        from VideoEncoder.utils.tasks import handle_torrent_download
        mock_which.return_value = "/usr/bin/aria2c"
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.stdout.readline.side_effect = [b""]
        mock_proc.stderr.readline.side_effect = [b""]
        mock_exec.return_value = mock_proc
        mock_walk.return_value = [("/tmp", [], ["video.mkv", "file.aria2"])]

        mock_msg = AsyncMock()
        res = await handle_torrent_download("magnet:?xt=urn:btih:12345", "/tmp", mock_msg)

        self.assertEqual(res, "/tmp/video.mkv")
        # Verify aria2c execution arguments included tracker and split settings
        args, _ = mock_exec.call_args
        self.assertEqual(args[0], "aria2c")
        self.assertIn("--split=16", args)
        self.assertIn("--enable-dht=true", args)
        self.assertNotIn("--bt-max-peers=0", args)
        self.assertTrue(any(a.startswith("--bt-tracker=") for a in args))

    @patch('asyncio.create_subprocess_exec', new_callable=AsyncMock)
    @patch('shutil.which')
    async def test_handle_torrent_download_failure_original_error(self, mock_which, mock_exec):
        from VideoEncoder.utils.tasks import handle_torrent_download
        mock_which.return_value = "/usr/bin/aria2c"
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.stdout.readline.side_effect = [b""]
        mock_proc.stderr.readline.side_effect = [b"Exception: [BitTorrent] Could not connect to peer\n", b""]
        mock_exec.return_value = mock_proc

        mock_msg = AsyncMock()
        res = await handle_torrent_download("magnet:?xt=urn:btih:failed123", "/tmp", mock_msg)

        self.assertIsNone(res)
        mock_msg.edit.assert_called()
        edit_args, _ = mock_msg.edit.call_args
        self.assertIn("Could not connect to peer", edit_args[0])

    @patch('VideoEncoder.utils.tasks.handle_torrent_download', new_callable=AsyncMock)
    async def test_handle_download_url_torrent_routing(self, mock_torrent_dl):
        from VideoEncoder.utils.tasks import handle_download_url
        mock_torrent_dl.return_value = "/tmp/torrent_file.mkv"
        mock_msg = AsyncMock()

        user_msg = AsyncMock()
        user_msg.text = "/fetch magnet:?xt=urn:btih:123456789"

        res = await handle_download_url(user_msg, mock_msg, False)
        self.assertEqual(res, "/tmp/torrent_file.mkv")
        mock_torrent_dl.assert_called_once_with("magnet:?xt=urn:btih:123456789", unittest.mock.ANY, mock_msg)


if __name__ == '__main__':
    unittest.main()
