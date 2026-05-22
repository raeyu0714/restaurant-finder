FROM python:3.11-slim

WORKDIR /app

# System libraries required by ultralytics/OpenCV (cv2) and torchvision
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (excluding keys/ and .env)
COPY . .

# Ensure model directories exist at startup
RUN mkdir -p nlp/models cv/models/food_vit

EXPOSE 8000

# Startup: if NLP or CV models are missing the server will warn but still start
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
