import os

from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv()

mogo_uri_borc = os.getenv("MONGO_URI_BORC")
client = MongoClient(mogo_uri_borc)

db = client["BORC"]
collection = db["UserProfile"]
collection_BookingOnline = db["BookingOnline"]
