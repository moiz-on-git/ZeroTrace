variable "aws_region" {
  type        = string
  default     = "ap-south-1" # Mumbai, India
  description = "AWS region for data localization compliance under DPDP Act 2023"
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Deployment environment (dev, staging, prod)"
}

variable "private_subnet_ids" {
  type        = list(string)
  default     = ["subnet-0123456789abcdef0", "subnet-0fedcba9876543210"]
  description = "VPC Private subnets for database and lakehouse isolation"
}

variable "db_instance_class" {
  type        = string
  default     = "db.r6g.xlarge"
  description = "RDS instance class for high-throughput pgvector scans"
}

variable "db_username" {
  type        = string
  default     = "zerotrace_admin"
  description = "Master database username"
}

variable "db_password" {
  type        = string
  sensitive   = true
  default     = "ZtSecureMasterPassword2026!"
  description = "Master database password"
}
