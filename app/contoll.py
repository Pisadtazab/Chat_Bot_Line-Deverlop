from pymongo import MongoClient
from gridfs import GridFS

from dotenv import load_dotenv
import os


# การเก็บ key
load_dotenv(override=True)


# MongoDB configuration MONGO_URI
mogo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)

# Name entity db
db = client["employee_research_db"]
collection = db["employees_profiles"]   


fs = GridFS(db)

test = db.collection.find_one({ "metadata.type": "image" })
print(test)


# จัดเก็บไฟล์ PDF จะอยู่ใน source
# ตัวอย่างไฟล์ = "/content/FoodMenu.pdf"
# ใส่ชื่อ PDF ที่ต้องการลบ ต้องเป็นชื่อในฐานข้อมูลเท่านั้น

# pdf_name = "/content/10RicherInthai2024.pdf" 

# files = db.fs.files.find({"metadata.source": pdf_name})

# files_text = db.collection.delete_many({"metadata.source":pdf_name})
# print (f"ลบข้อความเสร็จแล้ว{files_text}")
# print("ลบข้อความ:", files_text.deleted_count)

# count = 0
# for f in files:
#     fs.delete(f["_id"])   # ลบทั้ง files + chunks
#     print("ลบรูป:", f["filename"])
#     count += 1


# print("ลบข้อความ:", files_text.deleted_count)   
# print("ลบรูปทั้งหมด:", count)

# print(collection.find_one())
# อันนี้คือทดลอง
