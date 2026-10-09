# Báo Cáo Thực Nghiệm Randomized Chaos Engineering
> **Mục tiêu mở rộng (Stretch Goal 5)** — Đánh giá độ tin cậy thống kê của hệ thống Disaster Recovery qua 5 lần diễn tập ngẫu nhiên (§6 Chaos Engineering).

---

## 1. Kết Quả 5 Lần Diễn Tập Ngẫu Nhiên

| Lần chạy | Chế độ lỗi (Mode) | Thời điểm kích hoạt | RTO đo được | RPO đo được | Documents mất | Kết quả |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| #1 | `stop` | +8.4s | **`21.9s`** | `8.4s` | 4 docs | PASS |
| #2 | `netblock` | +13.5s | **`25.4s`** | `10.7s` | 5 docs | PASS |
| #3 | `netblock` | +13.9s | **`24.8s`** | `7.9s` | 3 docs | PASS |
| #4 | `stop` | +11.3s | **`21.6s`** | `8.4s` | 4 docs | PASS |
| #5 | `netblock` | +13.2s | **`25.7s`** | `11.4s` | 5 docs | PASS |

---

## 2. Phân Tích Thống Kê

- **Số lần thử nghiệm ($N$):** 5
- **RTO Trung bình ($\mu$):** **`23.88s`** (Mục tiêu: $\le 300\text{s}$)
- **Độ lệch chuẩn ($\sigma$):** **`1.97s`**
- **RTO Thấp nhất (Min):** `21.6s`
- **RTO Cao nhất (Max):** `25.7s`

---

## 3. Nhận Xét & Kết Luận Kỹ Thuật

1. **Sự khác biệt giữa `stop` và `netblock`:**
   - Chế độ **`stop`** (tiến trình bị tắt hoàn toàn) cho RTO nhanh hơn khoảng 3 – 4 giây so với **`netblock`**. Nguyên nhân: khi socket đóng đột ngột, client và health checker nhận ngay lỗi `ConnectError` mà không cần đợi hết `timeout = 2.0s`.
   - Chế độ **`netblock`** (mô phỏng rớt mạng / drop packet) phản ánh đúng trường hợp xấu nhất ngoài thực tế (worst-case scenario), vì request bị treo tối đa thời gian timeout trước khi đếm lỗi.
2. **Độ ổn định của hệ thống:**
   - Độ lệch chuẩn $\sigma = 1.97\text{s}$ rất nhỏ so với ngưỡng $300\text{s}$, chứng minh quy trình tự động hóa failover 5 bước có tính xác định cao (deterministic) và có thể tái lập ổn định trong môi trường production.
