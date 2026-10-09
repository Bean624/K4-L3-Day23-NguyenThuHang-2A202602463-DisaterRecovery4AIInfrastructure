# Postmortem — DR Drill Lab 23

Báo cáo phân tích sự cố theo chuẩn Blameless Postmortem (§4 "Sau Failover: Blameless Postmortem"). Trọng tâm hướng vào cải tiến hệ thống và quy trình tự động hóa.

## 1. Timeline (mọi dòng phải có evidence path:line)

| ISO time | Sự kiện | Evidence |
|---|---|---|
| 2026-10-09T04:52:11 | outage bắt đầu (Region A bị netblock) | `chaos/chaos-events.jsonl:3` |
| 2026-10-09T04:52:11 | user đầu tiên bị ảnh hưởng (request lỗi timeout) | `reports/drill-2-withdr.jsonl:25` |
| 2026-10-09T04:52:27 | health check alert (Region A đánh dấu UNHEALTHY sau 3 lần fail) | `reports/health-events.jsonl:2` |
| 2026-10-09T04:52:30 | operator confirm cutover & bắt đầu runbook | `reports/runbook-run.jsonl:2` |
| 2026-10-09T04:52:36 | resolved (request đầu tiên OK được serve bởi Region B) | `reports/drill-2-withdr.jsonl:36` |

## 2. RTO/RPO đo được vs mục tiêu — gap ở bước nào?

- RTO mục tiêu: 300s · đo được: `25.1s` · gap: `-274.9s` (vượt mục tiêu RTO 274.9 giây)
- RPO mục tiêu: 300s · đo được: `6.0s` (`3` doc bị mất) · gap: `-294.0s` (vượt mục tiêu RPO 294.0 giây)
- **Bước tốn nhiều giây nhất:** `Health-check detect floor` (15.0s, chiếm 59.8% tổng RTO). Nguyên nhân: để chống hiện tượng chập chờn (anti-flapping), checker yêu cầu 3 chu kỳ probe liên tiếp thất bại (`interval=5s × threshold=3`).

## 3. Root cause (5 whys)

1. *Tại sao user nhận lỗi 503?* Vì Region A bị cô lập mạng (mô phỏng sự cố đứt cáp / lỗi mạng cục bộ tại Availability Zone chính).
2. *Tại sao hệ thống không phục hồi ngay tức khắc?* Vì cần thời gian phát hiện lỗi tối thiểu (15.0s detection floor), thời gian khôi phục dữ liệu snapshot sang Region B, và độ trễ chờ bộ nhớ đệm DNS/LB hết hạn (EDGE TTL 5.0s).
3. *Nếu đây là outage thật, bước nào trong runbook có nguy cơ thất bại cao nhất?*
   - Bước `2_restore_snapshot`: Nếu embedding model version giữa bản snapshot và inference engine của Region phụ không tương thích (`VERSION mismatch`), toàn bộ vector index sẽ vô dụng và không thể trả lời inference đúng nghĩa.
   - Bước `3_scale_pool` / `4_wait_ready`: Khi Region chính sập, lưu lượng chuyển hướng 100% sang Region phụ có thể dẫn tới thiếu hụt GPU quota hoặc khởi động GPU cold quá thời gian chờ (warm-up timeout).

## 4. Action items (có owner + deadline)

| # | Action item | Owner | Deadline | Giảm RTO/RPO bao nhiêu giây |
|---|---|---|---|---|
| 1 | Tối ưu tần suất health check xuống 3s (threshold giữ 3) | SRE Team | 2026-10-20 | Giảm RTO 6.0 giây (detect floor giảm còn 9s) |
| 2 | Triển khai Change Data Capture (CDC) liên tục cho Vector DB | Data Platform | 2026-10-25 | Giảm RPO từ 6.0s xuống dưới 1.0s (gần như 0 doc lost) |
| 3 | Duy trì warm GPU pool dự phòng tại Region B | AI Infra | 2026-10-30 | Giảm thời gian scale pool và warm-up xuống 0.0s |

## 5. Ba câu hỏi bắt buộc trả lời

1. **`interval × threshold` của bạn là bao nhiêu giây? Nó chiếm bao nhiêu % RTO?**
   - Con số detection floor là: `5.0s × 3 = 15.0s`.
   - Chiếm tỉ trọng: `(15.0s / 25.1s) × 100% ≈ 59.8%` tổng thời gian RTO đo được.
2. **Nếu hạ interval xuống 1s, RTO giảm mấy giây — và bạn trả giá gì (§4 flapping)?**
   - RTO detection floor sẽ giảm từ 15s xuống `1s × 3 = 3s`, tức giảm được **12.0 giây**.
   - Cái giá phải trả: Rất dễ bị **Flapping (đảo cờ liên tục)**. Khi mạng có biến động tạm thời (network jitter hoặc drop gói trong 3-4 giây), hệ thống sẽ nhầm tưởng là thảm họa vùng và tự động chuyển vùng (failover). Khi mạng ổn lại, nó lại chuyển ngược về. Quá trình failover qua lại liên tục sẽ làm nghẽn GPU pool, ngắt kết nối người dùng và gây gián đoạn dịch vụ nghiêm trọng hơn cả sự cố ban đầu.
3. **Nếu outage kéo dài 6 giờ và region chính mất dữ liệu vĩnh viễn, `docs_lost` của bạn có nghĩa gì với khách hàng?**
   - `docs_lost = 3` có nghĩa là 3 văn bản / tài liệu / giao dịch mới nhất mà khách hàng đã nạp vào hệ thống trong khoảng 6.0 giây trước khi Region A sập đã bị mất vĩnh viễn vì chưa kịp nằm trong chu kỳ snapshot kế tiếp.
   - Đối với khách hàng, họ sẽ gặp tình trạng dữ liệu bị mất một phần (data loss). Họ phải gửi lại yêu cầu hoặc đội vận hành phải sử dụng nhật ký giao dịch ngoài (audit log) để tái tạo (re-ingest) 3 bản ghi này vào Region B.
