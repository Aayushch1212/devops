# Edge Robot Observability Stack — 10xConstruction DevOps Assignment

> **Platform:** 2-core 2 GHz CPU · 500 MB RAM · Docker
> **Memory budget:** < 300 MB for the entire stack
> **Stack:** Python sensor service + Prometheus + Grafana

---

## Video Walkthrough

> [https://www.loom.com/share/41b11843615c41c5964e9b1155733101]

---

## Quick Start

```bash
git clone https://github.com/Aayushch1212/devops.git
cd devops

# Build and start everything
docker compose up -d --build

# Verify containers
docker ps

# Check memory usage
docker stats --no-stream
```

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana Dashboard | http://localhost:3000 | admin / edge-robot-2024 |
| Prometheus UI | http://localhost:9090 | — |
| Sensor /metrics | http://localhost:8000/metrics | — |
| Sensor /health | http://localhost:8000/health | — |

---

## Repository Structure

```
.
├── sensor_service.py     # Optimised + fixed Python sensor service
├── Dockerfile            # Slim Python 3.11 image
├── requirements.txt      # prometheus-client only
├── prometheus.yml        # Memory-tuned config (6h retention, WAL compression)
├── docker-compose.yml    # Optimised compose with mem_limit per service
└── README.md
```

---

## Bugs Fixed in sensor_service.py

### Bug 1 — CPU Busy-Loop (CRITICAL)
**Original:**
```python
for _ in range(2000000):
    pass
```
Running 2 million iterations on every single Prometheus scrape pegged the CPU at ~100% continuously.

**Fix:** Removed entirely. Moved all computation to a background thread with `time.sleep(1)` between readings. CPU dropped from ~100% to <5%.

---

### Bug 2 — Memory Leak (CRITICAL)
**Original:**
```python
data_blob = "X" * 5_000_000
temp_data = data_blob * random.randint(1, 3)
```
Allocating 5–15 MB of string data on every scrape request, never freed. Over time this caused the container to OOM crash.

**Fix:** Removed `data_blob` entirely. Replaced with `deque(maxlen=60)` for a bounded sliding window — constant memory at ~1 KB regardless of uptime.

---

### Bug 3 — Scrape Delays (SCRAPE FAILURES)
**Original:** All computation happened inside the `/metrics` HTTP handler, blocking the response for several seconds and causing Prometheus scrape timeouts.

**Fix:** All sensor work now runs in a background thread. The `/metrics` handler only serializes the pre-computed Prometheus registry — completing in under 5ms.

---

### Bug 4 — Missing Custom Metric
**Original:** No histogram or meaningful distribution metric.

**Fix:** Added `sensor_cpu_spike_duration_seconds` histogram to track how long CPU spikes last, enabling p95 latency queries via PromQL.

---

## Custom Metric: `sensor_cpu_spike_duration_seconds`

| Field | Value |
|-------|-------|
| Type | Histogram |
| Buckets | 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0 seconds |
| Why Histogram | Reveals distribution — are spikes benign (<100ms) or scrape-blocking (>500ms)? |

**Key PromQL queries:**
```promql
# p95 spike duration over 5 min window
histogram_quantile(0.95, rate(sensor_cpu_spike_duration_seconds_bucket[5m]))

# Spike rate per minute
rate(sensor_cpu_spike_duration_seconds_count[1m]) * 60
```

---

## Memory Budget

Measured after 22 hours of continuous operation:

| Component | RAM Limit | Actual RSS (22h) |
|-----------|-----------|------------------|
| sensor-service | 40 MB | ~24.5 MB |
| prometheus | 100 MB | ~65.9 MB |
| grafana | 150 MB | ~97.9 MB |
| **TOTAL** | **290 MB** | **~188 MB** |

Total actual usage ~188 MB after 22 hours — 37% under the 300 MB budget.
All containers remain within their individual hard limits at sustained load.

---

## Prometheus Tuning

```yaml
--storage.tsdb.retention.time=6h   # short retention = less RAM
--storage.tsdb.wal-compression     # compress WAL segments
--query.max-concurrency=2          # limit parallel queries
scrape_interval: 15s               # balanced interval for edge devices
```

---

## Grafana Memory Savings

```yaml
GF_ALERTING_ENABLED: "false"
GF_UNIFIED_ALERTING_ENABLED: "false"
GF_PLUGINS_PREINSTALL: ""
GF_ANALYTICS_REPORTING_ENABLED: "false"
```

---

## Design Choices

### Why Prometheus over VictoriaMetrics?
- Native Grafana datasource — no extra relay container needed, saves ~15 MB RAM
- WAL compression + 6h retention keeps RSS under 100 MB even after 22h uptime
- Fewer than 100 active time series — VictoriaMetrics columnar format offers no advantage at this scale
- Well-understood failure modes, easier to debug on a headless edge device

### Why Grafana over static dashboard?
- Native PromQL histogram quantile visualization for the custom CPU spike metric
- Threshold markers, zoom, and time range selection
- Kept under 100 MB by disabling alerting and analytics engines via environment variables

---

## One More Week — Improvement

Deploy **Alertmanager** (~15 MB RAM) alongside Prometheus with alert rules:
- Fire if CPU spike p95 > 0.4s sustained for 2 minutes
- Fire if event failure rate > 1/min
- Route alerts to Slack webhook for on-call notification

This converts the stack from passive observation to active incident detection — critical for an autonomous edge device with no one watching a dashboard 24/7.
