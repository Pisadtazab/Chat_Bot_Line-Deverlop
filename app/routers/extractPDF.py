import fitz  # ให้ install PyMuPDF อ่านไฟล์ PDF, ดึงข้อความ
from PIL import Image
import io
import numpy as np
import unicodedata # Added for unicodedata.normalize
from pythainlp.tokenize import word_tokenize # Added this import

from typing import List, Dict, Tuple  # ✅ [แก้ไข] เพิ่ม Tuple สำหรับ return type ของ extract_pdf_content
import torch #ใช้กับโมเดลสรุปข้อความ
from transformers import T5Tokenizer, MT5ForConditionalGeneration #สรุปข้อความ (summarization)

from fixthaipdf import clean

from sentence_transformers import SentenceTransformer
from pymongo.mongo_client import MongoClient
from pymongo.operations import SearchIndexModel
import gridfs #เก็บที่อยู่รูปภาพ
from dotenv import load_dotenv


import os

from fastapi import APIRouter ,HTTPException,UploadFile, File
import shutil




router = APIRouter()

# การเก็บ key
load_dotenv(override=True)


# ใช้การด์จอ
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(" Using device:", device)


# ✅ [แก้ไข] โหลด SentenceTransformer ครั้งเดียวตอนเริ่มโปรแกรม แทนที่จะโหลดซ้ำทุกครั้งที่เรียก embed_text
# เดิม: โหลดในฟังก์ชัน embed_text ทำให้โหลดโมเดลใหม่ทุก call → ช้ามาก และเปลือง memory
MODEL_NAME = "BAAI/bge-m3"
sentence_model = SentenceTransformer(MODEL_NAME, device=device)


# ใช้แปลงข้อความ เป็น token
sum_tokenizer = T5Tokenizer.from_pretrained('StelleX/mt5-base-thaisum-text-summarization')

# โมเดลที่รับข้อความ (sequence หนึ่ง) แล้วสร้างข้อความใหม่ (อีก sequence หนึ่ง) หรือ การแปลงจาก token มาเป็นข้อความใหม่
sum_model = MT5ForConditionalGeneration.from_pretrained('StelleX/mt5-base-thaisum-text-summarization').to(device)


def summarize_content(content: str) -> str:
    """
        สรุปเนื้อหา
    """
    print("%%%%%%%%%%%%%% SUMMARY %%%%%%%%%%%%%%%%%%%%%")

    # Check if content is empty or too short
    if not content or len(content.strip()) < 50: # Arbitrary minimum length
        print("Content is too short for summarization.")
        return "ไม่สามารถสรุปเนื้อหาได้เนื่องจากเนื้อหาสั้นเกินไป"

    # ขั้นตอนเตรียมข้อความให้โมเดลสรุป
    # Ensure input_ids are within the model's max length
    input_ = sum_tokenizer(content, truncation=True, max_length=1024, return_tensors="pt")
    # PyTorch ใช้เพื่อ บอกว่าเราไม่ต้องคำนวณ gradient ต้องการดูผลลัพธ์ ข้อดีไม่เปลือง memery
    with torch.no_grad():
      # สร้างข้อความใหม่
        preds = sum_model.generate(
            input_['input_ids'].to(device), #token ของข้อความ input, ส่งไปยัง CPU
            # ✅ [แก้ไข] เพิ่ม attention_mask เพื่อให้โมเดลรู้ว่า token ไหนควรสนใจ
            # เดิม: ไม่ได้ส่ง attention_mask ทำให้โมเดลอาจ attend ไปที่ padding token ด้วย
            attention_mask=input_['attention_mask'].to(device),
            num_beams=15,  # ค้นหา sequence ที่ดีที่สุดโดยพิจารณา 4 ทางเลือกพร้อมกัน (จำนวนมากขึ้น → แม่นขึ้นแต่ช้า)
            num_return_sequences=1, # โมเดลจะ generate แค่ 1 ข้อความสรุป
            no_repeat_ngram_size=3, # ป้องกัน ซ้ำคำ/วลี 3 ตัวติดกัน ในสรุป
            remove_invalid_values=True, # ลบค่า token หรือผลลัพธ์ที่โมเดลสร้างไม่ถูกต้องออก
            max_length=300, # ปรับความยาวสรุปข้อความ จำกัดจำนวน token ของ ข้อความสรุป สูงสุด 500 token
            early_stopping=True # ถ้าโมเดลพบ token end-of-sequence จะหยุด generate ทันที ไม่ต้องรอจนเต็ม max_length
        )

    summary = sum_tokenizer.decode(preds[0], skip_special_tokens=True)

    print(f" summary: {summary}.")
    print("%%%%%%%%%%%%%% SUMMARY %%%%%%%%%%%%%%%%%%%%%")
    return summary


# แยกเนื้อหา, รูป ออกจาก PDF เก็บเป็น list ภายใน chunk เดียวเดียวกัน
# ✅ [แก้ไข] เปลี่ยน return type เป็น Tuple[List[Dict], str] เพื่อ return ทั้ง chunks และ summary
# เดิม: ใช้ global variable "summarize" ซึ่งเป็น anti-pattern
def extract_pdf_content(pdf_path: str) -> Tuple[List[Dict], str]:
    """
    แยกข้อความและรูปภาพจาก PDF โดยใช้ PyMuPDF
    คืนค่า: (content_chunks, summarized_text)
    """
    try:
        doc = fitz.open(pdf_path)
        content_chunks = []
        all_text=[]

        # วนลูป ทีละหน้าของ pdf สร้าง chunk ทีละหน้า
        for page_num in range(len(doc)):
            page = doc[page_num]

            # ทำความสะอาด pdf
            text = clean(page.get_text("text"))


            # Extract text
            # text = page.get_text("text").strip()
            all_text.append(f"{text} \n\n\n")

            if not text:
                text = f"ไม่มีข้อความในหน้า {page_num + 1}"

            print("################# Text data ##################")

            # Simplified chunk_data creation
            # chunk_data = {"text": f"ข้อมูลจากหน้า {page_num + 1} : {text}" , "images": []}
            # รวบรวมข้อความของหน้า PDF แต่ละหน้า
            chunk_data = {
                  "text": f"ข้อมูลจากหน้า {page_num + 1} : {text}",
                  "images": [], #ทำให้รู้ว่า ภาพนี้ มาจากหน้าที่ไหน เก็บภาพใน list
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
        content_text= "".join(all_text)

        # ตัดคำภาษาไทย
        # Added a check for Thai characters before tokenizing
        thaitoken_text = preprocess_thai_text(content_text) if any(ord(c) >= 0x0E00 and ord(c) <= 0x0E7F for c in content_text) else content_text
        print("################################")
        print(f"{ thaitoken_text }")
        print("################################")

        # ✅ [แก้ไข] เปลี่ยนจาก global variable มาเป็น local variable แล้ว return ออกไปแทน
        # เดิม: global summarize = summarize_content(thaitoken_text) → ใช้ global ใน function เป็น anti-pattern
        summarize = summarize_content(thaitoken_text)

        # ✅ [แก้ไข] return ทั้ง content_chunks และ summarize ออกไปพร้อมกัน
        return content_chunks, summarize

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


def embed_text(text: str) -> np.ndarray:
    """
    สร้าง embedding สำหรับข้อความโดยใช้ SentenceTransformer

    Args:
        text (str): ข้อความที่ต้องการสร้าง embedding

    Returns:
        np.ndarray: Embedding vector ที่รวมจากหลายโมเดล
    """
    print("-------------- start embed text  -------------------")

    # ตัดคำภาษาไทย
    processed_text = preprocess_thai_text(text) if any(ord(c) >= 0x0E00 and ord(c) <= 0x0E7F for c in text) else text

    # เรียกใช้ model embedding
    # ✅ [แก้ไข] ลบการโหลด SentenceTransformer ออกจากฟังก์ชันนี้
    # เดิม: MODEL_NAME = "BAAI/bge-m3" และ sentence_model = SentenceTransformer(MODEL_NAME, device=device)
    #        อยู่ในฟังก์ชันนี้ ทำให้โหลดโมเดลใหม่ทุกครั้งที่เรียก → ช้าและเปลือง memory
    # ใหม่: ใช้ sentence_model ที่โหลดไว้แล้ว 1 ครั้งตอนต้นไฟล์ (global scope)

    # สร้าง embedding ด้วย SentenceTransformer
    # The 'device' variable is not defined globally. Assuming it should be 'cpu' for general use.
    sentence_embedding = sentence_model.encode(processed_text, normalize_embeddings=True)

    return sentence_embedding


def store_in_mongodb(content_chunks: List[Dict], pdf_name: str):
    """
    เก็บข้อมูลข้อความและรูปภาพใน MogoDb พร้อม embedding
    """
    print("##### Start store in mogodb atlas #########")
     # MongoDB configuration
    mogo_uri = os.getenv("MONGO_URI")
    client = MongoClient(mogo_uri )

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
            "embedding": text_embedding.tolist()
        }
        collection.insert_one(text_document)

        print("################# images embeding store ##################")

        print(f"images: {images} ")
       # เก็บ images ลงฐานข้อมล Mongo db ไม้ได้นำรูปภาพมาแปลงเป็น vector
       # idx คือ คือเลขลำดับประกอบกับรูปภาพในรูปแบบ list จะเริ่มนับจาก index 1
        for  idx, img in enumerate(chunk["images"], start=1):
            # image_uid ทำหน้าที่เป็นรหัสเฉพาะของรูปภาพ 1 รูป ในระบบทั้งหมด เพื่อคุมตัว หน้าที่เท่าไหร่(page) และ รูปภาพที่เท่าไหร่(order) ไม่ชนกัน
            image_uid = f"{pdf_name}__page{chunk['page']}__order{idx}"
            file_id = data_images.put(img["bytes"],
            filename = f"{pdf_name}_page{chunk['page']}.{img['ext']}",
            content_type = "image/jpeg",
                      metadata={
                                "chunk_page": chunk["page"],        # chunk นี้อ้างอิงหน้าไหน
                                "order": idx,             # ตำแหน่งของรูป
                                "description": img["description"], # อธิบายภาพ
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
                "embedding": image_embedding.tolist()
            })


# ดึงตำแหน่งโฟลเดอร์ปัจจุบัน
# current_dir = os.path.dirname("CHATBOT-LINE")

# # เชื่อมเข้าไปที่ src/FoodMenu.pdf
# pdf_path = os.path.join(current_dir, "src", "FoodMenu.pdf")
# import os

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
os.makedirs(SRC_DIR, exist_ok=True)  # สร้างโฟลเดอร์ถ้ายังไม่มี
# # ✅ [แก้ไข] pdf_path เปลี่ยนเป็น SRC_DIR ชี้แค่โฟลเดอร์ src/ ไม่ชี้ไฟล์ใดไฟล์หนึ่ง
# # เดิม: pdf_path ชี้ไปที่ไฟล์ PDF โดยตรง → ถ้าไม่มีไฟล์จะ error ตอน import


# เอาไว้ test pdf โดยเฉพาะ
# try:
#     pdf_content = extract_pdf_content(pdf_path)
#     print("\nExtracted Content Chunks:")
#     # Print a summary or part of the extracted content for verification
#     for i, chunk in enumerate(pdf_content[:3]): # Print first 3 chunks
#         print(f"Chunk {i+1}: Text length = {len(chunk['text'])}, Images = {len(chunk['images'])}")

#         # print(f"Text: {chunk['text'][:300]}...") # Print first 200 chars of text
#     print(f"\nSummarized Content: {summarize}")

#     # Embed the summarized content and store it in a global variable to be printed
#     global document_embedding # Declare document_embedding as global
#     document_embedding = embed_text(summarize)
#     print(f"\nEmbedding of summarized content: {document_embedding}")

# except FileNotFoundError:
#     print(f"Error: PDF file not found at {pdf_path}")
# except Exception as e:
#     print(f"An error occurred during PDF processing: {e}")
#     raise

# ✅ [แก้ไข] ลบ mogodb_store ออกจาก global scope
# เดิม: mogodb_store = store_in_mongodb(pdf_content, pdf_path) → รันทันทีตอน import
#        ถ้าไม่มี pdf_content (เพราะ try block ถูก comment ออก) จะ NameError
#        และถ้า pdf ไม่มีอยู่จริง server จะ start ไม่ได้เลย
# ใหม่: การ store จะเกิดขึ้นใน /upload_pdf endpoint เท่านั้น

#บันทึกลงฐานข้อมูล
# mogodb_store = store_in_mongodb(pdf_content, pdf_path)
# print(f"\nStoring in MongoDB : {mogodb_store}")


# input ไฟล์ PDF
@router.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")

    # ✅ ใช้ SRC_DIR แทน BASE_DIR + "../src" เพื่อความสะอาด
    save_path = os.path.join(SRC_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # รัน extract และ store ลง MongoDB
    # ✅ [แก้ไข] รับค่า 2 ตัวจาก extract_pdf_content (content_chunks, summarize)
    pdf_content, summarize = extract_pdf_content(save_path)
    store_in_mongodb(pdf_content, file.filename)

    return {"message": f"{file.filename} uploaded and processed"}

# @router.get("/list_files")
# async def list_files():
#     collection = get_db()
#     # ดึงรายชื่อไฟล์ที่ unique จาก MongoDB
#     sources = collection.distinct("metadata.source")
#     return {"files": sources}