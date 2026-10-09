variable "primary_region" {
  type        = string
  default     = "us-east-1"
  description = "Region chinh phuc vu traffic (Region A)"
}

variable "replica_region" {
  type        = string
  default     = "us-west-2"
  description = "Region du phong thảm họa (Region B)"
}

variable "project_name" {
  type        = string
  default     = "ai-infra-dr"
  description = "Tên tiền tố cho các tài nguyên hạ tầng"
}

variable "domain_name" {
  type        = string
  default     = "ai-serving.example.internal"
  description = "Tên miền định tuyến failover"
}
