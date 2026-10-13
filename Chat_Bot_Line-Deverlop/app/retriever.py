import logging
import os
import threading
import time

from dotenv import load_dotenv
from linebot.v3.messaging import ImageMessage, TextMessage
from openai import OpenAI

from app.DB.database import collection
from app.promrt_typhoon import DOCUMENT_SYSTEM_PROMPT
from app.routers.extractPDF import embed_text


# โหลด environment variables
load_dotenv(override=True)


# Hugging Face Embedding

REQUEST_INTERVAL = 0.25  # 4 requests / second

last_request_time = 0
rate_lock = threading.Lock()

logger = logging.getLogger(__name__)



MAX_CONTEXT_RESULTS = 8
DEFAULT_CONTEXT_RESULTS = 4
MAX_LINE_TEXT_LENGTH = 4_800
EXTENDED_QUERY_TERMS = (
    "ทั้งหมด",
    "ทุกคน",
    "ทุกอาจารย์",
    "รายชื่อ",
    "มีใครบ้าง",
    "ละเอียด",
    "อธิบาย",
    "เปรียบเทียบ",
    "สรุป",
)


# Typhoon Client

typhoon_client = OpenAI(
    api_key=os.getenv("Typhoon_api_key"),
    base_url="https://api.opentyphoon.ai/v1",
    timeout=45.0,
    max_retries=2,
)


# Rate Limit Function

def wait_for_rate_limit():
    """
    ควบคุมระยะเวลาการเรียก API
    เพื่อไม่ให้ยิง request ถี่เกินไป
    """

    global last_request_time

    with rate_lock:
        now = time.time()
        diff = now - last_request_time

        if diff < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - diff)

        last_request_time = time.time()

# RAG
import json
import re


def query_rag(query_text):
    """
    ทำ RAG โดย

    1. สร้าง embedding จากคำถาม
    2. ค้นหาข้อมูลจาก MongoDB Vector Search
    3. สร้าง context พร้อม image_url จาก MongoDB
    4. ส่ง context ให้ Typhoon
    5. ให้ LLM เลือก image_urls ที่เกี่ยวข้อง
    6. ตรวจสอบว่า image_urls ที่ LLM เลือก
       มีอยู่จริงใน MongoDB context
    7. ส่ง image_urls กลับไป

    Returns:
        tuple:
            llm_answer
            current_pdf_name
            image_results
    """

    print("#### RAG get Question ####")

    needs_extended_answer = any(
        term in query_text for term in EXTENDED_QUERY_TERMS
    )
    question_embedding = embed_text(query_text)

    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index2",
                "path": "embedding",
                "queryVector": question_embedding,
                "numCandidates": 80,
                "limit": (
                    MAX_CONTEXT_RESULTS
                    if needs_extended_answer
                    else DEFAULT_CONTEXT_RESULTS
                ),
            }
        },  
        {
            "$project": {
                "content": 1,
                "metadata": 1,
                "score": {
                    "$meta": "vectorSearchScore"
                }
            }
        }
    ]

    results = list(collection.aggregate(pipeline))

    print("#### Vector Search Results ####")
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata", {}) or {}
        print(
            f"[{index}] score={result.get('score')} "
            f"type={metadata.get('type')} source={metadata.get('source')} "
            f"page={metadata.get('page')} content={(result.get('content') or '')[:200]!r}"
        )
        if metadata.get("type") == "image":
            print(f" image_url={metadata.get('image_url')}")

    if not results:
        print("No matching results found.")

        return (
            "ไม่พบข้อมูลที่เกี่ยวข้อง",
            None,
            []
        )

    # สร้าง context
    context_parts = []

    for index, result in enumerate(results, start=1):

        metadata = result.get("metadata", {}) or {}
        content = result.get("content", "") or ""

        image_url = metadata.get("image_url")
        source = metadata.get("source", "")

        part = f"""[ข้อมูลที่ {index} | เอกสาร: {source}]
{content}"""

        if image_url:
            part += f"""image_url: {image_url}"""

        context_parts.append(part)

    context = "\n\n".join(context_parts)

    # Current PDF
    top_result = results[0]

    current_pdf_name = (
        top_result
        .get("metadata", {})
        .get("source")
    )

    # Prompt
    prompt = f"""
จากบริบทต่อไปนี้ ตอบคำถามของผู้ใช้โดยใช้ข้อมูลจากบริบทเป็นหลัก

คำถาม:
{query_text}

บริบท:
{context}

====================
กฎเกี่ยวกับ image_urls
====================

- หากคำถามต้องการรูปภาพ และในบริบทมี image_url ที่เกี่ยวข้อง
  ให้เลือก image_url ที่ตรงกับคำถาม
- ใช้เฉพาะ image_url ที่ปรากฏอยู่ในบริบทเท่านั้น
- ห้ามสร้างหรือเดา image_url ใหม่
- หากผู้ใช้ขอรูปภาพหลายคนหรือหลายรายการ
  ให้เลือก image_url ของทุกคนหรือทุกรายการที่ตรงกับคำถาม
- หากขอรูปอาจารย์หลายคน ให้เลือกหนึ่งรูปต่ออาจารย์หนึ่งคน และพยายามให้มีรูปของทุกคนที่พบในบริบท
- หากมีหลายรูปของอาจารย์คนเดียวกัน ให้เลือกเพียงรูปเดียวที่ตรงที่สุด ห้ามส่งรูปคนเดิมซ้ำ
- ไม่ต้องจำกัดจำนวน image_urls
- หากพบรูปที่ตรงกับคำถามหลายรูป ให้เลือกทั้งหมดที่เกี่ยวข้อง
- หากไม่มีรูปที่เกี่ยวข้อง ให้ image_urls เป็น []
- หากถามรายชื่อหรือข้อมูลทั้งหมด โดยไม่ได้ขอรูป ให้ตอบเป็นข้อความและใช้ image_urls เป็น []
- หากขอรูปของทุกคนหรือทุกรายการโดยตรง ให้เลือก image_url ที่ตรงกันทั้งหมด
- คำตอบในฟิลด์ answer ต้องเป็นข้อความปกติ ห้ามใส่ JSON ซ้อนในฟิลด์นี้
- JSON เป็นรูปแบบภายในสำหรับระบบเท่านั้น ห้ามส่งโครง JSON ไปเป็นคำตอบผู้ใช้
- image_urls ใช้เฉพาะเมื่อผู้ใช้ร้องขอให้แสดงรูปภาพโดยตรง

====================
รูปแบบคำตอบ
====================

ต้องตอบเป็น JSON เท่านั้น:

{{
    "answer": "คำตอบสำหรับผู้ใช้",
    "image_urls": []
}}

กรณีมีรูปภาพ:

{{
    "answer": "คำตอบสำหรับผู้ใช้",
    "image_urls": [
        "image_url ของรูปที่ 1",
        "image_url ของรูปที่ 2"
    ]
}}

หากผู้ใช้ขอรูปของทุกคนหรือทุกรายการ และในบริบทมีรูปที่เกี่ยวข้อง
ให้ส่ง image_urls ของรูปที่เกี่ยวข้องทั้งหมด เพื่อให้ระบบตรวจข้อจำกัดจำนวนรูปก่อนส่ง LINE

ห้ามใส่ Markdown
ห้ามใส่ ```json
ห้ามเพิ่มข้อความนอก JSON
"""

    # ============================================================
    # Call Typhoon
    # ============================================================

    wait_for_rate_limit()

    response = typhoon_client.chat.completions.create(
        model="typhoon-v2.5-30b-a3b-instruct",
        messages=[
            {
                "role": "system",
                "content": (
                    "คุณเป็นผู้ให้คำแนะนำปรึกษา "
                    "คอยช่วยเหลือในขอบเขตที่ทำได้ "
                    f"{DOCUMENT_SYSTEM_PROMPT}"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=1500 if needs_extended_answer else 700,
        top_p=0.9,
        presence_penalty=0.6,
    )

    llm_raw = response.choices[0].message.content

    # ============================================================
    # Parse JSON
    # ============================================================

    raw_response = (llm_raw or "").strip()
    if raw_response.startswith("```"):
        raw_response = (
            raw_response.removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

    try:
        llm_result = json.loads(raw_response)
    except json.JSONDecodeError:
        print("Unable to parse LLM response as JSON")
        if raw_response.startswith(("{", "[")):
            answer_match = re.search(
                r'"answer"\s*:\s*("(?:\\.|[^"\\])*")',
                raw_response,
            )
            if answer_match:
                return (
                    json.loads(answer_match.group(1)),
                    current_pdf_name,
                    [],
                )
            return (
                "",
                current_pdf_name,
                [],
            )
        return (raw_response, current_pdf_name, [])

    if not isinstance(llm_result, dict):
        return (
            " ".join(item for item in llm_result if isinstance(item, str))
            if isinstance(llm_result, list)
            else str(llm_result) if isinstance(llm_result, str) else "",
            current_pdf_name,
            [],
        )

    llm_answer = llm_result.get("answer", "")
    raw_json_in_answer = False
    if not isinstance(llm_answer, str):
        llm_answer = next(
            (
                llm_answer.get(key)
                for key in ("answer", "text", "content")
                if isinstance(llm_answer, dict)
                and isinstance(llm_answer.get(key), str)
            ),
            " ".join(item for item in llm_answer if isinstance(item, str))
            if isinstance(llm_answer, list)
            else "",
        )
    elif llm_answer.lstrip().startswith(("{", "[")):
        raw_json_in_answer = True
        try:
            nested_result = json.loads(llm_answer)
            nested_answer = (
                nested_result.get("answer")
                if isinstance(nested_result, dict)
                else None
            )
            if isinstance(nested_answer, str):
                llm_answer = nested_answer
            elif isinstance(nested_result, list):
                llm_answer = " ".join(
                    item for item in nested_result if isinstance(item, str)
                )
            else:
                llm_answer = next(
                    (
                        nested_result.get(key)
                        for key in ("text", "content", "message")
                        if isinstance(nested_result, dict)
                        and isinstance(nested_result.get(key), str)
                    ),
                    "",
                )
        except (json.JSONDecodeError, AttributeError):
            answer_match = re.search(
                r'"answer"\s*:\s*("(?:\\.|[^"\\])*")',
                llm_answer,
            )
            llm_answer = (
                json.loads(answer_match.group(1)) if answer_match else ""
            )

    # ============================================================
    # รับ image_urls จาก LLM
    # ============================================================

    selected_image_urls = llm_result.get("image_urls", [])

    if not isinstance(selected_image_urls, list):
        selected_image_urls = []

    image_request = any(
        term in query_text.lower()
        for term in (
            "ขอรูป", "ขอดูรูป", "ดูรูป", "ส่งรูป", "แสดงรูป", "รูปภาพ", "รูปของ", "รูปอาจารย์",
            "ขอภาพ", "ขอดูภาพ", "ดูภาพ", "ส่งภาพ", "แสดงภาพ", "ภาพของ", "ภาพอาจารย์",
            "image", "photo", "picture",
        )
    )

    # ============================================================
    # ตรวจสอบ URL กับ MongoDB context
    # ============================================================

    context_image_urls = list(dict.fromkeys(
        result.get("metadata", {}).get("image_url")
        for result in results
        if (
            result.get("metadata", {}).get("type") == "image"
            and result.get("metadata", {}).get("image_url")
        )
    ))
    valid_image_urls = set(context_image_urls)

    # Use database URLs directly for image requests; LLM URL copying is unreliable.
    image_results = (
        context_image_urls
        if image_request
        else [
            url
            for url in selected_image_urls
            if isinstance(url, str)
            and url in valid_image_urls
        ]
    )

    # ป้องกันรูปซ้ำ
    image_results = list(dict.fromkeys(image_results))
    if raw_json_in_answer and not image_request:
        image_results = []

    logger.info("Selected %d relevant image results", len(image_results))
    print(f"#### Selected image results ({len(image_results)}) ####")
    for image_url in image_results:
        print(image_url)

    return (
        llm_answer,
        current_pdf_name,
        image_results
    )


def respone_message_LLM(llm_answer):
    """
    แปลงคำตอบจาก LLM เป็น LINE TextMessage
    """

    if llm_answer is None or llm_answer == "":
        llm_answer = (
            "ขออภัย ระบบไม่สามารถตอบคำถามได้ในตอนนี้ 🙇‍♂️"
        )

    elif len(llm_answer) > MAX_LINE_TEXT_LENGTH:
        llm_answer = (
            f"{llm_answer[:MAX_LINE_TEXT_LENGTH - 20].rstrip()}"
            "\n\n[คำตอบถูกตัดให้พอดีกับ LINE]"
        )

    return TextMessage(
        text=llm_answer
    )


# ============================================================
# LINE Image Message
# ============================================================

def send_image(image_urls):
    """
    ส่งรูปภาพผ่าน LINE ด้วย Cloudinary URL

    image_urls มาจาก MongoDB Vector Search โดยตรง
    """

    try:
        images = []

        for url in image_urls:
            images.append(
                ImageMessage(
                    original_content_url=url,
                    preview_image_url=url
                )
            )

        return images

    except Exception:
        logger.exception(
            "Unable to prepare LINE image messages"
        )

        return []
