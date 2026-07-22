FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DASHBOARD_MATRIX_DATA_DIR=/var/lib/dashboard-matrix/data \
    DASHBOARD_MATRIX_USER_PLUGINS_DIR=/var/lib/dashboard-matrix/user_plugins \
    DASHBOARD_MATRIX_USER_SCRIPTS_DIR=/var/lib/dashboard-matrix/user_scripts \
    DASHBOARD_MATRIX_USER_THEMES_DIR=/var/lib/dashboard-matrix/user_themes \
    DASHBOARD_MATRIX_HOST=0.0.0.0 DASHBOARD_MATRIX_PORT=8080
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home matrix
COPY . .
RUN mkdir -p /var/lib/dashboard-matrix/data /var/lib/dashboard-matrix/user_plugins /var/lib/dashboard-matrix/user_scripts /var/lib/dashboard-matrix/user_themes \
    && chown -R matrix:matrix /var/lib/dashboard-matrix
USER matrix
EXPOSE 8080
VOLUME ["/var/lib/dashboard-matrix"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)" || exit 1
CMD ["python", "matrix.py"]
