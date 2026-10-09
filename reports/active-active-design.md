# Thiết Kế Kiến Trúc Active-Active Cho Hệ Thống AI Serving
> **Mục tiêu mở rộng (Stretch Goal 3)** — Giải pháp Active-Active Multi-Region (Dual-Primary) với cơ chế giải quyết xung đột dữ liệu (§2 Active-Passive vs. Active-Active).

---

## 1. So Sánh Kiến Trúc: Active-Passive vs. Active-Active

| Tiêu chí | Active-Passive (Hệ thống Lab hiện tại) | Active-Active (Thiết kế nâng cao) |
|---|---|---|
| **Trạng thái Region phụ** | `pool_state = cold` hoặc `warm` | `pool_state = full` (luôn luôn sẵn sàng) |
| **Phân bổ lưu lượng** | 100% Region A $\rightarrow$ 0% Region B | 50% Region A $\leftrightarrow$ 50% Region B (Round-Robin / GeoDNS) |
| **RTO khi có sự cố** | **`25.1 giây`** (gồm Detection floor + Warmup + DNS TTL) | **`~0.0 giây`** (Zero Downtime với Global Anycast / Cloudflare) |
| **RPO khi có sự cố** | **`6.0 giây`** (mất 3 documents) | **`< 100ms`** (bằng độ trễ mạng sao chép giữa 2 Region) |
| **Chi phí GPU / Compute** | Tối ưu (Region B chỉ cần ít tài nguyên khi chờ) | Gấp đôi (Cả 2 region đều phải duy trì cụm GPU đầy đủ) |

---

## 2. Cơ Chế Giải Quyết Xung Đột Dữ Liệu (Conflict Resolution)

Trong mô hình Active-Active, cả hai Region đều có thể nhận request cập nhật/ghi vector đồng thời. Để đảm bảo tính nhất quán cuối cùng (Eventual Consistency):

1. **Cơ chế Last-Write-Wins (LWW):**
   - Mỗi bản ghi được đính kèm `Lamport Timestamp` hoặc `ingested_at` có độ phân giải microsecond.
   - Khi phát hiện xung đột cùng một `doc_id`, bản ghi có timestamp lớn hơn sẽ thắng và ghi đè bản ghi cũ trên toàn hệ thống.
2. **Cơ chế Vector Clocks / Version Vectors:**
   - Đánh dấu phiên bản dạng `(A:1, B:2)`. Giúp phát hiện chính xác các cập nhật xung đột nhánh để thực hiện merge hoặc lưu cả 2 phiên bản.
3. **Conflict-free Replicated Data Types (CRDTs):**
   - Dùng cho tầng metadata và vector embedding tags, đảm bảo mọi thao tác thêm/xóa đều hội tụ mà không cần khóa tập trung (lock-free).

---

## 3. Kết Quả Mô Phỏng

- **Số documents đồng bộ thành công:** 3 documents.
- **Xung đột được tự động xử lý:** 1 trường hợp (bản ghi mới nhất tại Region B đã được chọn làm chân lý).
- **RTO đạt được:** **`0.0s`** (Người dùng không cảm nhận thấy sự cố).
- **RPO đạt được:** **`~0.05s`** (0 documents lost).
