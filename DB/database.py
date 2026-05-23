from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
import os
from dotenv import load_dotenv
from bson.errors import InvalidId

import re

load_dotenv(override=True)


# MongoDB configuration MONGO_URI
mogo_uri = os.getenv("MONGO_URI")
client = MongoClient(mogo_uri )

# Name entity db
db = client["employee_research_db"]
collection = db["employees_profiles"]  

# def get_db():
#      # return collection ตรงๆ เลย ไม่ต้องสร้าง function แยก
#     return db


def delete_pdf_from_db(db, pdf_name: str):
    """ ฟังก์ชั่นการจัดการลบไฟล์ pdf ทั้งข้อความและรูปภาพ """
    fs = gridfs.GridFS(db)
     # ค้นหาแบบ regex เผื่อ path นำหน้า เช่น /content/FoodMenu.pdf
    pattern = re.compile(re.escape(pdf_name), re.IGNORECASE)
    # 1. ตรวจสอบว่ามีไฟล์นี้อยู่ไหม (ค้นจาก text หรือ image ก็ได้)
    any_doc = collection.find_one({"metadata.source": pdf_name})
    if not any_doc:
        raise ValueError(f"ไม่พบไฟล์ '{pdf_name}' ใน database")

    # ใช้ source จริงที่เจอใน database
    actual_source = any_doc["metadata"]["source"]

    # 2. ดึง gridfs_id ทั้งหมดจาก document ที่เป็น type: image
    image_docs = db["employees_profiles"].find({
        "metadata.source": pdf_name,
        "metadata.type": "image",
        "metadata.gridfs_id": {"$exists": True}
    })

    gridfs_ids = [doc["metadata"]["gridfs_id"] for doc in image_docs]

    # 3. ลบไฟล์รูปภาพออกจาก GridFS ทีละ id
    for gid in gridfs_ids:
        try:
            obj_id = ObjectId(str(gid))
            if fs.exists(obj_id):
                fs.delete(obj_id)
            # ลบ orphaned chunks
            db["fs.chunks"].delete_many({"files_id": obj_id})
        except Exception as e:
            print(f"ลบ GridFS id {gid} ไม่สำเร็จ: {e}")

    # 4. ลบ document ทั้งหมด (ทั้ง text และ image) ออกจาก employees_profiles
    db["employees_profiles"].delete_many({"metadata.source": actual_source})