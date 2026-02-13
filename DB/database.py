from pymongo import MongoClient
from bson.objectid import ObjectId
import gridfs
import os
from dotenv import load_dotenv

# การเก็บ key
load_dotenv(override=True)

# MongoDB connection
def get_db():
     # MongoDB configuration
    mogo_uri = os.getenv("MONGO_URI")
    client = MongoClient(mogo_uri)
    db = client["employee_research_db"]
    return db

# Function to delete file from MongoDB
def delete_pdf_from_db(db, file_id: str):
    fs = gridfs.GridFS(db)
    file = fs.get(ObjectId(file_id))  # Get file by ID
    if file:
        fs.delete(file._id)  # Delete the file from GridFS
        db["employees_profiles"].delete_many({"metadata.gridfs_id": file._id})  # Remove references in the collection
    else:
        raise ValueError("File not found")
