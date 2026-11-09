# 1. Use official Python lightweight image for smaller size
FROM python:3.12-slim

# 2. Set environment variables to optimize Python behavior
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 3. Allow overriding the package index (the Chabokan mirror is used by default
#    for networks where PyPI is not reachable).
ARG PIP_INDEX_URL=https://mirror2.chabokan.net/pypi/simple/

# 4. Set the working directory inside the container
WORKDIR /app

# 5. Copy ONLY the requirements file first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt

# 6. Copy the application code (the context is filtered by .dockerignore)
COPY app ./app

# 7. Run as an unprivileged user
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# 8. Expose the port FastAPI will run on
EXPOSE 8000

# 9. Report readiness to orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4).status == 200 else 1)"

# 10. Command to run the application using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
