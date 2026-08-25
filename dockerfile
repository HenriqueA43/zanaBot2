FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
WORKDIR /zana-app
ENV PATH="/zana-app/.venv/bin:$PATH" PYTHONPATH=/zana-app/src
CMD ["./docker-run.sh"]

