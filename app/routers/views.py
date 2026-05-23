from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import APIRouter,Request, HTTPException

from DB.database import collection,db

router = APIRouter()

# from DB.database import get_db #delete_pdf_from_db

# กำหนดโฟลเดอร์สำหรับเก็บไฟล์ HTML templates หน้าตา ui ง่ายๆ 
templates = Jinja2Templates(directory="templates")

# Model สำหรับแสดงข้อมูลในฐานข้อมูล
class FileData(BaseModel):
    file_name: str
    file_id: str

#แสดงหน้าตา ui
@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    แสดงชื่อไฟล์ PDF ทั้งหมดจากฐานข้อมูล  
    """
    try:
        files = db["employees_profiles"].find()  # ดึงข้อมูลไฟล์ทั้งหมดจาก MongoDB
        file_list = [file["metadata"]["source"] for file in files]  # ดึงเฉพาะชื่อไฟล์ (จาก metadata.source)
        
        return templates.TemplateResponse("index.html", {"request": request, "file_list": file_list})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")