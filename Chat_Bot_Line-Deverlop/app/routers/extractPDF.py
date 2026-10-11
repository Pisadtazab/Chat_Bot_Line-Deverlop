# import fitz  # ให้ install PyMuPDF อ่านไฟล์ PDF, ดึงข้อความ
import pymupdf
from PIL import Image
import io
import logging
import numpy as np
import requests
import tempfile

from pythainlp.tokenize import word_tokenize  # Added this import

from typing import List, Dict, Tuple

from fixthaipdf import clean

from dotenv import load_dotenv

import os

from fastapi import APIRouter, HTTPException, UploadFile, File
from starlette.concurrency import run_in_threadpool
from app.DB.database import collection
from app.services.cloudinary import upload_image




router = APIRouter()
MAX_PDF_BYTES = 50 * 1024 * 1024
logger = logging.getLogger(__name__)

# การเก็บ key
load_dotenv(override=True)


HF_TOKEN = os.getenv("CLOUDFLARE_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

# ✅ [แก้ไข] เปลี่ยน endpoint จาก api-inference.huggingface.co -> router.huggingface.co/hf-inference
# เดิม: https://api-inference.huggingface.co/... -> HF ปิด domain นี้ไปแล้ว (DNS resolve ไม่เจอ / 410 Gone)
# EMBED_MODEL_URL = (
#    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/baai/bge-m3"
# )

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

    if not HF_TOKEN:
        raise HTTPException(503, "Missing HUGGINGFACE_TOKEN")

    try:
        response = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/baai/bge-m3",
            headers=HF_HEADERS,
            json={"text": [payload]},
            timeout=60,
        )
        response.raise_for_status()
        arr = np.array(response.json(), dtype=np.float32)
        while arr.ndim > 1:          # รองรับทั้ง token-level และ batch
            arr = arr.mean(axis=0)
        norm = np.linalg.norm(arr)
        return (arr / norm).tolist() if norm > 0 else arr.tolist()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        detail = exc.response.text[:300] if exc.response is not None else str(exc)
        logger.error("CLOUDFLARE embedding request returned %s: %s", status, detail)
        raise HTTPException(502, "Embedding API returned an error") from exc
    except requests.RequestException as exc:
        logger.exception("CLOUDFLARE embedding request failed")
        raise HTTPException(502, "Embedding API request failed; check server logs") from exc
    except (ValueError, TypeError) as exc:
        logger.exception("CLOUDFLARE returned an invalid embedding response")
        raise HTTPException(502, "Invalid embedding response") from exc


def summarize_content(content: str) -> str:
    """
    สรุปเนื้อหา โดยเรียกผ่าน Typhoon API (chat completion)
    แทนการรัน MT5 ในเครื่องหรือเรียกผ่าน HF Inference API
    """
    if not content or len(content.strip()) < 50:
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
    except Exception as exc:
        logger.exception("Typhoon summarization failed")
        raise HTTPException(502, "Summarization API failed") from exc

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
            reference_urls = list(dict.fromkeys(
                link["uri"]
                for link in page.get_links()
                if link.get("uri", "").startswith(("https://", "http://"))
            ))
            if reference_urls:
                chunk_data["text"] += "\nลิงก์อ้างอิง: " + " ".join(reference_urls)

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
        logger.info("PDF text extracted (%d characters)", len(thaitoken_text))

        summary = summarize_content(thaitoken_text)
        return content_chunks, summary

    except Exception:
        logger.exception("Unable to extract PDF content")
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
    for chunk in content_chunks:
        text = chunk["text"]
        images = chunk["images"]
        text_embedding = embed_text(text)

        # Store text data
        text_document = {
            "content": text,
            "metadata": {"type": "text", "source": pdf_name, "page": chunk['page']},
            "embedding": text_embedding
        }
        collection.insert_one(text_document)

        logger.info("Storing PDF page %s with %d images", chunk["page"], len(images))
        for idx, img in enumerate(chunk["images"], start=1):
            image_uid = f"{pdf_name}__page{chunk['page']}__order{idx}"
            image_url = upload_image(
                image_bytes=img["bytes"],
                public_id=image_uid,
                folder="hms-rag/pdf-images",
            )

            image_embedding = embed_text(img["description"])

            image_document = {
                "content": img["description"],

                "metadata": {
                    "type": "image",
                    "source": pdf_name,
                    "page": chunk["page"],
                    "order": idx,
                    "image_uid": image_uid,
                    "image_url": image_url,
                    "image_description": img["description"],
                },

                "embedding": image_embedding,
            }

            collection.insert_one(image_document)

# ดึงตำแหน่งโฟลเดอร์ปัจจุบัน
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
os.makedirs(SRC_DIR, exist_ok=True)  # สร้างโฟลเดอร์ถ้ายังไม่มี


# input ไฟล์ PDF
@router.post("/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    filename = os.path.basename((file.filename or "").replace("\\", "/"))
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")

    with tempfile.NamedTemporaryFile(dir=SRC_DIR, suffix=".pdf", delete=False) as temp_file:
        save_path = temp_file.name

    try:
        size = 0
        with open(save_path, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    raise HTTPException(413, "PDF exceeds the 50 MB limit")
                output.write(chunk)

        with open(save_path, "rb") as uploaded_pdf:
            if not uploaded_pdf.read(5).startswith(b"%PDF-"):
                raise HTTPException(400, "Invalid PDF file")

        content_chunks, summary = await run_in_threadpool(extract_pdf_content, save_path)
        await run_in_threadpool(store_in_mongodb, content_chunks, filename)
        return {"message": f"{filename} uploaded and processed", "summary": summary}
    finally:
        os.remove(save_path)
