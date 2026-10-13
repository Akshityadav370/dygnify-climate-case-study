"""Pre-warm the cache for demo cities by calling the public API.

Usage: uv run python -m scripts.seed --api http://localhost:8000
"""

import argparse
import time

import httpx

DEMO_REGIONS = [
    {"type": "point", "lat": 28.61, "lon": 77.21, "label": "Delhi, India"},
    {"type": "point", "lat": 33.45, "lon": -112.07, "label": "Phoenix, United States"},
    {"type": "point", "lat": 48.86, "lon": 2.35, "label": "Paris, France"},
    {"type": "point", "lat": -33.87, "lon": 151.21, "label": "Sydney, Australia"},
    {"type": "point", "lat": 6.52, "lon": 3.38, "label": "Lagos, Nigeria"},
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--start", type=int, default=1990)
    parser.add_argument("--end", type=int, default=2020)
    args = parser.parse_args()

    with httpx.Client(base_url=args.api, timeout=120) as client:
        for region in DEMO_REGIONS:
            body = {"hazard": "heatwave", "region": region, "start_year": args.start, "end_year": args.end}
            started = time.monotonic()
            response = client.post("/api/analyze", json=body)
            took = time.monotonic() - started
            if response.status_code == 200:
                data = response.json()
                print(f"OK   {region['label']:<28} cached={data['cached']!s:<5} {took:5.1f}s  {data['insights'][0][:70]}")
            else:
                print(f"FAIL {region['label']:<28} HTTP {response.status_code}: {response.text[:120]}")
            time.sleep(7)  # stay under the 10/minute analyze limit


if __name__ == "__main__":
    main()
