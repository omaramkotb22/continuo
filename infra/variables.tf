variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "continuo"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Master password for the RDS Postgres instance."
}

variable "alpha_vantage_api_key" {
  type        = string
  sensitive   = true
  description = "Alpha Vantage API key, injected into the ingestion Lambda."
}

variable "db_ingress_cidr" {
  type        = string
  default     = "0.0.0.0/0"
  description = <<-EOT
    CIDR allowed to reach Postgres (5432). Defaults open because a non-VPC Lambda
    has no fixed egress IP. KNOWN LIMITATION — tighten to your IP for interactive
    use; the master password is the real control. See README "known limitations".
  EOT
}

variable "image_tag" {
  type        = string
  default     = "latest"
  description = "ECR image tag the Lambda runs. deploy.sh builds + pushes this tag."
}
