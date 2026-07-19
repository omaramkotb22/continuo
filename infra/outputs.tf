output "region" {
  value = var.region
}

output "ecr_repository_url" {
  value = aws_ecr_repository.ingest.repository_url
}

output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "rds_endpoint" {
  value = aws_db_instance.this.endpoint
}

output "lambda_function_name" {
  value = aws_lambda_function.ingest.function_name
}

output "event_rule_name" {
  value = aws_cloudwatch_event_rule.daily.name
}
