FROM python:3.11-slim

WORKDIR /app

# Install CPU-only PyTorch first to prevent CUDA version being pulled in
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY backend/ ./backend/
COPY data/ ./data/

# Train NLP models at build time
RUN python -m backend.nlp.train

EXPOSE 7860

CMD uvicorn backend.main:app --host 0.0.0.0 --port 7860
