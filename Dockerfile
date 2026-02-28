FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY SETTINGS.py run.py ./
COPY FRONTEND/ FRONTEND/

EXPOSE 5013

CMD ["python", "run.py"]
