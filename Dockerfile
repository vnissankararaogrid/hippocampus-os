FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY examples/ examples/

# Install the package
RUN pip install --no-cache-dir -e .

# Default command
CMD ["python", "examples/demo_loop_breaker.py"]
