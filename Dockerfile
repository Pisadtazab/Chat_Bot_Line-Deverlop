FROM python:3.12-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

# RUN pip install fastapi[standard]
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

# เปิด port 8000
EXPOSE 8000

# CMD ["fastapi", "run", "app/main.py", "--port", "8080"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]