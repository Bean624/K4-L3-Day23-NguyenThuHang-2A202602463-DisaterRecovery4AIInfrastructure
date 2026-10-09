# Terraform Infrastructure as Code — Multi-Region DR for AI

Tài liệu này ánh xạ trực tiếp các thành phần mô phỏng cục bộ trong Lab 23 sang kiến trúc đám mây chuẩn AWS:

| Thành phần cục bộ trong Lab | Tài nguyên AWS tương ứng trong Terraform | File cấu hình |
|---|---|---|
| `state/snapshot.py put` / `get` | `aws_s3_bucket_replication_configuration` (Cross-Region Replication) | `s3_replication.tf` |
| `state/_replica/dr-artifacts/MANIFEST.json` | `aws_s3_bucket_versioning` (S3 Object Versioning & Metadata) | `s3_replication.tf` |
| `dr/health_checker.py` (`threshold=3`) | `aws_route53_health_check` (`failure_threshold = 3`, path `/readyz`) | `route53_failover.tf` |
| `edge/proxy.py` (`edge/active_region`) | `aws_route53_record` với `failover_routing_policy` (Primary / Secondary) | `route53_failover.tf` |
| `EDGE_TTL_SECONDS = 5` | `ttl = 5` trên Route53 Record | `route53_failover.tf` |
