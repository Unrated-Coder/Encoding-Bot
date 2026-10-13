

from hydrogram import Client
from hydrogram.types import Message

from ... import log
from .access_db import db
from ..ui import card, esc


async def AddUserToDatabase(bot: Client, cmd: Message):
    if not await db.is_user_exist(cmd.from_user.id):
        await db.add_user(cmd.from_user.id)
        if log is not None:
            await bot.send_message(
                int(log),
                card("new user", rows=[
                    ("user", f"<a href='tg://user?id={cmd.from_user.id}'>{esc(cmd.from_user.first_name)}</a>", True),
                    ("id", cmd.from_user.id),
                    ("bot", f"@{(await bot.get_me()).username}", True),
                ], icon="🆕")
            )
