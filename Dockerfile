FROM python:3.12-slim

WORKDIR /app

# Install the package + runtime deps (from pyproject [project.dependencies])
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Domain data (owners / fake feed / knowledge base sources)
COPY data ./data

EXPOSE 8000
CMD ["uvicorn", "app.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
