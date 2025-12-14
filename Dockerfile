# Use Python Slim
FROM python:3.9-slim

# Install System Dependencies (Vulkan, Parallel, Zip)
RUN apt-get update && apt-get install -y \
    wget unzip parallel libvulkan1 mesa-vulkan-drivers vulkan-tools ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set Working Directory
WORKDIR /app

# Install Gradio
RUN pip install gradio

# Download and Install Real-ESRGAN
RUN wget https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip \
    && unzip realesrgan-ncnn-vulkan-20220424-ubuntu.zip \
    && chmod +x realesrgan-ncnn-vulkan \
    && mv realesrgan-ncnn-vulkan executable

# Copy App Code
COPY app.py .

# Expose Port
EXPOSE 7860

# Run
CMD ["python", "app.py"]