
from os import getenv
import logging
import os
import time
from io import BytesIO, StringIO
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
import hydrogram as hydrogram
from hydrogram import Client

botStartTime = time.time()

if os.path.exists('config.env'):
    load_dotenv('config.env')

# Variables & Default Fallbacks

raw_api_id = getenv("API_ID", "0")
api_id = int(raw_api_id) if raw_api_id and raw_api_id.isdigit() else 0
api_hash = getenv("API_HASH", "")
bot_token = getenv("BOT_TOKEN", "")

mongo_uri = getenv("MONGO_URI", "mongodb://localhost:27017/VideoEncoder")
database = "VideoEncoder"
session = getenv("SESSION_NAME", "VideoEncoder")

drive_dir = getenv("DRIVE_DIR", "drive")
index = getenv("INDEX_URL", "")

download_dir = getenv("DOWNLOAD_DIR", "downloads")
encode_dir = getenv("ENCODE_DIR", "encode")

owner = list(set(int(x) for x in getenv("OWNER_ID", "").split() if x.strip('-').isdigit())) if getenv("OWNER_ID") else []
sudo_users = list(set(int(x) for x in getenv("SUDO_USERS", "").split() if x.strip('-').isdigit())) if getenv("SUDO_USERS") else []
everyone = list(set(int(x) for x in getenv("EVERYONE_CHATS", "").split() if x.strip('-').isdigit())) if getenv("EVERYONE_CHATS") else []
all = everyone + sudo_users + owner

log_env = getenv("LOG_CHANNEL")
if log_env and (log_env.strip('-').isdigit() or log_env.startswith('@')):
    log = int(log_env) if log_env.strip('-').isdigit() else log_env
else:
    log = owner[0] if owner else 0


data = []

PROGRESS = """├ ꜱɪᴢᴇ › <code>{0} / {1}</code>
├ ꜱᴘᴇᴇᴅ › <code>{2}</code>
╰ ᴇᴛᴀ › <code>{3}</code>"""

video_mimetype = [
    "video/x-flv",
    "video/mp4",
    "application/x-mpegURL",
    "video/MP2T",
    "video/3gpp",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-ms-wmv",
    "video/x-matroska",
    "video/webm",
    "video/x-m4v",
    "video/quicktime",
    "video/mpeg"
]

def memory_file(name=None, contents=None, *, bytes=True):
    if isinstance(contents, str) and bytes:
        contents = contents.encode()
    file = BytesIO() if bytes else StringIO()
    if name:
        file.name = name
    if contents:
        file.write(contents)
        file.seek(0)
    return file

# Check Folder
if not os.path.isdir(download_dir):
    os.makedirs(download_dir)
if not os.path.isdir(encode_dir):
    os.makedirs(encode_dir)

if not os.path.isdir('VideoEncoder/utils/extras'):
    os.makedirs('VideoEncoder/utils/extras')

# the logging things
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(
            'VideoEncoder/utils/extras/logs.txt',
            backupCount=20,
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)

logging.getLogger("hydrogram").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

# Client
app = Client(
    session,
    bot_token=bot_token,
    api_id=api_id,
    api_hash=api_hash,
    plugins={'root': os.path.join(__package__, 'plugins')},
    sleep_threshold=30,
    workers=min(32, (os.cpu_count() or 4) * 4),
    max_concurrent_transmissions=10,
    ipv6=False)
