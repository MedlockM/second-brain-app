# Lambda Dockerfile for utility/background Lambda functions
# This image can be reused for handlers under media_summarizer.workers.*
# It packages all dependencies needed for the Lambda runtime

FROM public.ecr.aws/lambda/python:3.11

# Install build dependencies
RUN yum install -y gcc python3-devel && yum clean all

# Install uv for faster dependency installation
RUN pip install --no-cache-dir uv

# Set working directory to Lambda task root
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy dependency files first (for better caching)
COPY pyproject.toml ./

# Install dependencies using uv
# We install in the Lambda task root so they're available at runtime
RUN uv pip install --system --no-cache-dir \
    aioboto3 \
    aiohttp \
    boto3 \
    httpx \
    pydantic \
    pydantic-settings \
    python-dotenv \
    tenacity

# Copy application code
COPY media_summarizer/ ./media_summarizer/

# Set the handler - this can be overridden per function in Terraform
# Default to the cleanup job archiver handler.
CMD ["media_summarizer.workers.cleanup.job_archiver.lambda_handler"]
