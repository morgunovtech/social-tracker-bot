FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/
COPY entrypoint.sh .

# The bot runs as non-root appuser; entrypoint.sh starts as root only to hand
# the data volume to appuser (platforms mount it root-owned), then drops.
RUN useradd --uid 1000 --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data \
    && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "bot.main"]
