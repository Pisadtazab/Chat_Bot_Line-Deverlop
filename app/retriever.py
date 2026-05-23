
# from pymongo.mongo_client import MongoClient
# from pymongo.operations import SearchIndexModel
from gridfs import GridFS
from fastapi import HTTPException
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
from PIL import Image
# import io
import numpy as np
from pythainlp.tokenize import word_tokenize # Added this import
from bson.objectid import ObjectId
from openai import OpenAI
import re
# import time


# from linebot.models import ImageSendMessage
# from linebot import LineBotApi
from linebot.v3.messaging import ImageMessage

from linebot.v3.messaging import TextMessage
import os
from dotenv import load_dotenv

from app.promrt_typhoon import DOCUMENT_SYSTEM_PROMPT

# การเก็บ key
load_dotenv(override=True)

# MongoDB configuration
mogo_uri = os.getenv("MONGO_URI")
client = MongoClient(mogo_uri )

# Name entity db
db = client["employee_research_db"]
collection = db["employees_profiles"]   
print("Connected to MongoDB Atlas")



# --- Embed query ---
MODEL_NAME = "BAAI/bge-m3"
sentence_model = SentenceTransformer(MODEL_NAME)


import time
import threading

REQUEST_INTERVAL = 0.25  # 4 request / sec
last_request_time = 0
rate_lock = threading.Lock()

def wait_for_rate_limit():
    """ เช็คว่า ยิง api ตอนไหน
        ถ้าไม่ถึง 2.5 วิ ต้องรอให้ครบถึงจะส่ง
        เป็นการจัดการเวลา การเข้า api ให้มีการ delay
    """
    global last_request_time
    
    with rate_lock:
        now = time.time()
        diff = now - last_request_time

        if diff < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - diff)

        last_request_time = time.time()

def query_rag(query_text):
    """
    ทำ RAG โดยค้นหา embedding จาก MongoDB VectorSearch
    และเตรียม context + รูปภาพ ส่งออกเป็น prompt ให้ LLM ใช้ต่อ
    """

    print("####  RAG get Question #### ")

    # MongoDB configuration
    mogo_uri = os.getenv("MONGO_URI")
    client = MongoClient(mogo_uri )

    # Name entity db
    db = client["employee_research_db"]
    collection = db["employees_profiles"]   
    print("Connected to MongoDB Atlas")

    # --- 1) สร้าง embedding ของคำถาม ---
    question_embedding = sentence_model.encode(query_text).tolist()

    # --- 2) กำหนดจำนวนผลลัพธ์ตามคำถาม ---
    max_result = 3
    
    if "กี่" in query_text or "บ้าง" in query_text:
        max_result = 5
    if "ทั้งหมด" in query_text:
        max_result = 10

    
    # --- 3) MongoDB vector search ---
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": question_embedding,
                "numCandidates": 100,
                "limit": max_result
            }
        },
        {
            "$project": {
                "content": 1,
                "metadata": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]

    results = list(collection.aggregate(pipeline))
    

    print("#### Vector Search Results ####")
    if not results:
        print("No matching results found.")
        return "ไม่พบข้อมูลที่เกี่ยวข้อง",None
    
      # ข้อความที่คะแนนสูงสุด → บอกว่า PDF ไหนเกี่ยวที่สุด
    top_result = results[0]
    # หน้าที่อธิบาย ระบุ PDF บอกว่า context มาจากไฟล์ไหน current_pdf_name
    current_pdf_name = top_result["metadata"].get("source")
    
    # --- 4) รวม context และค้นหารูป ---
    context_texts = []
  

    for r in results:
        content = r["content"]
        metadata = r.get("metadata", {})

        context_texts.append(content)
        
        
    # --- 5) รวม context ---
    context = "\n".join(context_texts)


#3️⃣ สร้าง prompt สำหรับ Typhoon
    prompt = f"""จากบริบทต่อไปนี้ ตอบคำถาม: {query_text}
    # บริบท:
    # {context}
    # หากมีชื่อไฟล์รูปภาพต้องให้แสดงคำอธิบายหรือ placeholder ของภาพ ให้ต่อสุดท้าย"""  #สั่งให้โชว์รูปภาพที่เกี่ยวข้องกับบริบท

    typhoon_client = OpenAI(
        api_key= os.getenv("Typhoon_api_key"),
        base_url="https://api.opentyphoon.ai/v1"
    )
    
    # เรียกใช้ฟังก์ชั่น ระยะเวลารอ api
    wait_for_rate_limit()

    response = typhoon_client.chat.completions.create(
    model="typhoon-v2.5-30b-a3b-instruct",
    messages=[
        {"role": "system", "content": f"คุณเป็นผู้ให้คำแนะนำปรึกษา ค่อยช่วยเหลือในขอบเขตที่ทำได้ {DOCUMENT_SYSTEM_PROMPT}"},
        {"role": "user", "content":  prompt}
    ],
    temperature=0.7,
    max_tokens=10000,
    top_p=0.9,
    presence_penalty=0.6 # alternative
)

    llm_answer = response.choices[0].message.content
    return llm_answer,current_pdf_name


#  ข้อความการตอบของ  AI ส่งผ่านไลน์
def respone_message_LLM(llm_answer):
    if llm_answer is None or llm_answer == "":
        llm_answer = "ขออภัย ระบบไม่สามารถตอบคำถามได้ในตอนนี้ 🙇‍♂️"
    return TextMessage(text=llm_answer)


 
# ขั้นตอนการ ดึง id gridfs เพื่อเอาไปเชื่อง api

def extract_image_filenames(llm_answer):
    """
    ดึงชื่อไฟล์ภาพจากคำตอบ LLM
    รองรับ:
    pic-1-1.jpeg
    Pic_1_1.jpeg
    pic_1_1.JPG
    """

    pattern = r"(pic[-_]?\d+[-_]?\d+\.(?:jpe?g|png))"

    files = re.findall(pattern, str(llm_answer), flags=re.IGNORECASE)

    return files


def parse_page_order(files: str):
    
    """ แปลงชื่อไฟล์รูป เช่น pic_1_1.jpeg
        ให้เป็น (page, order)
    """
   
    numbers = re.findall(r"\d+", files)

    if len(numbers) < 2:
        return None, None

    page = int(numbers[0])
    order = int(numbers[1])

    return page, order

def id_image(llm_answer, collection,current_pdf_name):
       
    #กัน eror หารูปภาพ pdf ไม่เจอ
    if not current_pdf_name:
        return []
    
    filenames = extract_image_filenames(llm_answer)
    gridfs_ids = []

    for fname in set(filenames):
        page, order = parse_page_order(fname)
        if page is None or order is None:
            continue

        image_uid = f"{current_pdf_name}__page{page}__order{order}"

        doc = collection.find_one({
            "metadata.type": "image",
            "metadata.image_uid": image_uid
        })

        if doc and "gridfs_id" in doc["metadata"]:
            gridfs_ids.append(doc["metadata"]["gridfs_id"])
 
    return gridfs_ids





def send_image(gridfs_ids):
    """ส่งรูปภาพผ่านไลน์ด้วย push"""
    
    ngrok_uri = os.getenv("NGROK_URL")  

    try:
        if not ngrok_uri:
            raise ValueError("NGROK_URI not set")

        # ถ้า env มี https อยู่แล้วจะไม่ซ้ำ
        if not ngrok_uri.startswith("http"):
            base_url = f"https://{ngrok_uri}"
        else:
            base_url = ngrok_uri

        images = []

        for file_id in gridfs_ids:
            url = f"{base_url}/image/{file_id}"

            images.append(
                ImageMessage(
                    original_content_url=url,
                    preview_image_url=url
                )
            )

        return images
    except Exception as e:
        print("ไม่มีรูปภาพส่ง")
