from __future__ import annotations

import argparse
import csv
import ipaddress
import random
from datetime import datetime, timedelta
from pathlib import Path


PROTOCOLS = ("TCP", "UDP", "ICMP")
COMMON_PORTS = (22, 25, 53, 80, 110, 123, 143, 443, 587, 993, 995, 3306, 5432)
RARE_PORTS = (4444, 31337)


def _random_private_ip() -> str:
    network = ipaddress.ip_network(random.choice(("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))
    return str(network.network_address + random.randint(1, network.num_addresses - 2))


def _normal_row(timestamp: datetime) -> dict[str, object]:
    port = random.choice(COMMON_PORTS)
    protocol = random.choices(PROTOCOLS, weights=(0.74, 0.23, 0.03), k=1)[0]
    duration = round(random.uniform(0.2, 8.0), 2)
    packets = random.randint(8, 180)
    bytes_sent = random.randint(1_200, 95_000)

    return {
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "src_ip": _random_private_ip(),
        "dst_ip": _random_private_ip(),
        "port": port,
        "protocol": protocol,
        "bytes_sent": bytes_sent,
        "duration": duration,
        "packets": packets,
    }


def _inject_anomaly(row: dict[str, object]) -> dict[str, object]:
    row["port"] = random.choice(RARE_PORTS)
    row["protocol"] = "TCP"
    row["bytes_sent"] = random.randint(910_000, 3_500_000)
    row["duration"] = round(random.uniform(0.01, 0.09), 2)
    row["packets"] = random.randint(520, 2_500)
    if random.random() < 0.4:
        row["dst_ip"] = f"{random.randint(11, 223)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
    return row


def generate_logs(rows: int = 500, anomaly_count: int = 20, seed: int | None = 42) -> list[dict[str, object]]:
    if anomaly_count >= rows:
        raise ValueError("anomaly_count must be lower than rows")

    if seed is not None:
        random.seed(seed)

    start = datetime(2024, 1, 15, 10, 23, 1)
    logs: list[dict[str, object]] = []

    for index in range(rows - anomaly_count):
        logs.append(_normal_row(start + timedelta(seconds=index * 3)))

    for index in range(anomaly_count):
        timestamp = start + timedelta(seconds=(rows - anomaly_count + index) * 3)
        logs.append(_inject_anomaly(_normal_row(timestamp)))

    random.shuffle(logs)
    logs.sort(key=lambda row: row["timestamp"])

    return logs


def write_logs(output: Path, rows: int = 500, anomaly_count: int = 20, seed: int | None = 42) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    records = generate_logs(rows=rows, anomaly_count=anomaly_count, seed=seed)

    with output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate fake NetFlow-style traffic logs.")
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--output", type=Path, default=Path("fake_logs.csv"))
    parser.add_argument("--anomaly-count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output = write_logs(args.output, rows=args.rows, anomaly_count=args.anomaly_count, seed=args.seed)
    print(f"Generated {args.rows} rows at {output}")


if __name__ == "__main__":
    main()
