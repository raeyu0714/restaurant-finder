FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (excluding keys/ and .env)
COPY . .

# Ensure NLP models directory exists
RUN mkdir -p nlp/models

EXPOSE 8000

# Startup: if NLP models are missing the server will warn but still start
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
