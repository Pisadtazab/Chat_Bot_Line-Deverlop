
from pydantic import BaseModel
from fastapi import APIRouter,HTTPException
from gridfs import GridFS
from fastapi.responses import StreamingResponse
from bson import ObjectId

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


fs = GridFS(db)

# ค้นหารูปภาพ
@router.get("/image/{file_id}")
def get_image(file_id: str):
    """ เทสดึงรูปภาพ """
    try:
        oid = ObjectId(file_id) # มันอยู่ใน metadata ใช้ ObjectId ในการค้นหา
    except:
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    if not fs.exists(oid):
        raise HTTPException(status_code=404, detail="Image not found")

    grid_out = fs.get(oid)

    return StreamingResponse(
        grid_out,
        media_type=grid_out.content_type or "image/jpeg",
    )

 