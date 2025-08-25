# Use Python 3.12.8 as the base image to match pyproject.toml requirements
FROM python:3.12.8-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
# First, install core dependencies that the AgentCore Runtime needs
# RUN pip install --no-cache-dir \
#     boto3>=1.40 \
#     bedrock-agentcore \
#     pydantic>=2.10.6 \
#     fastapi>=0.115.11 \
#     uvicorn>=0.34.0 \
#     python-dotenv>=1.1.0 \
#     opentelemetry-api>=1.31.1 \
#     opentelemetry-sdk>=1.31.1 \
#     opentelemetry-exporter-otlp>=1.31.1 \
#     opentelemetry-instrumentation-bedrock>=0.39.0 \
#     PyJWT
COPY src/agentic_platform/service/agentcore/runtime/example_agent_deployment/requirements.txt /app
RUN pip install -r /app/requirements.txt
# Copy the entire agentic_platform source code to maintain import structure
COPY src/agentic_platform/ /app/agentic_platform/

# Create an empty __init__.py in the root to make imports work
RUN touch /app/__init__.py

# Set the default AWS region (can be overridden at runtime)
ENV REGION=us-west-2

# Expose port for the service (if it runs as a web service)
EXPOSE 8080

# Default command - can be overridden at runtime
CMD ["uvicorn", "agentic_platform.service.agentcore.runtime.example_agent_deployment.service_runner:app", "--host", "0.0.0.0", "--port", "8080"] 
