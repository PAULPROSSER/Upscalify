# Use Debian Bullseye (Stable & Complete)
FROM python:3.10-bullseye

# 1. Install System Dependencies
# 'vulkan-tools' and 'mesa-vulkan-drivers' are critical for the software GPU
RUN apt-get update && apt-get install -y \
    wget unzip parallel libvulkan1 mesa-vulkan-drivers vulkan-tools ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 2. Set Working Directory
WORKDIR /app

# 3. Install Python Dependencies
# We unpin versions to get the latest stable releases that support Docker
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir gradio>=4.44.0 huggingface-hub>=0.25.0

# 4. Download Real-ESRGAN
RUN wget https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip \
    && unzip realesrgan-ncnn-vulkan-20220424-ubuntu.zip \
    && chmod +x realesrgan-ncnn-vulkan \
    && mv realesrgan-ncnn-vulkan executable

# 5. Copy App Code
COPY app.py .

# 6. Environment Variables
# These settings help the software renderer find itself
ENV PYTHONUNBUFFERED=1
ENV GRADIO_SERVER_NAME="0.0.0.0"
ENV GRADIO_SERVER_PORT="7860"
ENV LIBGL_ALWAYS_SOFTWARE=1

# 7. Expose and Run
EXPOSE 7860
CMD ["python", "app.py"]
