# import fitz  # ให้ install PyMuPDF อ่านไฟล์ PDF, ดึงข้อความ
import pymupdf
from PIL import Image
import io
import numpy as np
import requests

from pythainlp.tokenize import word_tokenize  # Added this import

from typing import List, Dict, Tuple

from fixthaipdf import clean

from pymongo.mongo_client import MongoClient
import gridfs  # เก็บที่อยู่รูปภาพ
from dotenv import load_dotenv

import os

from fastapi import APIRouter, HTTPException, UploadFile, File
import shutil




router = APIRouter()

# การเก็บ key
load_dotenv(override=True)


HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

# ✅ [แก้ไข] เปลี่ยน endpoint จาก api-inference.huggingface.co -> router.huggingface.co/hf-inference
# เดิม: https://api-inference.huggingface.co/... -> HF ปิด domain นี้ไปแล้ว (DNS resolve ไม่เจอ / 410 Gone)
EMBED_MODEL_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "BAAI/bge-m3/pipeline/feature-extraction"
)

HF_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

#       เป็น LLM ตัวใหญ่ พร้อมใช้งานแน่นอน ไม่มีปัญหาเรื่อง catalog แบบ HF
from openai import OpenAI

typhoon_client = OpenAI(
    api_key=os.getenv("Typhoon_api_key"),
    base_url="https://api.opentyphoon.ai/v1",
    timeout=45.0,
    max_retries=2,
)

def embed_text(text: str) -> List[float]:
    """
    สร้าง embedding ผ่าน Hugging Face Inference API (BAAI/bge-m3)
    คืนค่า vector 1024 มิติ normalize 
    """
    print("-------------- start embed text (HF API) -------------------")

    payload = text.strip()

    response = requests.post(
        EMBED_MODEL_URL,
        headers=HF_HEADERS,
        json={"inputs": payload},
        timeout=60,
    )

    if response.status_code == 200:
        arr = np.array(response.json(), dtype=np.float32)
        while arr.ndim > 1:          # รองรับทั้ง token-level และ batch
            arr = arr.mean(axis=0)
        norm = np.linalg.norm(arr)
        return (arr / norm).tolist() if norm > 0 else arr.tolist()

    print(f"HF embedding API error: {response.status_code} {response.text}")


def summarize_content(content: str) -> str:
    """
    สรุปเนื้อหา โดยเรียกผ่าน Typhoon API (chat completion)
    แทนการรัน MT5 ในเครื่องหรือเรียกผ่าน HF Inference API
    """
    print("%%%%%%%%%%%%%% SUMMARY %%%%%%%%%%%%%%%%%%%%%")

    if not content or len(content.strip()) < 50:
        print("Content is too short for summarization.")
        return "ไม่สามารถสรุปเนื้อหาได้เนื่องจากเนื้อหาสั้นเกินไป"

    # จำกัดความยาว input กันข้อความยาวเกินไป (กัน token เกิน context window / ค่าใช้จ่ายบาน)
    truncated_content = content[:6000]

    try:
        response = typhoon_client.chat.completions.create(
            model="typhoon-v2.5-30b-a3b-instruct",
            messages=[
                {"role": "system", "content": "คุณเป็นผู้เชี่ยวชาญด้านการสรุปเนื้อหาภาษาไทย สรุปให้กระชับ ครอบคลุมประเด็นสำคัญ ความยาวไม่เกิน 5-8 ประโยค"},
                {"role": "user", "content": f"สรุปเนื้อหาต่อไปนี้:\n\n{truncated_content}"},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        summary = response.choices[0].message.content
    except Exception as e:
        print(f"Typhoon summarization API error: {e}")
        raise HTTPException(502, f"Summarization API error: {e}")

    print(f" summary: {summary}.")
    print("%%%%%%%%%%%%%% SUMMARY %%%%%%%%%%%%%%%%%%%%%")
    return summary


# แยกเนื้อหา, รูป ออกจาก PDF เก็บเป็น list ภายใน chunk เดียวเดียวกัน
def extract_pdf_content(pdf_path: str) -> Tuple[List[Dict], str]:
    """
    แยกข้อความและรูปภาพจาก PDF โดยใช้ PyMuPDF
    คืนค่า: (content_chunks, summarized_text)
    """
    try:
        doc = pymupdf.open(pdf_path)
        content_chunks = []
        all_text = []

        # วนลูป ทีละหน้าของ pdf สร้าง chunk ทีละหน้า
        for page_num in range(len(doc)):
            page = doc[page_num]

            # ทำความสะอาด pdf
            text = clean(page.get_text("text"))

            # Extract text
            all_text.append(f"{text} \n\n\n")

            if not text:
                text = f"ไม่มีข้อความในหน้า {page_num + 1}"

            print("################# Text data ##################")

            # รวบรวมข้อความของหน้า PDF แต่ละหน้า
            chunk_data = {
                "text": f"ข้อมูลจากหน้า {page_num + 1} : {text}",
                "images": [],  # ทำให้รู้ว่า ภาพนี้ มาจากหน้าที่ไหน เก็บภาพใน list
                "page": page_num + 1
            }
            # Extract images
            image_list = page.get_images(full=True)
            print("################# images list ##################")
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # Convert to PIL Image
                try:
                    image = Image.open(io.BytesIO(image_bytes))
                    if image.mode != "RGB":
                        image = image.convert("RGB")

                    # สร้างคำอธิบายรูป
                    img_desc = f"รูปภาพ หน้า {page_num+1} รูปที่ {img_index+1}, บริบท: {text[:80]}..."
                    chunk_data["images"].append({
                        "bytes": image_bytes,
                        "ext": image_ext,
                        "description": img_desc,
                        "page": page_num + 1  # เก็บหมายเลขหน้าที่ chunk นี้อยู่

                    })

                    # เพิ่ม placeholder ใน text
                    chunk_data["text"] += f"\n[ภาพ: pic_{page_num+1}_{img_index+1}.{image_ext}]"

                except Exception as e:
                    print(f"ไม่สามารถประมวลผลรูปภาพที่หน้า {str(page_num+1)}, รูปที่ {str(img_index+1)}: {str(e)}")

            if chunk_data["text"]:
                content_chunks.append(chunk_data)

        doc.close()
        content_text = "".join(all_text)

        # ตัดคำภาษาไทย
        thaitoken_text = preprocess_thai_text(content_text) if any(0x0E00 <= ord(c) <= 0x0E7F for c in content_text) else content_text
        print("################################")
        print(f"{ thaitoken_text }")
        print("################################")

        summary = summarize_content(thaitoken_text)

        return content_chunks, summary

    except Exception as e:
        print("เกิดข้อผิดพลาดในการแยก PDF: %s", str(e))
        raise


# ตัดคำภาษาไทย ก่อนรวมข้อความ
def preprocess_thai_text(text: str) -> str:
    """
    ตัดคำภาษาไทยด้วย pythainlp เพื่อเตรียมข้อความ

    Args:
        text (str): ข้อความภาษาไทย

    Returns:
        str: ข้อความที่ตัดคำแล้ว
    """
    return " ".join(word_tokenize(text, engine="newmm"))


def store_in_mongodb(content_chunks: List[Dict], pdf_name: str):
    """
    เก็บข้อมูลข้อความและรูปภาพใน MogoDb พร้อม embedding
    """
    print("##### Start store in mogodb atlas #########")
    # MongoDB configuration
    mongo_uri = os.getenv("MONGO_URI")
    client = MongoClient(mongo_uri)

    # NameNentity db
    db = client["employee_research_db"]
    collection = db["employees_profiles"]
    data_images = gridfs.GridFS(db)

    print("Connected to MongoDB Atlas")

    for chunk in content_chunks:
        text = chunk["text"]
        images = chunk["images"]
        print("################# Text embeding store ##################")
        text_embedding = embed_text(text)

        print(f"text: {text} ")

        # Store text data
        text_document = {
            "content": text,
            "metadata": {"type": "text", "source": pdf_name, "page": chunk['page']},
            "embedding": text_embedding
        }
        collection.insert_one(text_document)

        print("################# images embeding store ##################")

        print(f"images: {images} ")
        for idx, img in enumerate(chunk["images"], start=1):
            image_uid = f"{pdf_name}__page{chunk['page']}__order{idx}"
            file_id = data_images.put(img["bytes"],
                                       filename=f"{pdf_name}_page{chunk['page']}.{img['ext']}",
                                       content_type=f"image/{'jpeg' if img['ext'].lower() in ('jpg', 'jpeg') else img['ext'].lower()}",
                                       metadata={
                                           "chunk_page": chunk["page"],        # chunk นี้อ้างอิงหน้าไหน
                                           "order": idx,             # ตำแหน่งของรูป
                                           "description": img["description"],  # อธิบายภาพ
                                           "source": pdf_name,                # ไฟล์ต้นทาง
                                           "image_uid": image_uid   #  สำคัญ

                                       }
                                       )

            image_embedding = embed_text(img["description"])
            collection.insert_one({
                "content": img["description"],
                "metadata": {
                    "type": "image",
                    "source": pdf_name,
                    "page": chunk['page'],
                    "order": idx,
                    "gridfs_id": file_id,
                    "image_uid": image_uid
                },
                "embedding": image_embedding
            })


# ดึงตำแหน่งโฟลเดอร์ปัจจุบัน
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
os.makedirs(SRC_DIR, exist_ok=True)  # สร้างโฟลเดอร์ถ้ายังไม่มี


# input ไฟล์ PDF
@router.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")

    save_path = os.path.join(SRC_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # รัน extract และ store ลง MongoDB
    content_chunks, summary = extract_pdf_content(save_path)
    store_in_mongodb(content_chunks, file.filename)

    return {"message": f"{file.filename} uploaded and processed", "summary": summary}