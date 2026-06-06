from __future__ import annotations

import argparse
import csv
import ipaddress
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROTOCOLS = ("TCP", "UDP", "ICMP")
COMMON_PORTS = (22, 25, 53, 80, 110, 123, 143, 443, 587, 993, 995, 3306, 5432)
RARE_PORTS = (4444, 5555, 6667, 8081, 31337)


def _random_private_ip() -> str:
    network = ipaddress.ip_network(random.choice(("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))
    return str(network.network_address + random.randint(1, network.num_addresses - 2))


def _normal_row(timestamp: datetime) -> dict[str, object]:
    port = random.choice(COMMON_PORTS)
    protocol = "ICMP" if port == 0 else random.choices(PROTOCOLS, weights=(0.72, 0.25, 0.03), k=1)[0]
    duration = round(random.uniform(0.2, 120.0), 3)
    packets = random.randint(3, 900)
    bytes_sent = int(max(64, random.gauss(45_000, 30_000)))

    return {
        "timestamp": timestamp.isoformat(),
        "src_ip": _random_private_ip(),
        "dst_ip": _random_private_ip(),
        "port": port,
        "protocol": protocol,
        "bytes_sent": bytes_sent,
        "duration": duration,
        "packets": packets,
    }


def _inject_anomaly(row: dict[str, object]) -> dict[str, object]:
    anomaly_type = random.choice(("data_exfiltration", "rare_port", "port_scan"))

    if anomaly_type == "data_exfiltration":
        row["bytes_sent"] = random.randint(2_000_000, 25_000_000)
        row["duration"] = round(random.uniform(180.0, 900.0), 3)
        row["packets"] = random.randint(4_000, 40_000)
    elif anomaly_type == "rare_port":
        row["port"] = random.choice(RARE_PORTS)
        row["protocol"] = "TCP"
        row["bytes_sent"] = random.randint(300_000, 3_500_000)
        row["packets"] = random.randint(1_000, 8_000)
    else:
        row["duration"] = round(random.uniform(0.01, 0.3), 3)
        row["packets"] = random.randint(2_000, 18_000)
        row["bytes_sent"] = random.randint(20_000, 250_000)
        row["port"] = random.choice(COMMON_PORTS + RARE_PORTS)
        row["protocol"] = "TCP"

    return row


def generate_logs(rows: int = 500, anomaly_rate: float = 0.08, seed: int | None = 42) -> list[dict[str, object]]:
    if seed is not None:
        random.seed(seed)

    start = datetime.now(timezone.utc) - timedelta(minutes=rows)
    logs: list[dict[str, object]] = []

    for index in range(rows):
        timestamp = start + timedelta(seconds=index * random.randint(20, 90))
        row = _normal_row(timestamp)

        if random.random() < anomaly_rate:
            row = _inject_anomaly(row)

        logs.append(row)

    return logs


def write_logs(output: Path, rows: int = 500, anomaly_rate: float = 0.08, seed: int | None = 42) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    records = generate_logs(rows=rows, anomaly_rate=anomaly_rate, seed=seed)

    with output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fake NetFlow-style traffic logs.")
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--output", type=Path, default=Path("data/netflow_logs.csv"))
    parser.add_argument("--anomaly-rate", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output = write_logs(args.output, rows=args.rows, anomaly_rate=args.anomaly_rate, seed=args.seed)
    print(f"Generated {args.rows} rows at {output}")


if __name__ == "__main__":
    main()

