# Shared Lambda container image for all functions (API + workers).
# ARM64/Graviton2 base for 20% cost saving.
# CMD is overridden per function in Terraform (image_config.command).

FROM public.ecr.aws/lambda/python:3.11-arm64

# Install build dependencies for C extensions (cryptography, bcrypt, lxml)
RUN yum install -y gcc python3-devel libxml2-devel libxslt-devel && yum clean all

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Set working directory to Lambda task root
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy dependency manifest
COPY pyproject.toml ./

# Install all runtime dependencies using uv
# Note: openai-whisper, docker, slowapi, redis have been removed from pyproject.toml
RUN uv pip install --system --no-cache-dir ".[default]" 2>/dev/null || \
    uv pip install --system --no-cache-dir -e .

# Copy application code
COPY media_summarizer/ ./media_summarizer/

# Lambda runs as a non-root user. Restrictive umask on the host (e.g. 0600 files)
# propagates through COPY, so the runtime user can't read the files. Fix by
# making everything world-readable (and dirs world-executable) inside the image.
RUN chmod -R a+rX ${LAMBDA_TASK_ROOT}

# Default CMD is the API handler; overridden per worker in Terraform
CMD ["media_summarizer.api.lambda_handler.handler"]
