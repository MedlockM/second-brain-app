# Shared Lambda container image for asynchronous workers only.
# ARM64/Graviton2 base for 20% cost saving. The interactive API uses the
# dedicated minimal image in lambda-api.Dockerfile.
# CMD is overridden per function in Terraform (image_config.command).

FROM public.ecr.aws/lambda/python:3.11-arm64

# Install build dependencies for C extensions (cryptography, bcrypt, lxml)
RUN yum install -y gcc python3-devel libxml2-devel libxslt-devel && yum clean all

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Set working directory to Lambda task root
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy dependency manifest and its lockfile
COPY pyproject.toml uv.lock ./

# Install base runtime dependencies plus worker-only extraction dependencies,
# at the versions pinned in uv.lock rather than whatever the pyproject ranges
# resolve to on build day (see the comment in lambda-api.Dockerfile: an
# unpinned fastapi took dev down). --no-emit-project keeps the project itself
# out of the resolution; its source tree is copied below.
RUN uv export --frozen --no-dev --extra worker --no-emit-project \
      --format requirements-txt -o /tmp/requirements.txt \
    && uv pip install --system --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Copy application code
COPY media_summarizer/ ./media_summarizer/

# Lambda runs as a non-root user. Restrictive umask on the host (e.g. 0600 files)
# propagates through COPY, so the runtime user can't read the files. Fix by
# making everything world-readable (and dirs world-executable) inside the image.
RUN chmod -R a+rX ${LAMBDA_TASK_ROOT}

# Default to one valid worker handler; Terraform overrides this for every
# deployed worker with the mapping in lambda_workers.tf.
CMD ["media_summarizer.workers.lambda_handlers.article_extraction_handler"]
