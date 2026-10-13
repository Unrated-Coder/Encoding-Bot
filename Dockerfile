FROM python:3.10-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Dhaka \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Use the current Debian Bookworm repositories instead of the old Bullseye base.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git wget pv jq aria2 mediainfo gcc \
    libsm6 libxext6 libfontconfig1 libxrender1 libgl1 tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/downloads /app/encode /app/sessions /app/VideoEncoder/utils/extras

CMD ["python", "-m", "VideoEncoder"]
