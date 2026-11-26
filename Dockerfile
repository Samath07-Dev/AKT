FROM python:3.13-slim

# Create a non-root user (standard for Hugging Face Spaces with UID 1000)
RUN useradd -m -u 1000 user

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    SANDBOX_OFFLINE=1 \
    SBERT_MODEL_PATH=models/sbert_programming_minilm

WORKDIR $HOME/app

# Install Python dependencies
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy backend files
COPY --chown=user api.py .
COPY --chown=user src/ src/
COPY --chown=user data/ data/
COPY --chown=user models/ models/

# Hugging Face Spaces exposes port 7860
EXPOSE 7860

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips=*"]
