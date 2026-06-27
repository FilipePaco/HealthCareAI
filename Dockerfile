# Imagem leve para o serviço SRAG Report Agent.
# Estratégia: base python slim (não alpine — alpine quebra wheels de pandas/matplotlib)
# + multi-stage para deixar o toolchain de build fora da imagem final.

# ---------- Stage 1: builder ----------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# venv isolado que será copiado "limpo" para o runtime
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Usuário não-root (boa prática de segurança / guardrail de deploy)
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

# Só o venv pronto e o código da aplicação entram na imagem final
COPY --from=builder /opt/venv /opt/venv
COPY src/ ./src/
COPY app_streamlit.py ./

# Pasta de dados gravável pelo usuário não-root (download do CSV do DATASUS)
RUN mkdir -p /app/data && chown appuser /app/data

USER appuser
EXPOSE 8000

# Railway injeta $PORT; cai para 8000 localmente. Shell form para expandir a env.
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
