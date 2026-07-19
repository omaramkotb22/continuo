# Registry for the ingestion container image. deploy.sh pushes here before the
# Lambda (which references this repo) is created.
resource "aws_ecr_repository" "ingest" {
  name                 = "${var.project}-ingest"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # allow `terraform destroy` even with images present

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep only the last few images to avoid storage creep.
resource "aws_ecr_lifecycle_policy" "ingest" {
  repository = aws_ecr_repository.ingest.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire all but the 5 most recent images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}
