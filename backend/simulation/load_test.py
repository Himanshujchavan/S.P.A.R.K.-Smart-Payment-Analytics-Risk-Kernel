# simulation/load_test.py
# High-throughput asynchronous load testing and latency benchmarking script
# for the S.P.A.R.K. /score endpoint.

import argparse
import asyncio
import random
import time
import uuid
import httpx
import numpy as np

PAYMENT_METHODS = ["upi", "card", "netbanking", "wallet", "emandate"]
SAMPLE_BUYERS = [f"usr_{i:04d}" for i in range(100)]
SAMPLE_DEVICES = [f"dev_{i:04d}" for i in range(50)]
SAMPLE_IPS = [f"192.168.1.{i}" for i in range(1, 30)]


def generate_random_payload() -> dict:
    return {
        "txn_id": str(uuid.uuid4()),
        "buyer_id": random.choice(SAMPLE_BUYERS),
        "device_id": random.choice(SAMPLE_DEVICES),
        "amount": round(random.uniform(50.0, 35000.0), 2),
        "currency": "INR",
        "method": random.choice(PAYMENT_METHODS),
        "card_bin": f"4{random.randint(10000, 99999)}" if random.random() < 0.3 else None,
        "ip_address": random.choice(SAMPLE_IPS),
        "city": random.choice(["Bengaluru", "Mumbai", "Delhi", "Pune"]),
    }


async def send_scoring_request(
    client: httpx.AsyncClient,
    url: str,
    results: list,
    semaphore: asyncio.Semaphore,
):
    async with semaphore:
        payload = generate_random_payload()
        start = time.perf_counter()
        try:
            resp = await client.post(url, json=payload, timeout=10.0)
            latency_ms = (time.perf_counter() - start) * 1000.0
            results.append({
                "status": resp.status_code,
                "latency_ms": latency_ms,
                "tier": resp.json().get("decision") if resp.status_code == 200 else "error",
            })
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000.0
            results.append({"status": 0, "latency_ms": latency_ms, "error": str(e)})


async def run_benchmark(
    base_url: str,
    total_requests: int = 500,
    concurrency: int = 25,
):
    target_url = f"{base_url.rstrip('/')}/api/v1/score"
    print(f"\n========================================================")
    print(f" S.P.A.R.K. Scoring Endpoint Load Benchmark")
    print(f" Target: {target_url}")
    print(f" Total Requests: {total_requests} | Concurrency: {concurrency}")
    print(f"========================================================\n")

    results = []
    semaphore = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)

    start_total = time.perf_counter()
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [
            send_scoring_request(client, target_url, results, semaphore)
            for _ in range(total_requests)
        ]
        await asyncio.gather(*tasks)

    duration_total = time.perf_counter() - start_total
    rps = total_requests / duration_total if duration_total > 0 else 0

    successes = [r for r in results if r.get("status") == 200]
    latencies = [r["latency_ms"] for r in successes]

    print(f"Completed {len(results)} requests in {duration_total:.2f}s ({rps:.1f} req/sec)")
    print(f"Success count: {len(successes)} / {total_requests} ({(len(successes)/total_requests)*100:.1f}%)")

    if latencies:
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        avg = np.mean(latencies)
        print(f"\n--- Latency Breakdown (ms) ---")
        print(f"  Average: {avg:.2f} ms")
        print(f"  p50:     {p50:.2f} ms")
        print(f"  p95:     {p95:.2f} ms")
        print(f"  p99:     {p99:.2f} ms")

        # Tier breakdown
        tiers = [r.get("tier") for r in successes]
        print(f"\n--- Decisions Distribution ---")
        for tier in ["allow", "challenge", "block"]:
            count = tiers.count(tier)
            pct = (count / len(successes)) * 100 if successes else 0
            print(f"  {tier.capitalize():<10}: {count:>4} ({pct:>5.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Run S.P.A.R.K. scoring latency benchmark.")
    parser.add_argument("--url", default="http://localhost:8000", help="Base API URL")
    parser.add_argument("--requests", type=int, default=100, help="Total requests to send")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent workers")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.url, args.requests, args.concurrency))


if __name__ == "__main__":
    main()
