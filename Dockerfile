# syntax=docker/dockerfile:1
FROM python:3.13-slim-trixie AS builder
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
ARG INSTALL_DEV=false
RUN python -m venv /opt/venv
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$INSTALL_DEV" = "true" ]; then \
        /opt/venv/bin/pip install -r requirements-dev.txt; \
    else \
        /opt/venv/bin/pip install -r requirements.txt; \
    fi

RUN if [ "$INSTALL_DEV" != "true" ]; then /opt/venv/bin/python -m pip uninstall -y pip; fi

FROM python:3.13-slim-trixie AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH"
RUN groupadd --gid 10001 appuser && useradd --uid 10001 --gid appuser --create-home --shell /usr/sbin/nologin appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser manage.py ./
COPY --chown=appuser:appuser tutberry/ ./tutberry/
USER appuser
ARG APP_VERSION=0.0.0-dev
ENV APP_VERSION=$APP_VERSION
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=2).close()"
CMD ["gunicorn", "tutberry.wsgi:application", "--bind", "0.0.0.0:8080", "--access-logfile", "-"]
