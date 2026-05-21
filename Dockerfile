FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY backend/ ./backend/
COPY data/ ./data/

# Train NLP models at build time (downloads paraphrase-multilingual-MiniLM-L12-v2 from HuggingFace)
RUN python -m backend.nlp.train

EXPOSE 8000

CMD sh -c 'echo "PORT=$PORT" && python -c "from backend.main import app; print(\"APP IMPORT OK\")" 2>&1 && uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-10000}" --log-level debug 2>&1'
