
import asyncio
import functools
import inspect
import io
import logging
import math
import os
from hashlib import md5
from pathlib import PurePath
from typing import Union, BinaryIO, Callable

import hydrogram as hydrogram
from hydrogram import StopTransmission
from hydrogram import raw
from hydrogram.session import Session
from hydrogram.methods.advanced.save_file import SaveFile

log = logging.getLogger(__name__)

async def save_file(
    self: "hydrogram.Client",
    path: Union[str, BinaryIO],
    file_id: int = None,
    file_part: int = 0,
    progress: Callable = None,
    progress_args: tuple = ()
):
    """Upload a file onto Telegram servers, without actually sending the message to anyone.
    Useful whenever an InputFile type is required.

    .. note::

        This is a utility method intended to be used **only** when working with raw
        :obj:`functions <hydrogram.api.functions>` (i.e: a Telegram API method you wish to use which is not
        available yet in the Client class as an easy-to-use method).

    .. include:: /_includes/usable-by/users-bots.rst

    Parameters:
        path (``str`` | ``BinaryIO``):
            The path of the file you want to upload that exists on your local machine or a binary file-like object
            with its attribute ".name" set for in-memory uploads.

        file_id (``int``, *optional*):
            In case a file part expired, pass the file_id and the file_part to retry uploading that specific chunk.

        file_part (``int``, *optional*):
            In case a file part expired, pass the file_id and the file_part to retry uploading that specific chunk.

        progress (``Callable``, *optional*):
            Pass a callback function to view the file transmission progress.
            The function must take *(current, total)* as positional arguments (look at Other Parameters below for a
            detailed description) and will be called back each time a new file chunk has been successfully
            transmitted.

        progress_args (``tuple``, *optional*):
            Extra custom arguments for the progress callback function.
            You can pass anything you need to be available in the progress callback scope; for example, a Message
            object or a Client instance in order to edit the message with the updated progress status.

    Other Parameters:
        current (``int``):
            The amount of bytes transmitted so far.

        total (``int``):
            The total size of the file.

        *args (``tuple``, *optional*):
            Extra custom arguments as defined in the ``progress_args`` parameter.
            You can either keep ``*args`` or add every single extra argument in your function signature.

    Returns:
        ``InputFile``: On success, the uploaded file is returned in form of an InputFile object.

    Raises:
        RPCError: In case of a Telegram RPC error.
    """
    semaphore = getattr(self, "save_file_semaphore", None)
    if semaphore:
        async with semaphore:
            return await _save_file_internal(self, path, file_id, file_part, progress, progress_args)
    else:
        return await _save_file_internal(self, path, file_id, file_part, progress, progress_args)


async def _save_file_internal(
    self: "hydrogram.Client",
    path: Union[str, BinaryIO],
    file_id: int = None,
    file_part: int = 0,
    progress: Callable = None,
    progress_args: tuple = ()
):
    if path is None:
        return None

    async def worker(session):
        while True:
            data = await queue.get()

            if data is None:
                return

            try:
                await session.invoke(data)
            except Exception as e:
                log.exception(e)

    part_size = 512 * 1024

    if isinstance(path, (str, PurePath)):
        fp = open(path, "rb")
    elif isinstance(path, io.IOBase):
        fp = path
    else:
        raise ValueError("Invalid file. Expected a file path as string or a binary (not text) file pointer")

    file_name = getattr(fp, "name", "file.jpg")

    fp.seek(0, io.SEEK_END)
    file_size = fp.tell()
    fp.seek(0)

    if file_size == 0:
        raise ValueError("File size equals to 0 B")

    is_premium = getattr(self.me, "is_premium", False) if getattr(self, "me", None) else False
    file_size_limit_mib = 4000 if is_premium else 2000

    if file_size > file_size_limit_mib * 1024 * 1024:
        raise ValueError(f"Can't upload files bigger than {file_size_limit_mib} MiB")

    file_total_parts = int(math.ceil(file_size / part_size))
    is_big = file_size > 10 * 1024 * 1024

    max_transmissions = getattr(self, "max_concurrent_transmissions", 4)
    workers_count = max_transmissions if is_big else 1

    is_missing_part = file_id is not None
    file_id = file_id or self.rnd_id()
    md5_sum = md5() if not is_big and not is_missing_part else None
    session = Session(
        self, await self.storage.dc_id(), await self.storage.auth_key(),
        await self.storage.test_mode(), is_media=True
    )
    workers = [self.loop.create_task(worker(session)) for _ in range(workers_count)]
    queue = asyncio.Queue(1)

    try:
        await session.start()

        fp.seek(part_size * file_part)

        while True:
            chunk = fp.read(part_size)

            if not chunk:
                if not is_big and not is_missing_part:
                    md5_sum = "".join([hex(i)[2:].zfill(2) for i in md5_sum.digest()])
                break

            if is_big:
                rpc = raw.functions.upload.SaveBigFilePart(
                    file_id=file_id,
                    file_part=file_part,
                    file_total_parts=file_total_parts,
                    bytes=chunk
                )
            else:
                rpc = raw.functions.upload.SaveFilePart(
                    file_id=file_id,
                    file_part=file_part,
                    bytes=chunk
                )

            await queue.put(rpc)

            if is_missing_part:
                return

            if not is_big and not is_missing_part:
                md5_sum.update(chunk)

            file_part += 1

            if progress:
                func = functools.partial(
                    progress,
                    min(file_part * part_size, file_size),
                    file_size,
                    *progress_args
                )

                if inspect.iscoroutinefunction(progress):
                    await func()
                else:
                    await self.loop.run_in_executor(self.executor, func)
    except StopTransmission:
        raise
    except Exception as e:
        log.exception(e)
    else:
        if is_big:
            return raw.types.InputFileBig(
                id=file_id,
                parts=file_total_parts,
                name=file_name,

            )
        else:
            return raw.types.InputFile(
                id=file_id,
                parts=file_total_parts,
                name=file_name,
                md5_checksum=md5_sum
            )
    finally:
        for _ in workers:
            await queue.put(None)

        await asyncio.gather(*workers)

        await session.stop()

        if isinstance(path, (str, PurePath)):
            fp.close()

# Apply the patch to SaveFile class
SaveFile.save_file = save_file

# Apply the patch to Client class directly to be sure
hydrogram.Client.save_file = save_file

# ==========================================================
# 🌟 MONKEYPATCH START (Buttons Color Support Enable Karein)
# ==========================================================

_original_btn_init = hydrogram.types.InlineKeyboardButton.__init__
_original_btn_write = hydrogram.types.InlineKeyboardButton.write

def patched_btn_init(self, text: str, callback_data: str = None, url: str = None, style: str = None, **kwargs):
    _original_btn_init(self, text=text, callback_data=callback_data, url=url, **kwargs)
    self.style = style

async def patched_btn_write(self, client=None):
    raw_button = await _original_btn_write(self, client)

    if hasattr(self, "style") and self.style:
        s = str(self.style).lower().strip().lstrip('#')
        style_obj = None

        # Check raw TL schema support
        if hasattr(raw.types, "KeyboardButtonStyle"):
            if s in ["primary", "blue"]:
                style_obj = raw.types.KeyboardButtonStyle(bg_primary=True)
            elif s in ["danger", "red"]:
                style_obj = raw.types.KeyboardButtonStyle(bg_danger=True)
            elif s in ["success", "green"]:
                style_obj = raw.types.KeyboardButtonStyle(bg_success=True)

        if style_obj:
            raw_button.style = style_obj
            # MTProto flag for style field
            if hasattr(raw_button, "flags"):
                raw_button.flags |= (1 << 10)

    return raw_button

hydrogram.types.InlineKeyboardButton.__init__ = patched_btn_init
hydrogram.types.InlineKeyboardButton.write = patched_btn_write
