# Use Python Slim
FROM python:3.9-slim

# 1. Install System Dependencies (Vulkan, Parallel, FFmpeg)
RUN apt-get update && apt-get install -y \
    wget unzip parallel libvulkan1 mesa-vulkan-drivers vulkan-tools ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 2. Set Working Directory
WORKDIR /app

# 3. Install Python Dependencies (PINNED VERSIONS TO FIX CRASH)
# We use --no-cache-dir to ensure you don't get the old broken files
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir gradio==4.29.0 huggingface-hub==0.23.2

# 4. Download and Install Real-ESRGAN (The AI Engine)
RUN wget https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip \
    && unzip realesrgan-ncnn-vulkan-20220424-ubuntu.zip \
    && chmod +x realesrgan-ncnn-vulkan \
    && mv realesrgan-ncnn-vulkan executable

# 5. Copy App Code
COPY app.py .

# 6. Environment Variables for CPU Rendering (Prevents Vulkan Crash)
ENV VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.x86_64.json
ENV LIBGL_ALWAYS_SOFTWARE=1

# 7. Expose and Run
EXPOSE 7860
CMD ["python", "app.py"]
