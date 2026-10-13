

import datetime

import motor.motor_asyncio


class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.col2 = self.db.status
        self._user_cache = {}
        self._sudo_cache = None
        self._chat_cache = None

    def new_user(self, id):
        return dict(
            id=id,
            join_date=datetime.date.today().isoformat(),
            extensions='MKV',
            hevc=False,
            aspect=False,
            cabac=False,
            reframe='pass',
            tune=True,
            frame='source',
            audio='aac',
            sample='source',
            bitrate='source',
            bits=False,
            channels='source',
            drive=False,
            preset='sf',
            metadata=True,
            hardsub=False,
            watermark=False,
            subtitles=True,
            resolution='OG',
            upload_as_doc=False,
            crf=22,
            resize=False,
            thumbnail=None,
            thumb_mode='custom',
            rename_template='{filename}',
            metadata_title='',
            metadata_author='',
            metadata_audio_title='',
            metadata_sub_title='',
            clear_metadata=False,
            motion_watermark=False,
            motion_opacity='50'
        )

    async def add_user(self, id):
        uid = int(id)
        if not await self.is_user_exist(uid):
            user = self.new_user(uid)
            await self.col.insert_one(user)
            self._user_cache[uid] = user

    async def is_user_exist(self, id):
        uid = int(id)
        if uid in self._user_cache:
            return True
        user = await self.col.find_one({'id': uid})
        if user:
            self._user_cache[uid] = user
            return True
        return False

    async def _update_user_field(self, id, key, val):
        uid = int(id)
        await self.col.update_one({'id': uid}, {'$set': {key: val}}, upsert=True)
        if uid in self._user_cache:
            self._user_cache[uid][key] = val

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.col.find({})
        return all_users

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def _get_user(self, id):
        uid = int(id)
        if uid in self._user_cache:
            return self._user_cache[uid]
        user = await self.col.find_one({'id': uid})
        if not user:
            await self.add_user(uid)
            user = await self.col.find_one({'id': uid})
        if user:
            self._user_cache[uid] = user
        return user

    # Telegram Related

    # Upload As Doc
    async def set_upload_as_doc(self, id, upload_as_doc):
        await self._update_user_field(id, 'upload_as_doc', upload_as_doc)

    async def get_upload_as_doc(self, id):
        user = await self._get_user(id)
        return user.get('upload_as_doc', False)

    # Encoding Settings

    # Resize
    async def set_resize(self, id, resize):
        await self._update_user_field(id, 'resize', resize)

    async def get_resize(self, id):
        user = await self._get_user(id)
        return user.get('resize', 'resize')

    # Frame
    async def set_frame(self, id, frame):
        await self._update_user_field(id, 'frame', frame)

    async def get_frame(self, id):
        user = await self._get_user(id)
        return user.get('frame', 'source')

    # Convert To 720p
    async def set_resolution(self, id, resolution):
        await self._update_user_field(id, 'resolution', resolution)

    async def get_resolution(self, id):
        user = await self._get_user(id)
        return user.get('resolution', 'OG')

    # Video Bits
    async def set_bits(self, id, bits):
        await self._update_user_field(id, 'bits', bits)

    async def get_bits(self, id):
        user = await self._get_user(id)
        return user.get('bits', False)

    # Copy Subtitles
    async def set_subtitles(self, id, subtitles):
        await self._update_user_field(id, 'subtitles', subtitles)

    async def get_subtitles(self, id):
        user = await self._get_user(id)
        return user.get('subtitles', False)

    # Sample rate
    async def set_samplerate(self, id, sample):
        await self._update_user_field(id, 'sample', sample)

    async def get_samplerate(self, id):
        user = await self._get_user(id)
        return user.get('sample', '44.1K')

    # Extensions
    async def set_extensions(self, id, extensions):
        await self._update_user_field(id, 'extensions', extensions)

    async def get_extensions(self, id):
        user = await self._get_user(id)
        return user.get('extensions', 'MP4')

    # Bit rate
    async def set_bitrate(self, id, bitrate):
        await self._update_user_field(id, 'bitrate', bitrate)

    async def get_bitrate(self, id):
        user = await self._get_user(id)
        return user.get('bitrate', '128')

    # Reframe
    async def set_reframe(self, id, reframe):
        await self._update_user_field(id, 'reframe', reframe)

    async def get_reframe(self, id):
        user = await self._get_user(id)
        return user.get('reframe', 'pass')

    # Audio Codec
    async def set_audio(self, id, audio):
        await self._update_user_field(id, 'audio', audio)

    async def get_audio(self, id):
        user = await self._get_user(id)
        return user.get('audio', 'dd')

    # Audio Channels
    async def set_channels(self, id, channels):
        await self._update_user_field(id, 'channels', channels)

    async def get_channels(self, id):
        user = await self._get_user(id)
        return user.get('channels', 'source')

    # Metadata Watermark
    async def set_metadata_w(self, id, metadata):
        await self._update_user_field(id, 'metadata', metadata)

    async def get_metadata_w(self, id):
        user = await self._get_user(id)
        return user.get('metadata', False)

    # Watermark
    async def set_watermark(self, id, watermark):
        await self._update_user_field(id, 'watermark', watermark)

    async def get_watermark(self, id):
        user = await self._get_user(id)
        return user.get('watermark', False)

    # Motion Watermark
    async def set_motion_watermark(self, id, motion):
        await self._update_user_field(id, 'motion_watermark', motion)

    async def get_motion_watermark(self, id):
        user = await self._get_user(id)
        return user.get('motion_watermark', False)

    # Motion Opacity
    async def set_motion_opacity(self, id, opacity):
        await self._update_user_field(id, 'motion_opacity', opacity)

    async def get_motion_opacity(self, id):
        user = await self._get_user(id)
        return user.get('motion_opacity', '50')

    # Preset
    async def set_preset(self, id, preset):
        await self._update_user_field(id, 'preset', preset)

    async def get_preset(self, id):
        user = await self._get_user(id)
        return user.get('preset', 'sf')

    # Hard Sub
    async def set_hardsub(self, id, hardsub):
        await self._update_user_field(id, 'hardsub', hardsub)

    async def get_hardsub(self, id):
        user = await self._get_user(id)
        return user.get('hardsub', False)

    # HEVC
    async def set_hevc(self, id, hevc):
        await self._update_user_field(id, 'hevc', hevc)

    async def get_hevc(self, id):
        user = await self._get_user(id)
        return user.get('hevc', False)

    # Tune
    async def set_tune(self, id, tune):
        await self._update_user_field(id, 'tune', tune)

    async def get_tune(self, id):
        user = await self._get_user(id)
        return user.get('tune', False)

    # CABAC
    async def set_cabac(self, id, cabac):
        await self._update_user_field(id, 'cabac', cabac)

    async def get_cabac(self, id):
        user = await self._get_user(id)
        return user.get('cabac', False)

    # Aspect ratio
    async def set_aspect(self, id, aspect):
        await self._update_user_field(id, 'aspect', aspect)

    async def get_aspect(self, id):
        user = await self._get_user(id)
        return user.get('aspect', False)

    # Google Drive
    async def set_drive(self, id, drive):
        await self._update_user_field(id, 'drive', drive)

    async def get_drive(self, id):
        user = await self._get_user(id)
        return user.get('drive', False)

    # CRF
    async def get_crf(self, id):
        user = await self._get_user(id)
        return user.get('crf', 18)

    async def set_crf(self, id, crf):
        await self._update_user_field(id, 'crf', crf)

    # Process killed status
    async def get_killed_status(self):
        status = await self.col2.find_one({'id': 'killed'})
        if not status:
            await self.col2.insert_one({'id': 'killed', 'status': False})
            return False
        else:
            return status.get('status')

    async def set_killed_status(self, status):
        await self.col2.update_one({'id': 'killed'}, {'$set': {'status': status}}, upsert=True)

    # Auth Chat
    async def get_chat(self):
        if self._chat_cache is not None:
            return self._chat_cache
        status = await self.col2.find_one({'id': 'auth'})
        if not status:
            await self.col2.insert_one({'id': 'auth', 'chat': '5217257368'})
            self._chat_cache = '5217257368'
            return '5217257368'
        else:
            self._chat_cache = status.get('chat')
            return self._chat_cache

    async def set_chat(self, chat):
        self._chat_cache = chat
        await self.col2.update_one({'id': 'auth'}, {'$set': {'chat': chat}}, upsert=True)

    # Auth Sudo
    async def get_sudo(self):
        if self._sudo_cache is not None:
            return self._sudo_cache
        status = await self.col2.find_one({'id': 'sudo'})
        if not status:
            await self.col2.insert_one({'id': 'sudo', 'sudo_': '5217257368'})
            self._sudo_cache = '5217257368'
            return '5217257368'
        else:
            self._sudo_cache = status.get('sudo_')
            return self._sudo_cache

    async def set_sudo(self, sudo):
        self._sudo_cache = sudo
        await self.col2.update_one({'id': 'sudo'}, {'$set': {'sudo_': sudo}}, upsert=True)

    # Thumbnail
    async def set_thumbnail(self, id, thumbnail):
        await self._update_user_field(id, 'thumbnail', thumbnail)

    async def get_thumbnail(self, id):
        user = await self._get_user(id)
        return user.get('thumbnail', None)

    # Thumbnail Mode ('custom', 'frame', 'default', 'none')
    async def set_thumb_mode(self, id, thumb_mode):
        await self._update_user_field(id, 'thumb_mode', thumb_mode)

    async def get_thumb_mode(self, id):
        user = await self._get_user(id)
        return user.get('thumb_mode', 'custom')

    # Rename Template
    async def set_rename_template(self, id, rename_template):
        await self._update_user_field(id, 'rename_template', rename_template)

    async def get_rename_template(self, id):
        user = await self._get_user(id)
        return user.get('rename_template', '{filename}')

    # Metadata Title
    async def set_metadata_title(self, id, metadata_title):
        await self._update_user_field(id, 'metadata_title', metadata_title)

    async def get_metadata_title(self, id):
        user = await self._get_user(id)
        return user.get('metadata_title', '')

    # Metadata Author
    async def set_metadata_author(self, id, metadata_author):
        await self._update_user_field(id, 'metadata_author', metadata_author)

    async def get_metadata_author(self, id):
        user = await self._get_user(id)
        return user.get('metadata_author', '')

    # Metadata Audio Title
    async def set_metadata_audio_title(self, id, metadata_audio_title):
        await self._update_user_field(id, 'metadata_audio_title', metadata_audio_title)

    async def get_metadata_audio_title(self, id):
        user = await self._get_user(id)
        return user.get('metadata_audio_title', '')

    # Metadata Subtitle Title
    async def set_metadata_sub_title(self, id, metadata_sub_title):
        await self._update_user_field(id, 'metadata_sub_title', metadata_sub_title)

    async def get_metadata_sub_title(self, id):
        user = await self._get_user(id)
        return user.get('metadata_sub_title', '')

    # Clear Metadata
    async def set_clear_metadata(self, id, clear_metadata):
        await self._update_user_field(id, 'clear_metadata', clear_metadata)

    async def get_clear_metadata(self, id):
        user = await self._get_user(id)
        return user.get('clear_metadata', False)
