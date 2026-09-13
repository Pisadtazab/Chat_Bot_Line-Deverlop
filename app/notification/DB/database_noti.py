import os

from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv()

mogo_uri_locl = os.getenv("MONGO_URI_LOCAL")
client = MongoClient(mogo_uri_locl)

db = client["BORC"]
collection = db["UserProfile"]
collection_BookingOnline = db["BookingOnline"]
