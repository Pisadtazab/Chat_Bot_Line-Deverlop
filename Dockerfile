FROM python:3.12-slim

WORKDIR /code

# copy requirements ก่อน เพื่อให้ docker cache layer นี้ไว้ ไม่ต้อง install ใหม่ทุกครั้งถ้า requirements ไม่เปลี่ยน
COPY requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --default-timeout=1000 --upgrade pip
RUN pip install --no-cache-dir --default-timeout=1000 -r /code/requirements.txt

# Runtime files needed by the FastAPI app and its Home page.
COPY ./app /code/app
COPY ./templates /code/templates
RUN mkdir -p /code/src

EXPOSE 5000

# The webhook queue is maintained in this process. Keep one worker so messages
# from the same LINE user always reach the same per-user queue.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "1"]