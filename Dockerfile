# The OS suffix is explicit: a bare «3.14-slim» changes OS with the next Debian
# stable. The digest pins the exact image CI built and ran; Dependabot (docker)
# proposes the next one as a PR.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

WORKDIR /app

COPY requirements.txt .
# Exactly the locked versions, each checked against its hash (requirements.txt
# is compiled from requirements.in); nothing else gets resolved.
RUN pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt

COPY bot/ bot/
COPY entrypoint.sh .

# The bot runs as non-root appuser; entrypoint.sh starts as root only to hand
# the data volume to appuser (platforms mount it root-owned), then drops.
RUN useradd --uid 1000 --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data \
    && chmod +x /app/entrypoint.sh

# Build commit for «🔄 Бот обновился» and ⚙️ Настройки. Railway sets
# RAILWAY_GIT_COMMIT_SHA on its own; other builds can pass --build-arg.
ARG APP_COMMIT=""
ENV APP_COMMIT=$APP_COMMIT

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "bot.main"]
