# Dedicated minimal AWS Lambda image for the interactive FastAPI runtime.
# Worker-only system packages and Python dependencies deliberately stay in
# lambda.Dockerfile so API cold starts do not pay their download/import cost.

FROM public.ecr.aws/lambda/python:3.11-arm64

RUN pip install --no-cache-dir uv

WORKDIR ${LAMBDA_TASK_ROOT}

COPY pyproject.toml uv.lock ./

# Install the locked versions, never the pyproject ranges. Resolving the ranges
# at build time made every build a different image: `fastapi>=0.104.0` silently
# resolved to 0.141.1, whose include_router internals broke the startup guard in
# main.py, while the local venv stayed on the locked 0.116.1 — dev answered 500
# on every route and nothing reproduced outside the image.
# --no-emit-project: the project itself is the source tree copied below, not a
# dependency to resolve here.
RUN uv export --frozen --no-dev --no-emit-project --format requirements-txt \
      -o /tmp/requirements.txt \
    && uv pip install --system --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY media_summarizer/ ./media_summarizer/

RUN chmod -R a+rX ${LAMBDA_TASK_ROOT}

CMD ["media_summarizer.api.lambda_handler.handler"]
