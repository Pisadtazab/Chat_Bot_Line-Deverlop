import os
import pymongo
from dotenv import load_dotenv
from pymongo import MongoClient


# เข้าถึงตัวแปลในไฟล์ .env เพื่อดึงมาใช้งานในไฟล์ ConnentDB.py แบบ Local
load_dotenv()

mogo_uri = os.getenv("MONGO_URI_LOCAL")
client = MongoClient(mogo_uri)

# Name entity db
db = client["BORC"]
collection = db["UserProfile"]  
collection_BookingOnline = db["BookingOnline"]


# Connect_MongoDB ใช้สำหรับเชื่อมต่อ MongoDB ผ่าน Client URL
def Connect_MongoDB():
    try:
        myclient = pymongo.MongoClient(os.getenv("MONGO_URI_LOCAL"))
        print(collection_BookingOnline)
        print("database is connected")
        return myclient
    except Exception as e:
        print(f"database_local connecting failed: {e}")

if __name__ == "__main__":
    Connect_MongoDB()