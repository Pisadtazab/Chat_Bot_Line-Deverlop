from fastapi import APIRouter ,HTTPException,Depends
from DB.database import delete_pdf_from_db,collection,db
from fastapi.responses import HTMLResponse, JSONResponse
import re


router = APIRouter()

#ลบไฟล์ pdf  
@router.delete("/delete_file", response_class=JSONResponse)
async def delete_file(pdf_name: str):
    try:
        # print(f"[DELETE] pdf_name received: '{pdf_name}'")
        
        # all_sources = db["employees_profiles"].distinct("metadata.source")
        
        # print(f"[DEBUG] all sources in DB: {all_sources}")

        # count = db["employees_profiles"].count_documents({})
        # print(f"[DEBUG] total documents: {count}")

        # # ดู document ตัวแรกดิบๆ
        # sample = db["employees_profiles"].find_one()
        # print(f"[DEBUG] sample document: {sample}")

        # ค้นหาแบบ flexible — ตรงทั้ง full path และชื่อไฟล์อย่างเดียว
        file = collection.find_one({
            "metadata.source": {"$regex": re.escape(pdf_name) + "$"}
        })

        if not file:
            raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์ชื่อ '{pdf_name}'")

        # ดึง source จริงจาก DB ไปใช้ลบ (กรณี full path)
        actual_source = file["metadata"]["source"]
        delete_pdf_from_db(db, actual_source)
        
        return {"status": "success", "message": f"ลบไฟล์ '{pdf_name}' สำเร็จ"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    