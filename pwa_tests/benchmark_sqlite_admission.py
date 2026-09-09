"""Isolated schema-opening benchmark; never reads a user/production database.

Run: .venv/bin/python -m pwa_tests.benchmark_sqlite_admission
See vmshpwa/docs/sqlite-admission-performance.md for interpretation.
"""

import argparse
import asyncio
import json
import platform
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path

from db_methods.pwa import PwaConnectionFactory, apply_schema_migrations
from helpers.pwa.request_trace import traced_thread


async def measure(factory, *, callers, iterations, admitted):
    def operation(connection):
        return connection.execute("SELECT 1").fetchone()

    async def client():
        elapsed = []
        for _ in range(iterations):
            started = time.perf_counter()
            if admitted:
                await factory.run_read_async(operation)
            else:
                await traced_thread(factory.run_read, operation)
            elapsed.append((time.perf_counter() - started) * 1000)
        return elapsed

    started = time.perf_counter()
    batches = await asyncio.gather(*(client() for _ in range(callers)))
    elapsed = sorted(value for batch in batches for value in batch)
    return {
        "admitted": admitted,
        "callers": callers,
        "operations": len(elapsed),
        "mean_ms": round(statistics.mean(elapsed), 2),
        "p95_ms": round(elapsed[min(len(elapsed) - 1, int(len(elapsed) * .95))], 2),
        "wall_seconds": round(time.perf_counter() - started, 2),
    }


async def benchmark(path, callers, iterations):
    factory = PwaConnectionFactory(path)
    for concurrency in (1, callers):
        for admitted in (False, True):
            print(json.dumps(await measure(
                factory, callers=concurrency, iterations=iterations, admitted=admitted
            )), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--callers", type=int, default=24)
    parser.add_argument("--iterations", type=int, default=25)
    args = parser.parse_args()
    if args.callers < 1 or args.iterations < 1:
        parser.error("callers and iterations must be positive")
    print(json.dumps({"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                      "platform": platform.platform()}), flush=True)
    with tempfile.TemporaryDirectory(prefix="vmsh-sqlite-benchmark-") as directory:
        path = Path(directory) / "synthetic.sqlite3"
        apply_schema_migrations(path)
        asyncio.run(benchmark(path, args.callers, args.iterations))


if __name__ == "__main__":
    main()
