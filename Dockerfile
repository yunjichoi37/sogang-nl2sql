FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY core/ core/
COPY pages/ pages/
COPY data/db/sogang_university.db data/db/sogang_university.db
COPY data/metadata/ data/metadata/
COPY data/submissions/ data/submissions/

EXPOSE 8080

CMD ["streamlit", "run", "app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
