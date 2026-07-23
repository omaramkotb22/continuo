#!/usr/bin/env bash
# Deploy the Continuo AWS stack. Handles the image chicken-and-egg: the Lambda
# references an ECR image that must exist first, so we create the repo, build+push,
# then apply the rest. Idempotent — re-run to ship a new image.
#
# Prereqs: authenticated AWS session (aws sts get-caller-identity works), Docker,
# and infra/terraform.tfvars filled in.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# Terraform's AWS provider reads standard env/shared creds, not custom CLI wrappers
# (e.g. the `login_session` profile). If no creds are already in the env, materialize
# the CLI's resolved (possibly temporary) credentials so Terraform can use them.
if [ -z "${AWS_ACCESS_KEY_ID:-}" ] && aws configure export-credentials --format env >/dev/null 2>&1; then
  eval "$(aws configure export-credentials --format env)"
fi

REGION="$(sed -n 's/^region *= *"\(.*\)"/\1/p' terraform.tfvars 2>/dev/null || echo us-east-1)"

terraform init -input=false

echo "== 1/3: ensure ECR repository exists =="
terraform apply -input=false -auto-approve -target=aws_ecr_repository.ingest

REPO="$(terraform output -raw ecr_repository_url)"
REGISTRY="${REPO%%/*}"

echo "== 2/3: build + push image ($REPO:latest) =="
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
# --provenance=false: skip BuildKit's attestation manifest, which turns the push into
# an OCI manifest index that Lambda's container runtime rejects ("media type ... not supported").
docker build --provenance=false --platform linux/amd64 -t "$REPO:latest" ..
docker push "$REPO:latest"

echo "== 3/3: apply full stack =="
terraform apply -input=false -auto-approve

echo
echo "Done. Manually invoke the ingestion Lambda with:"
echo "  aws lambda invoke --function-name \$(terraform output -raw lambda_function_name) --region $REGION /dev/stdout"
