FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scraper.py links.txt ./

# wyniki lądują w /app/output – zamontuj tam folder z hosta
ENTRYPOINT ["python", "scraper.py"]
