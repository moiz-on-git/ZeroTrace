# ───────────────────────────────────────────────────────────────────────────────
# ZeroTrace Enterprise Cloud Infrastructure (Terraform)
# AWS ap-south-1 (Mumbai) Region Architecture for DPDP Act 2023 Compliance
# ───────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "ZeroTrace"
      Compliance  = "DPDP-Act-2023"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ── 1. KMS Customer Master Key (CMK) for Envelope Encryption & Key Shredding ─
resource "aws_kms_key" "zerotrace_master_key" {
  description             = "ZeroTrace Master Key for DPDP Act Section 8(4) Envelope Shredding"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "zerotrace-envelope-cmk-${var.environment}"
  }
}

resource "aws_kms_alias" "zerotrace_key_alias" {
  name          = "alias/zerotrace-${var.environment}"
  target_key_id = aws_kms_key.zerotrace_master_key.key_id
}

# ── 2. S3 Lakehouse Storage with Automatic Version Purge ─────────────────────
resource "aws_s3_bucket" "lakehouse_bucket" {
  bucket        = "zerotrace-lakehouse-${var.environment}-${var.aws_region}"
  force_destroy = false
}

resource "aws_s3_bucket_lifecycle_configuration" "lakehouse_lifecycle" {
  bucket = aws_s3_bucket.lakehouse_bucket.id

  # Critical DPDP Act Rule: Permanently expire deleted object versions after 1 day
  rule {
    id     = "dpdp-purge-noncurrent-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 1
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lakehouse_encryption" {
  bucket = aws_s3_bucket.lakehouse_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.zerotrace_master_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# ── 3. Amazon RDS PostgreSQL with pgvector for AI Long-Term Memory ───────────
resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "zerotrace-rds-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "postgres" {
  identifier             = "zerotrace-db-${var.environment}"
  engine                 = "postgres"
  engine_version         = "16.3"
  instance_class         = var.db_instance_class
  allocated_storage      = 50
  max_allocated_storage  = 500
  storage_type           = "gp3"
  db_name                = "zerotrace"
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  skip_final_snapshot    = var.environment == "dev"
  kms_key_id             = aws_kms_key.zerotrace_master_key.arn
  storage_encrypted      = true
  publicly_accessible    = false

  tags = {
    Name = "zerotrace-postgres-${var.environment}"
  }
}

# ── 4. Amazon ElastiCache Redis for High-Speed Semantic Cache Purge ──────────
resource "aws_elasticache_subnet_group" "redis_subnets" {
  name       = "zerotrace-redis-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "zerotrace-redis-${var.environment}"
  engine               = "redis"
  node_type            = "cache.t4g.medium"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis_subnets.name
}
