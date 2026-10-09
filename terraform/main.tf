terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Provider cho Region chinh (Region A - vi du: us-east-1)
provider "aws" {
  alias  = "primary"
  region = var.primary_region
}

# Provider cho Region phu (Region B - vi du: us-west-2)
provider "aws" {
  alias  = "replica"
  region = var.replica_region
}
