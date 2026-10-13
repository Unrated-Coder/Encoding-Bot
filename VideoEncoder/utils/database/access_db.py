

from ... import database, session, mongo_uri
from .database import Database

db = Database(mongo_uri, database)
