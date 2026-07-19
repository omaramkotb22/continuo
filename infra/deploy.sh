#!/usr/bin/env bash
# Deploy the Continuo AWS stack. Handles the image chicken-and-egg: the Lambda
# references an ECR image that must exist first, so we create the repo, build+push,
# then apply the rest. Idempotent — re-run to ship a new image.
#
# Prereqs: authenticated AWS session (aws sts get-caller-identity works), Docker,
# and infra/terraform.tfvars filled in.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
REGION="$(terraform output -raw region 2>/dev/null || sed -n 's/^region *= *"\(.*\)"/\1/p' terraform.tfvars 2>/dev/null || echo us-east-1)"

terraform init -input=false

echo "== 1/3: ensure ECR repository exists =="
terraform apply -input=false -auto-approve -target=aws_ecr_repository.ingest

REPO="$(terraform output -raw ecr_repository_url)"
REGISTRY="${REPO%%/*}"

echo "== 2/3: build + push image ($REPO:latest) =="
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker build --platform linux/amd64 -t "$REPO:latest" ..
docker push "$REPO:latest"

echo "== 3/3: apply full stack =="
terraform apply -input=false -auto-approve

echo
echo "Done. Manually invoke the ingestion Lambda with:"
echo "  aws lambda invoke --function-name \$(terraform output -raw lambda_function_name) --region $REGION /dev/stdout"
