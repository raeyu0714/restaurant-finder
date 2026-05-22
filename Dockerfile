FROM python:3.11-slim

WORKDIR /app

# System libs required by ultralytics/OpenCV (cv2) and torchvision
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch + torchvision from the same wheel index (must match)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY backend/ ./backend/
COPY data/ ./data/

# Ensure model directories exist
RUN mkdir -p backend/nlp/models backend/cv/models/food_vit

# Train NLP models at build time
RUN python -m backend.nlp.train

EXPOSE 7860

CMD uvicorn backend.main:app --host 0.0.0.0 --port 7860
