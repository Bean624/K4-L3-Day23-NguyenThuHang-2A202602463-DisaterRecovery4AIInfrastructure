# Runbook 1 trang — Region chính down

Runbook chuẩn cho kỹ sư trực ca (on-call SRE / DevOps) lúc 3h sáng. Mỗi bước có lệnh copy-paste được, tiêu chí hoàn thành rõ ràng, phân định vai trò và điều kiện rollback an toàn.

| # | Bước | Lệnh | Biết là xong khi | Ai làm |
|---|---|---|---|---|
| 1 | Xác nhận outage | `python chaos/kill_region.py status` | `a.alive=false` hoặc `a.ready=false` 3 lần liên tiếp | SRE On-call |
| 2 | Mở incident + bấm giờ RTO | `python dr/runbook.py --primary a --target b --backend fs --auto` | Dòng log step 2 ghi nhận trong `reports/runbook-run.jsonl` | Incident Commander |
| 3 | Restore state ở region phụ | `python state/snapshot.py get --region b --backend fs` | `state/region-b/vectors.sqlite` và weights tồn tại, log trả về `restored_at` | Automation / SRE |
| 4 | Scale pool warm→full | `echo full > state/region-b/pool_state && curl -s http://127.0.0.1:8002/readyz` | `/readyz` của Region B trả về HTTP 200 `ready: true` | SRE On-call |
| 5 | DNS/LB cutover | `echo b > edge/active_region` | `curl -s http://localhost:8080/edge/state` trả về `active_region="b"` | SRE On-call |
| 6 | Verify golden signals | `python -c "import httpx; res=[httpx.get('http://127.0.0.1:8002/v1/infer').status_code for _ in range(10)]; print('Success:', res.count(200)/10)"` | p95 latency < 500ms, error rate = 0% trên 10 request kiểm tra | SRE On-call |
| 7 | Đo RTO + postmortem | `python tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300` | Terminal in ra JSON có `rto_verdict: "PASS"`, `rto_measured_s <= 300` | SRE Lead / Postmortem Owner |

---

## Điều kiện Rollback (Failover ngược về Region A)

**Không bao giờ tự động rollback (No full-auto rollback)** nhằm tránh vòng lặp flapping 2 chiều làm sập cả hai region.

1. **Điều kiện kỹ thuật bắt buộc để xem xét rollback:**
   - Region A đã khôi phục hoàn toàn: tiến trình sống, kiểm tra `/readyz` ổn định trong ít nhất 15 phút liên tục không có lỗi.
   - Dữ liệu mới phát sinh tại Region B trong thời gian sự cố đã được đồng bộ ngược (reverse-replication) về Region A thành công, kiểm tra `latest_doc_ts` của A >= `latest_doc_ts` của B (RPO = 0s).
   - Tải hệ thống đang ở khung giờ thấp điểm (off-peak hours).

2. **Thẩm quyền quyết định:**
   - Chỉ có **Incident Commander (IC)** hoặc **Tech Lead hệ thống AI** mới có quyền phê duyệt lệnh rollback về Region A.
