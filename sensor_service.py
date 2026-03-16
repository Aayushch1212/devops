

import time
import random
import threading
import logging
from collections import deque

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

REGISTRY = CollectorRegistry()


REQUEST_COUNT = Counter("sensor_requests_total", "Total sensor requests", registry=REGISTRY)
CPU_SPIKE = Gauge("sensor_cpu_spike", "Simulated CPU spike state", registry=REGISTRY)
PROCESS_LATENCY = Histogram("sensor_processing_latency_seconds", "Processing time", registry=REGISTRY)


sensor_temperature = Gauge("sensor_temperature_celsius", "Temperature reading", registry=REGISTRY)
sensor_humidity = Gauge("sensor_humidity_percent", "Humidity reading", registry=REGISTRY)
sensor_vibration = Gauge("sensor_vibration_ms2", "Vibration in m/s²", registry=REGISTRY)
events_processed = Counter("sensor_events_processed_total", "Total events processed", registry=REGISTRY)
events_failed = Counter("sensor_events_failed_total", "Total failed events", registry=REGISTRY)


cpu_spike_duration = Histogram(
    "sensor_cpu_spike_duration_seconds",
    "Duration of CPU spike events in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    registry=REGISTRY,
)


WINDOW = 60
recent_temps: deque = deque(maxlen=WINDOW)
_lock = threading.Lock()


def sensor_loop() -> None:
    log.info("Sensor loop started")
    while True:
        try:
            start = time.time()
            temp = round(random.uniform(20.0, 85.0), 2)
            hum  = round(random.uniform(30.0, 90.0), 2)
            vib  = round(random.uniform(0.0, 10.0), 3)

            with _lock:
                sensor_temperature.set(temp)
                sensor_humidity.set(hum)
                sensor_vibration.set(vib)
                recent_temps.append(temp)

            events_processed.inc()
            REQUEST_COUNT.inc()

            spike = 0
            if random.random() < 0.05:
                spike = 1
                _simulate_cpu_spike()

            CPU_SPIKE.set(spike)
            PROCESS_LATENCY.observe(time.time() - start)

        except Exception as exc:
            log.warning("Sensor read error: %s", exc)
            events_failed.inc()

        time.sleep(1)  # BUG FIX: missing in original → 100% CPU


def _simulate_cpu_spike() -> None:
    duration = random.uniform(0.01, 0.5)
    start = time.perf_counter()
    deadline = start + duration
    acc = 0
    while time.perf_counter() < deadline:
        acc += 1
    actual = time.perf_counter() - start
    cpu_spike_duration.observe(actual)


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/metrics":
            output = generate_latest(REGISTRY)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(output)))
            self.end_headers()
            self.wfile.write(output)
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        elif self.path == "/sensor":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args) -> None:
        pass


def main() -> None:
    port = 8000
    t = threading.Thread(target=sensor_loop, daemon=True, name="sensor-loop")
    t.start()
    log.info("Starting metrics server on :%d", port)
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
