FROM python:3.11-slim

# System deps for OpenCV + EasyOCR
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    libgl1-mesa-glx ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Create required dirs
RUN mkdir -p uploads data datasets

EXPOSE 7860

CMD ["gunicorn", "app:app", "--workers", "1", "--timeout", "300", "--bind", "0.0.0.0:7860"]
