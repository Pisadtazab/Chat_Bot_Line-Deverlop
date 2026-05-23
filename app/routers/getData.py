
from pydantic import BaseModel
from fastapi import APIRouter,HTTPException

from DB.database import collection,db

router = APIRouter()

# Model สำหรับแสดงข้อมูลในฐานข้อมูล
class FileData(BaseModel):
    file_name: str
    file_id: str

@router.get("/files", response_model=list[FileData])
async def get_files():
    """
    ดึงข้อมูลไฟล์ทั้งหมดจาก MongoDB
    """
    try:
        files = collection.find()
        file_list = [{"file_name": file["metadata"]["source"], "file_id": str(file["_id"])} for file in files]
        return file_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))