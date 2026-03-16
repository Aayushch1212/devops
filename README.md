# DevOps Assignment — 10xConstruction

Platform: 2-core 2GHz, 500MB RAM, Docker
Goal: keep the whole stack under 300MB

Stack: Python sensor service + Prometheus + Grafana

---

## Demo

https://www.loom.com/share/41b11843615c41c5964e9b1155733101

---

## Running it
```bash
git clone https://github.com/Aayushch1212/devops.git
cd devops

docker compose up -d --build

docker ps
docker stats --no-stream
```

## URLs

| Service | URL | Login |
|---------|-----|-------|
| Grafana | http://localhost:3000 | admin / edge-robot-2024 |
| Prometheus | http://localhost:9090 | - |
| Metrics endpoint | http://localhost:8000/metrics | - |
| Health check | http://localhost:8000/health | - |

---

## Files
```
sensor_service.py     — main sensor service (fixed)
Dockerfile            — python 3.11 slim
requirements.txt      — only prometheus-client
prometheus.yml        — tuned for low memory
docker-compose.yml    — mem limits per container
```

---

## Bugs fixed in sensor_service.py

**Bug 1 — CPU was getting pegged at 100%**
```python
# this was running on every single scrape request
for _ in range(2000000):
    pass
```

Removed it. Moved sensor reads to a background thread with a 1s sleep. CPU now sits under 5%.

---

**Bug 2 — Container was OOMing after a while**
```python
data_blob = "X" * 5_000_000
temp_data = data_blob * random.randint(1, 3)
```

This was allocating up to 15MB per scrape and never freeing it. Replaced with a `deque(maxlen=60)` — memory stays constant now regardless of uptime.

---

**Bug 3 — Scrape timeouts**

All the sensor computation was blocking the `/metrics` handler directly, so Prometheus kept timing out waiting for a response. Moved everything to a background thread, handler just reads the pre-computed values. Response time dropped to under 5ms.

---

**Bug 4 — No useful custom metric**

Added `sensor_cpu_spike_duration_seconds` as a histogram. Lets you query p95 spike durations which is more useful than just knowing a spike happened.
```promql
histogram_quantile(0.95, rate(sensor_cpu_spike_duration_seconds_bucket[5m]))
rate(sensor_cpu_spike_duration_seconds_count[1m]) * 60
```

Buckets: 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0 seconds

---

## Memory after 22h uptime

| Container | Limit | Actual |
|-----------|-------|--------|
| sensor-service | 40 MB | ~24.5 MB |
| prometheus | 100 MB | ~65.9 MB |
| grafana | 150 MB | ~97.9 MB |
| total | 290 MB | ~188 MB |

Stayed well under budget. Hard limits in compose mean a leak won't silently eat into
the host.

---

## Prometheus tuning

Short retention (6h) + WAL compression keeps RSS under 100MB. Capped query
concurrency at 2 since it's a 2-core machine. 15s scrape interval is fine for
this use case.

---

## Grafana

Disabled alerting and analytics — those are the main things that bloat Grafana's
memory. Keeps it under 100MB.

---

## Why Prometheus over VictoriaMetrics

We're only tracking ~100 time series, so VictoriaMetrics' columnar format doesn't
give any real advantage here. It also needs an extra relay container for Grafana.
Prometheus with short retention does the job and is simpler to debug on a headless device.

## Why Grafana over a static dashboard

Mainly for the histogram quantile panels — visualising p95 spike duration in native
Grafana is much cleaner than building it custom. Also wanted threshold markers and
zoom for the time series.
