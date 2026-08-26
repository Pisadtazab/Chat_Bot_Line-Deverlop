FROM python:3.12-slim

WORKDIR /code

# copy requirements ก่อน เพื่อให้ docker cache layer นี้ไว้ ไม่ต้อง install ใหม่ทุกครั้งถ้า requirements ไม่เปลี่ยน
COPY requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --default-timeout=1000 --upgrade pip
RUN pip install --no-cache-dir --default-timeout=1000 -r /code/requirements.txt

# copy โค้ดทีหลังสุด เปลี่ยนบ่อยที่สุด
COPY ./app /code/app

EXPOSE 5000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "4"]