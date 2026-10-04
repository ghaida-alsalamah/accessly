FROM node:22-bookworm-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright STRANDS_BROWSER_HEADLESS=true \
    ACCESSLY_PUBLIC_MODE=1 ACCESSLY_DATA_DIR=/var/data/accessly
WORKDIR /app
COPY requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt \
    && python -m pip check \
    && python -c "from strands import Agent; from strands_tools.browser import LocalChromiumBrowser; import nest_asyncio; import playwright.sync_api" \
    && python -m playwright install --with-deps chromium \
    && useradd --create-home --uid 10001 accessly \
    && mkdir -p /var/data/accessly \
    && chown -R accessly:accessly /app /var/data/accessly
COPY --chown=accessly:accessly api.py main.py db.py auth.py mailer.py result_presenter.py deployment_runtime.py ./
COPY --from=frontend-build --chown=accessly:accessly /frontend/dist ./frontend/dist
USER accessly
EXPOSE 8000
CMD ["sh", "-c", "exec python -m uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
