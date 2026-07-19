# Ingestion Lambda, from the container image in ECR.
# NOTE: the image tag must exist in ECR before this applies — deploy.sh handles the
# ordering (create ECR -> build+push -> full apply). Not in a VPC, so it has direct
# internet access to Alpha Vantage and reaches RDS over its public endpoint.
resource "aws_lambda_function" "ingest" {
  function_name = "${var.project}-ingest"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.ingest.repository_url}:${var.image_tag}"

  timeout     = 60
  memory_size = 256

  environment {
    variables = {
      ALPHA_VANTAGE_API_KEY = var.alpha_vantage_api_key
      RAW_BUCKET            = aws_s3_bucket.raw.bucket
      RAW_DIR               = "/tmp"
      DATABASE_URL = format(
        "postgresql://%s:%s@%s/%s",
        aws_db_instance.this.username,
        var.db_password,
        aws_db_instance.this.endpoint, # host:port
        aws_db_instance.this.db_name,
      )
    }
  }
}

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/${aws_lambda_function.ingest.function_name}"
  retention_in_days = 14
}
