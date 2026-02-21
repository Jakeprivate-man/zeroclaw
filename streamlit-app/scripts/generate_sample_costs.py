#!/usr/bin/env python3
"""Generate sample costs.jsonl file for testing the cost tracking UI.

This script creates realistic sample cost data that mimics what ZeroClaw
would generate during actual operation.

Usage:
    python scripts/generate_sample_costs.py
"""

import json
import uuid
from datetime import datetime, timedelta
import random
import os


def generate_sample_costs(output_file: str = "~/.zeroclaw/state/costs.jsonl", num_records: int = 50):
    """Generate sample cost records.

    Args:
        output_file: Path to output costs.jsonl file
        num_records: Number of records to generate
    """
    output_file = os.path.expanduser(output_file)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Model configurations with pricing (per million tokens)
    models = [
        {
            "model": "anthropic/claude-sonnet-4",
            "input_price": 3.0,
            "output_price": 15.0,
            "weight": 0.5  # Higher probability
        },
        {
            "model": "openai/gpt-4o",
            "input_price": 5.0,
            "output_price": 15.0,
            "weight": 0.3
        },
        {
            "model": "anthropic/claude-3.5-sonnet",
            "input_price": 3.0,
            "output_price": 15.0,
            "weight": 0.15
        },
        {
            "model": "openai/gpt-4o-mini",
            "input_price": 0.15,
            "output_price": 0.6,
            "weight": 0.05
        }
    ]

    # Generate session IDs (simulate 2-3 sessions)
    session_ids = [str(uuid.uuid4()) for _ in range(3)]

    # Generate records spanning last 30 days
    now = datetime.utcnow()
    records = []

    for i in range(num_records):
        # Random timestamp in last 30 days (weighted toward recent)
        days_ago = random.choices([0, 1, 2, 7, 14, 30], weights=[30, 20, 15, 15, 10, 10])[0]
        hours_ago = random.randint(0, 24)
        minutes_ago = random.randint(0, 60)

        timestamp = now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)

        # Select model based on weights
        model = random.choices(
            models,
            weights=[m["weight"] for m in models]
        )[0]

        # Generate realistic token counts
        input_tokens = random.randint(500, 5000)
        output_tokens = random.randint(200, 2000)
        total_tokens = input_tokens + output_tokens

        # Calculate cost
        cost_usd = (
            (input_tokens / 1_000_000) * model["input_price"] +
            (output_tokens / 1_000_000) * model["output_price"]
        )

        # Select session ID (recent records more likely to be in current session)
        if days_ago == 0:
            session_id = session_ids[0]  # Current session
        elif days_ago <= 2:
            session_id = random.choice(session_ids[:2])
        else:
            session_id = random.choice(session_ids)

        record = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "model": model["model"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost_usd, 6),
            "timestamp": timestamp.isoformat() + "Z"
        }

        records.append(record)

    # Sort by timestamp
    records.sort(key=lambda r: r["timestamp"])

    # Write to file
    with open(output_file, 'w') as f:
        for record in records:
            f.write(json.dumps(record) + '\n')

    print(f"Generated {len(records)} cost records")
    print(f"Output: {output_file}")

    # Print summary
    total_cost = sum(r["cost_usd"] for r in records)
    total_tokens = sum(r["total_tokens"] for r in records)

    print(f"\nSummary:")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Sessions: {len(session_ids)}")
    print(f"  Models used: {len(set(r['model'] for r in records))}")


if __name__ == "__main__":
    generate_sample_costs()
