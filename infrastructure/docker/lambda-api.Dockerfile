# Dedicated minimal AWS Lambda image for the interactive FastAPI runtime.
# Worker-only system packages and Python dependencies deliberately stay in
# lambda.Dockerfile so API cold starts do not pay their download/import cost.

FROM public.ecr.aws/lambda/python:3.11-arm64

RUN pip install --no-cache-dir uv

WORKDIR ${LAMBDA_TASK_ROOT}

COPY pyproject.toml ./

# Project base dependencies are the API/shared runtime set. Worker-only extras
# (currently trafilatura and its parsing stack) are intentionally not installed.
RUN uv pip install --system --no-cache-dir -r pyproject.toml

COPY media_summarizer/ ./media_summarizer/

RUN chmod -R a+rX ${LAMBDA_TASK_ROOT}

CMD ["media_summarizer.api.lambda_handler.handler"]
