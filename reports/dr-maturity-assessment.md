# Đánh Giá Độ Trưởng Thành Phục Hồi Thảm Họa (DR Maturity Assessment)
> **Mục tiêu mở rộng (Stretch Goal 6)** — Khung đánh giá năng lực Disaster Recovery & High Availability cho Hạ tầng AI.

---

## 1. Thang Đo Độ Trưởng Thành DR (Levels 0 – 4)

Dựa trên tiêu chuẩn vận hành đám mây (AWS Well-Architected Reliability Pillar & SRE Practices):

| Cấp độ (Level) | Mô hình kiến trúc | RTO kỳ vọng | RPO kỳ vọng | Đặc điểm vận hành |
|---|---|---|---|---|
| **Level 0: Không có DR (Unprepared)** | Single Region, không sao lưu | $\infty$ (Mất trắng) | $\infty$ | Sự cố xảy ra là mất toàn bộ dữ liệu, dịch vụ chết vĩnh viễn (như Drill 1). |
| **Level 1: Backup & Restore thủ công** | Cold Standby, backup định kỳ ngày/tuần | 12 – 48 giờ | 24 giờ | Lưu trữ cold storage; khi xảy ra thảm họa, kỹ sư phải dựng lại hạ tầng từ đầu. |
| **Level 2: Warm Standby / Bán tự động** | Pilot Light, snapshot 30s – 1h | 1 – 5 phút | 30s – 15 phút | Region phụ ở trạng thái warm/chờ; có script tự động khôi phục nhưng cần con người xác nhận. |
| **Level 3: Multi-Region Hot Standby** | Multi-Region Automated Failover | < 30 giây | < 1 giây | CDC Streaming đồng bộ thời gian thực; tự động failover hoàn toàn có circuit breaker. |
| **Level 4: Active-Active & Continuous Chaos** | Multi-Site Active-Active | 0 giây (Không gián đoạn) | 0 giây | Cả 2 region cùng xử lý traffic; Chaos Engineering định kỳ hàng tuần trong production. |

---

## 2. Tự Đánh Giá Hệ Thống Hiện Tại (Hạ Tầng Lab 23)

### Điểm số hiện tại: **Level 2.3 / 4 (Warm Standby bán tự động nâng cao)**

### Minh chứng đo đạc thực tế:
- **RTO đạt được:** **`25.1 giây`** (vượt xa mục tiêu 300 giây của Level 2).
- **RPO đạt được:** **`6.0 giây`** / **`3 documents`** (phụ thuộc vào chu kỳ `replicate.py` 30s).
- **Cơ chế chống Flapping:** Đã hiện thực ngưỡng $3$ lần fail liên tiếp (`threshold=3`), tạo ra sàn phát hiện lỗi cố định $15.0\text{s}$ (`interval=5s × threshold=3`).
- **Mức độ tự động hóa:** Bán tự động (Semi-Automated) với xác nhận an toàn của kỹ sư trực ca (1-click confirmation) để ngăn chặn hiện tượng failover hai chiều liên tục.

### Phân tích khoảng cách (Gap Analysis):
1. **Khoảng cách RPO (6.0s vs < 1s của Level 3):** Cơ chế hiện tại là periodic file copy (`state/snapshot.py`) mỗi 30s. Nếu sự cố rơi vào giây thứ 29 của chu kỳ, tối đa 15 documents có thể bị mất.
2. **Khoảng cách RTO (25.1s vs 0s của Level 4):** Phải chờ DNS TTL (5 giây) và GPU warm-up (0.22s) khi chuyển vùng.
3. **Quy trình vận hành:** Vẫn phụ thuộc vào việc kỹ sư on-call chạy script runbook (mất ~3 giây thao tác).

---

## 3. Lộ Trình Cụ Thể Để Nâng Cấp Lên Level 3 & Level 4

### Để đạt Level 3 (Hot Standby hoàn toàn tự động):
1. **Thay thế Batch Snapshot bằng CDC (Change Data Capture):**
   - Sử dụng WAL replication (SQLite WAL streaming hoặc Debezium/Kafka) để đẩy từng vector insert sang Region B ngay khi vừa ghi xong. Giảm RPO từ $6.0\text{s} \rightarrow < 500\text{ms}$.
2. **Pre-warmed GPU Pool:**
   - Giữ Region B ở trạng thái `pool_state=warm` với Model Weights tải sẵn vào GPU memory, giảm thời gian khởi động về $0\text{s}$.
3. **Tự động hóa Failover có Circuit Breaker:**
   - Khi Health Checker báo `UNHEALTHY` liên tiếp 3 lần, tự động kích hoạt failover mà không cần chờ người gõ lệnh, nhưng trang bị Circuit Breaker: nếu chuyển vùng thất bại hoặc mạng chập chờn, lập tức khóa trạng thái (freeze state) và gửi còi báo động PagerDuty.

### Để đạt Level 4 (Active-Active Multi-Region & Chaos Automation):
1. **Cấu hình Anycast DNS / Global Anycast BGP Routing:**
   - Loại bỏ độ trễ của DNS TTL caching. Khi 1 Region lỗi, các bộ định tuyến BGP sẽ tự động rút đường truyền (withdraw BGP route) trong < 1 giây.
2. **Replication 2 chiều có giải quyết xung đột (Conflict Resolution):**
   - Thiết kế Vector Ingestion hỗ trợ CRDT (Conflict-free Replicated Data Type) hoặc Last-Write-Wins (LWW) dựa trên Vector Clock.
3. **Continuous Game Day CI/CD:**
   - Tích hợp Chaos Monkey tự động ngắt kết nối 1 Region ngẫu nhiên mỗi tuần vào khung giờ thấp điểm để kiểm chứng khả năng tự liền sẹo (self-healing) liên tục.
