# Project Anton Egon - Dockerfile for RunPod RTX 4090
# Cloud Infrastructure: LivePortrait + Faster-Whisper + ChromaDB
# Phase 17: Cloud Infrastructure

FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0
ENV TORCH_CUDA_ARCH_LIST="8.9"  # RTX 4090

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-venv \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create Python virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Install PyTorch with CUDA support
RUN pip install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu121

# Install core dependencies
RUN pip install \
    opencv-python-headless \
    mediapipe \
    faster-whisper \
    edge-tts \
    pydantic \
    pyyaml \
    python-dotenv \
    loguru \
    aiohttp \
    fastapi \
    uvicorn[standard] \
    websockets \
    pyaudio \
    numpy \
    Pillow \
    scikit-learn \
    sentence-transformers

# Install LivePortrait dependencies
RUN pip install \
    insightface \
    onnxruntime-gpu \
    diffusers \
    transformers \
    accelerate \
    safetensors \
    controlnet-aux

# Install ChromaDB
RUN pip install chromadb

# Install Groq SDK
RUN pip install groq

# Install Tailscale
RUN wget -q https://tailscale.com/install.sh && \
    sh install.sh || true

# Create working directory
WORKDIR /app

# Copy project files
COPY core/ /app/core/
COPY audio/ /app/audio/
COPY vision/ /app/vision/
COPY video/ /app/video/
COPY integration/ /app/integration/
COPY comms/ /app/comms/
COPY ui/ /app/ui/
COPY memory/ /app/memory/
COPY requirements.txt /app/

# Install project dependencies
RUN pip install -r requirements.txt || true

# Create directories for assets and models
RUN mkdir -p /app/assets/props /app/assets/overlays /app/assets/backgrounds
RUN mkdir -p /app/models/liveportrait /app/models/whisper
RUN mkdir -p /app/vault/internal /app/vault/client /app/vault/general
RUN mkdir -p /app/logs

# Expose ports
EXPOSE 8000  # FastAPI
EXPOSE 8765  # ChromaDB
EXPOSE 41641 # Tailscale

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "core.cloud_bridge:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
