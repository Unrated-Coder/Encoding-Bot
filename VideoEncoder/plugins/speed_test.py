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
        # Run speedtest-cli as a subprocess
        proc = await asyncio.create_subprocess_exec(
            'speedtest-cli', '--json',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(f"Speedtest failed: {stderr.decode().strip()}")

        result = json.loads(stdout.decode())

        caption = card(
            "speedtest result",
            rows=[
                ("ip", result['client']['ip']),
                ("isp", result['client']['isp']),
                ("ping", f"{int(result['ping'])} ms"),
                ("isp rating", result['client']['isprating']),
                ("sponsor", result['server']['sponsor']),
                ("upload", f"{humanbytes(result['upload'] / 8)}/s"),
                ("download", f"{humanbytes(result['download'] / 8)}/s"),
                ("server", result['server']['name']),
                ("country", f"{result['server']['country']}, {result['server']['cc']}"),
                ("lat/lon", f"{result['client']['lat']}/{result['client']['lon']}"),
            ],
            icon="🚀",
        )
        await msg.delete()
        # speedtest-cli json output contains 'share' which is the image URL
        await message.reply_photo(photo=result['share'], caption=caption)
    except Exception as e:
        LOGGER.error(e)
        await msg.edit(card('speedtest failed', rows=[('error', e)], icon='❌'))
