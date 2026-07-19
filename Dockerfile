# Lambda-compatible ingestion image. Runs on AWS Lambda (via the bundled Runtime
# API) and locally (via the base image's Runtime Interface Emulator) unchanged.
FROM public.ecr.aws/lambda/python:3.12

COPY requirements-ingest.txt .
RUN pip install --no-cache-dir -r requirements-ingest.txt

# Code + schema (fetch_movers.py resolves db/schema.sql relative to itself).
COPY fetch_movers.py handler.py ${LAMBDA_TASK_ROOT}/
COPY db/schema.sql ${LAMBDA_TASK_ROOT}/db/schema.sql

CMD ["handler.handler"]
