"""BƯỚC 3c — SINH VIÊN VIẾT. Tự động hoá runbook §4 "Runbook: Region Chính Down".

7 bước trên slide, mỗi bước 1 dòng log có ts. Log này CHÍNH LÀ timeline của postmortem.
  1 xac_nhan_outage          — probe cả 2 region, đừng tin 1 lần fail (dùng nhiều lần
                              hoặc gọi health_checker.probe nếu đã viết xong 3a)
  2 thong_bao_incident       — ts của dòng này là mốc "operator biết tin", LUÔN LUÔN
                              SAU t_outage trong chaos-events (không thể trùng — operator
                              không thể biết ngay giây outage xảy ra). Ghi cả 2 ts vào
                              log để postmortem tính được "độ trễ thông báo".
  3 scale_gpu_pool           — gọi HÀM `failover.failover(...)` MỘT LẦN DUY NHẤT. Hàm
                              đó tự làm đủ 5 bước con (verify/restore/scale/wait/cutover)
                              và tự ghi log riêng vào reports/failover-events.jsonl.
  4 verify_state_replica     — KHÔNG gọi lại failover — chỉ ĐỌC kết quả (vector count +
                              weights ở region phụ) từ dict mà bước 3 trả về, để log vào
                              runbook-run.jsonl cho postmortem đọc 1 chỗ duy nhất.
  5 dns_cutover              — cũng chỉ đọc lại: kết quả cutover có ok hay không.
  6 verify_golden_signals    — 10 request thật vào region phụ: p95 latency + error rate
  7 post_incident            — elapsed_s + lệnh đo RTO

BÁN TỰ ĐỘNG, KHÔNG FULL-AUTO (§4: "failover đầu tiên nên là bán tự động — alert +
1-click confirm — tránh flapping gây failover 2 chiều liên tục"). Mặc định phải hỏi
người vận hành confirm; --auto chỉ dùng trong CI/khi chấm điểm.

Chạy:  python dr/runbook.py --primary a --target b --backend fs
"""
import argparse
import json
import pathlib
import sys
import time

# pyrefly: ignore [missing-import]
import httpx

sys.path.insert(0, ".")
from dr import failover as fo  # noqa: E402

LOG = pathlib.Path("reports/runbook-run.jsonl")
URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}


def step(n, name, **kw):
    """Ghi 1 dòng {ts, iso, step, name, ...} vào LOG."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "step": n,
        "name": name,
        **kw,
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print("RUNBOOK", json.dumps(rec))
    return rec


def confirm(auto: bool, msg: str) -> bool:
    """auto=True -> True; ngược lại hỏi y/N. Đừng bỏ hàm này đi."""
    if auto:
        return True
    try:
        ans = input(f"{msg} [y/N]: ").strip().lower()
        return ans in ("y", "yes")
    except EOFError:
        return True


def run(primary: str, target: str, backend: str, auto: bool) -> dict:
    """7 bước tự động hóa runbook §4 'Runbook: Region Chính Down'."""
    t_start_runbook = time.time()

    # Bước 1: 1 xac_nhan_outage
    from dr import health_checker
    p_ok, p_reason = health_checker.probe(primary, timeout=2.0)
    t_ok, t_reason = health_checker.probe(target, timeout=2.0)
    step(1, "xac_nhan_outage", primary=primary, primary_ready=p_ok, primary_reason=p_reason,
         target=target, target_ready=t_ok, target_reason=t_reason)

    if not confirm(auto, f"Region {primary} gap su co, xac nhan failover sang region {target}?"):
        step(1, "aborted_by_operator", reason="operator_declined")
        return {"ok": False, "aborted": True}

    # Bước 2: 2 thong_bao_incident
    chaos_file = pathlib.Path("chaos/chaos-events.jsonl")
    t_outage = None
    if chaos_file.exists():
        for line in chaos_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    e = json.loads(line)
                    if e.get("action") == "kill" and e.get("region") == primary:
                        t_outage = e.get("ts")
                except Exception:
                    pass
    t_aware = time.time()
    alert_delay = round(t_aware - t_outage, 2) if t_outage else None
    step(2, "thong_bao_incident", primary=primary, target=target,
         t_outage=t_outage, t_operator_aware=t_aware, alert_delay_s=alert_delay)

    # Bước 3: 3 scale_gpu_pool (gọi failover.failover DUY NHẤT 1 LẦN)
    fo_res = fo.failover(target=target, backend=backend, wait=60.0)
    step(3, "scale_gpu_pool", target=target, backend=backend,
         failover_ok=fo_res.get("ok"), failover_res=fo_res)

    if not fo_res.get("ok"):
        return {"ok": False, "error": "failover_failed", "detail": fo_res}

    # Bước 4: 4 verify_state_replica (ĐỌC lại từ dict trả về của bước 3)
    step(4, "verify_state_replica", target=target,
         rpo_seconds=fo_res.get("rpo_seconds"),
         docs_lost=fo_res.get("docs_lost"),
         embed_model_version=fo_res.get("embed_model_version"))

    # Bước 5: 5 dns_cutover (ĐỌC lại từ kết quả bước 3)
    step(5, "dns_cutover", target=target, active_region=fo_res.get("target"), ok=fo_res.get("ok"))

    # Bước 6: 6 verify_golden_signals (10 request thật vào region phụ)
    latencies = []
    errors = 0
    for _ in range(10):
        t0 = time.time()
        try:
            r = httpx.get(f"{URL[target]}/v1/infer", timeout=3.0)
            if r.status_code == 200:
                latencies.append((time.time() - t0) * 1000.0)
            else:
                errors += 1
        except Exception:
            errors += 1
    p95 = None
    if latencies:
        latencies.sort()
        idx = int(len(latencies) * 0.95)
        p95 = round(latencies[min(idx, len(latencies) - 1)], 1)
    error_rate = round(errors / 10.0, 2)
    step(6, "verify_golden_signals", target=target, sample_count=10,
         p95_latency_ms=p95, error_rate=error_rate)

    # Bước 7: 7 post_incident
    elapsed = round(time.time() - t_start_runbook, 2)
    measure_cmd = "python tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300"
    step(7, "post_incident", elapsed_s=elapsed, measure_cmd=measure_cmd)

    return {
        "ok": True,
        "primary": primary,
        "target": target,
        "elapsed_s": elapsed,
        "rpo_seconds": fo_res.get("rpo_seconds"),
        "docs_lost": fo_res.get("docs_lost"),
        "p95_latency_ms": p95,
        "error_rate": error_rate,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--primary", default="a")
    p.add_argument("--target", default="b")
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--auto", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.primary, a.target, a.backend, a.auto), indent=2))
