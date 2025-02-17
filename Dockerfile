# Define the image argument and provide a default value
ARG IMAGE=python:3-slim-bookworm

# Use the image as specified
FROM ${IMAGE}

# Re-declare the ARG after FROM
ARG IMAGE

# Update and upgrade the existing packages 
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    python3 git wget \
    python3-pip \
    ninja-build \
    libopenblas-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/*

RUN python3 -m pip install --upgrade pip

RUN python3 -m pip install --upgrade pip pytest cmake scikit-build setuptools fastapi uvicorn sse-starlette pydantic-settings starlette-context

RUN pip install llama-cpp-python --verbose

WORKDIR /app
COPY app.py requirements.txt /app/

RUN pip install -r requirements.txt

WORKDIR ./models
RUN wget -q https://huggingface.co/MaziyarPanahi/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct.Q8_0.gguf

# Set environment variable for the host
ENV HOST=0.0.0.0
ENV PORT=8000

# Expose a port for the server
EXPOSE 8000

# Run the server start script
WORKDIR /app
#CMD ["tail", "-f", "/dev/null"]
CMD ["python3", "app.py"]