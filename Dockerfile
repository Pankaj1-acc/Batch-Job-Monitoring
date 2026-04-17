FROM python:3.12-slim

LABEL maintainer="D365 F&O Monitoring Team"
LABEL description="Daily batch job monitoring agent for Dynamics 365 Finance & Operations"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY config/ config/

# Create logs directory
RUN mkdir -p logs

# Non-root user for security
RUN adduser --disabled-password --gecos "" monitor && chown -R monitor:monitor /app
USER monitor

ENTRYPOINT ["python", "-m", "src.scheduler"]
