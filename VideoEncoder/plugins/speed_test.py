import asyncio
import json
from hydrogram import filters

from .. import app, LOGGER, sudo_users, owner
from ..utils.display_progress import humanbytes
from ..utils.ui import card, title_only

@app.on_message(filters.command("speedtest") & filters.user(sudo_users + owner))
async def speedtest_handler(_, message):
    msg = await message.reply(card('speed test', rows=[('status', 'running, please wait')], icon='🚀'))
    try:
        import sys
        # Run speedtest with --share --json
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'speedtest', '--share', '--json',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            proc = await asyncio.create_subprocess_exec(
                'speedtest-cli', '--share', '--json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(f"Speedtest failed: {stderr.decode().strip()}")

        result = json.loads(stdout.decode())

        client_info = result.get('client', {})
        server_info = result.get('server', {})

        caption = card(
            "speedtest result",
            rows=[
                ("ip", client_info.get('ip', 'N/A')),
                ("isp", client_info.get('isp', 'N/A')),
                ("ping", f"{int(result.get('ping', 0))} ms"),
                ("isp rating", client_info.get('isprating', 'N/A')),
                ("sponsor", server_info.get('sponsor', 'N/A')),
                ("upload", f"{humanbytes(result.get('upload', 0) / 8)}/s"),
                ("download", f"{humanbytes(result.get('download', 0) / 8)}/s"),
                ("server", server_info.get('name', 'N/A')),
                ("country", f"{server_info.get('country', 'N/A')}, {server_info.get('cc', 'N/A')}"),
                ("lat/lon", f"{client_info.get('lat', 'N/A')}/{client_info.get('lon', 'N/A')}"),
            ],
            icon="🚀",
        )
        await msg.delete()
        
        photo_url = result.get('share')
        if photo_url:
            try:
                await message.reply_photo(photo=photo_url, caption=caption)
                return
            except Exception as pe:
                LOGGER.warning(f"Failed to reply photo for speedtest: {pe}")

        await message.reply_text(caption)
    except Exception as e:
        LOGGER.error(e)
        await msg.edit(card('speedtest failed', rows=[('error', e)], icon='❌'))
