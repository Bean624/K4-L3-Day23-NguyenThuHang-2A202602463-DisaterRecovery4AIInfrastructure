# ==============================================================================
# STRETCH GOAL 4 — S3 Cross-Region Replication (CRR) cho Vector DB & Model Weights
# Ánh xạ từ logic snapshot.put() / snapshot.get() trong state/snapshot.py
# ==============================================================================

# 1. Bucket dich tai Region B (Replica Bucket)
resource "aws_s3_bucket" "replica" {
  provider = aws.replica
  bucket   = "${var.project_name}-artifacts-region-b"
}

resource "aws_s3_bucket_versioning" "replica_versioning" {
  provider = aws.replica
  bucket   = aws_s3_bucket.replica.id
  versioning_configuration {
    status = "Enabled"
  }
}

# 2. Bucket nguon tai Region A (Primary Bucket)
resource "aws_s3_bucket" "primary" {
  provider = aws.primary
  bucket   = "${var.project_name}-artifacts-region-a"
}

resource "aws_s3_bucket_versioning" "primary_versioning" {
  provider = aws.primary
  bucket   = aws_s3_bucket.primary.id
  versioning_configuration {
    status = "Enabled"
  }
}

# 3. IAM Role cho replication tu A sang B
resource "aws_iam_role" "replication_role" {
  provider = aws.primary
  name     = "${var.project_name}-s3-crr-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
      }
    ]
  })
}

resource "aws_iam_policy" "replication_policy" {
  provider = aws.primary
  name     = "${var.project_name}-s3-crr-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [aws_s3_bucket.primary.arn]
      },
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.primary.arn}/*"]
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.replica.arn}/*"]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "replication_attach" {
  provider   = aws.primary
  role       = aws_iam_role.replication_role.name
  policy_arn = aws_iam_policy.replication_policy.arn
}

# 4. Cau hinh Replication Configuration (Anh xa put/get cua state/snapshot.py)
resource "aws_s3_bucket_replication_configuration" "crr" {
  provider = aws.primary
  depends_on = [
    aws_s3_bucket_versioning.primary_versioning,
    aws_s3_bucket_versioning.replica_versioning,
    aws_iam_role_policy_attachment.replication_attach
  ]

  bucket = aws_s3_bucket.primary.id
  role   = aws_iam_role.replication_role.arn

  rule {
    id     = "replicate-vector-db-and-model-weights"
    status = "Enabled"

    filter {
      prefix = "" # Dong bo toan bo artifacts (vectors.sqlite, model.bin, MANIFEST.json)
    }

    destination {
      bucket        = aws_s3_bucket.replica.arn
      storage_class = "STANDARD"
    }
  }
}
