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

    rag_started = time.perf_counter()
    print("#### RAG get Question ####")

    needs_all_advisors = (
        any(term in query_text for term in ("อาจารย์", "อจารย์"))
        and any(
            term in query_text
            for term in ("ทั้งหมด", "ทุกคน", "ทุกอาจารย์", "รายชื่อ", "มีใครบ้าง")
        )
    )
    needs_extended_answer = needs_all_advisors or any(
        term in query_text for term in EXTENDED_QUERY_TERMS
    )
    if needs_all_advisors:
        mongo_started = time.perf_counter()
        try:
            results = list(collection.find(
                {"metadata.type": "text"},
                {"content": 1, "metadata": 1},
            ))
        finally:
            logger.info(
                "RAG MongoDB search completed in %.3fs (all advisors)",
                time.perf_counter() - mongo_started,
            )
    else:
        embedding_started = time.perf_counter()
        try:
            question_embedding = embed_text(query_text)
        finally:
            logger.info(
                "RAG embedding completed in %.3fs",
                time.perf_counter() - embedding_started,
            )
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index2",
                    "path": "embedding",
                    "queryVector": question_embedding,
                    "numCandidates": 80,
                    "limit": MAX_CONTEXT_RESULTS if needs_extended_answer else DEFAULT_CONTEXT_RESULTS,
                }
            },
            {
                "$project": {
                    "content": 1,
                    "metadata": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        mongo_started = time.perf_counter()
        try:
            results = list(collection.aggregate(pipeline))
        finally:
            logger.info(
                "RAG MongoDB vector search completed in %.3fs",
                time.perf_counter() - mongo_started,
            )

    print("#### Vector Search Results ####")
    if not results:
        print("No matching results found.")
        logger.info("RAG completed in %.3fs (no results)", time.perf_counter() - rag_started)

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

{"เมื่อขอรายชื่ออาจารย์ทั้งหมด ให้ไล่รวบรวมชื่ออาจารย์ทุกชื่อที่ปรากฏในบริบทนี้ ตัดชื่อซ้ำ และห้ามจำกัดจำนวนชื่อ" if needs_all_advisors else ""}

บริบท:
{context}

====================
กฎเกี่ยวกับ image_urls
====================

- หากคำถามต้องการรูปภาพ และในบริบทมี image_url ที่เกี่ยวข้อง
  ให้เลือก image_url ที่ตรงกับคำถาม
- ใช้เฉพาะ image_url ที่ปรากฏอยู่ในบริบทเท่านั้น
- ห้ามสร้างหรือเดา image_url ใหม่
- หากผู้ใช้ขอรูปอาจารย์หลายคน ให้ตอบเป็นข้อความว่าระบบให้รูปได้ครั้งละ 1 รูป และขอให้ระบุอาจารย์หนึ่งท่าน; ใช้ image_urls เป็น []
- หากผู้ใช้ขอรูปอาจารย์คนเดียว ให้เลือกรูปที่ตรงที่สุดหนึ่งรูป
- เมื่อตอบคำขอรูป ห้ามกล่าวถึงชนิดไฟล์หรือรูปแบบการส่ง เช่น JPG, PNG หรือ URL 
- สำหรับคำขออาจารย์คนเดียว ให้เลือก image_url ที่ตรงที่สุดเพียงรายการเดียว
- หากไม่มีรูปที่เกี่ยวข้อง ให้ image_urls เป็น []
- เมื่อผู้ใช้ขอรูปอาจารย์คนเดียว ให้ตอบสั้น ๆ และแนบรูปโดยไม่ระบุจำนวนรูป
- หากถามรายชื่อหรือข้อมูลทั้งหมด โดยไม่ได้ขอรูป ให้ตอบเป็นข้อความแสดงรายชื่ออย่างเดี่ยวที่ค้นหาเจอ
- หากคำขอรูปมีหลายคน ให้ใช้ image_urls เป็น [] ไม่ว่าผู้ใช้จะระบุชื่อหรือไม่
- คำตอบในฟิลด์ answer ต้องเป็นข้อความปกติ ห้ามใส่ JSON ซ้อนในฟิลด์นี้
- JSON เป็นรูปแบบภายในสำหรับระบบเท่านั้น ห้ามส่งโครง JSON ไปเป็นคำตอบผู้ใช้
- image_urls ใช้เมื่อผู้ใช้ขอรูปโดยตรง หรือถามข้อมูลเจาะจงเกี่ยวกับอาจารย์คนเดียวและมีรูปของอาจารย์คนนั้นในบริบท

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
        "image_url ของรูปที่ตรงที่สุด"
    ]
}}

หากผู้ใช้ขอรูปอาจารย์หลายคน ให้ตอบเป็นข้อความว่าระบบให้รูปได้ครั้งละ 1 รูป ขอให้เลือกอาจารย์หนึ่งท่าน และส่ง image_urls เป็น []
หากผู้ใช้ขอรูปอาจารย์คนเดียว ให้ส่ง image_url ที่ตรงที่สุดหนึ่งรายการ หากพบในบริบท

ห้ามใส่ Markdown
ห้ามใส่ ```json
ห้ามเพิ่มข้อความนอก JSON
"""

    # ============================================================
    # Call Typhoon
    # ============================================================

    rate_limit_started = time.perf_counter()
    try:
        wait_for_rate_limit()
    finally:
        logger.info(
            "RAG Typhoon rate-limit wait took %.3fs",
            time.perf_counter() - rate_limit_started,
        )

    llm_started = time.perf_counter()
    try:
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
    finally:
        logger.info(
            "RAG Typhoon request completed in %.3fs",
            time.perf_counter() - llm_started,
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

    # ============================================================
    # ตรวจสอบ URL กับ MongoDB context
    # ============================================================

    valid_image_urls = {
        result.get("metadata", {}).get("image_url")
        for result in results
        if (
            result.get("metadata", {}).get("type") == "image"
            and result.get("metadata", {}).get("image_url")
        )
    }

    # เอาเฉพาะ URL ที่มีอยู่จริงใน MongoDB
    image_results = [
        url
        for url in selected_image_urls
        if isinstance(url, str)
        and url in valid_image_urls
    ]

    # ป้องกันรูปซ้ำ
    image_results = list(dict.fromkeys(image_results))
    if any(
        term in query_text.lower()
        for term in ("หลายคน", "หลายท่าน", "ทุกคน", "ทุกท่าน", "ทั้งหมด", "ทั้งคู่", "สองคน", "2 คน", "และ", "หรือ", "กับ", ",")
    ):
        image_results = []
    else:
        image_results = image_results[:1]

    if raw_json_in_answer:
        image_results = []

    logger.info("Selected %d relevant image results", len(image_results))
    logger.info("RAG completed in %.3fs", time.perf_counter() - rag_started)

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
