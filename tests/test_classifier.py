import csv
from collections import Counter
from pathlib import Path

import pytest

from app.classifier import Category, classify

DATA = Path(__file__).parent / "data" / "messages.csv"


def load_cases():
    with DATA.open(encoding="utf-8") as f:
        return [(r["text"], r["expected"] or None) for r in csv.DictReader(f)]


CASES = load_cases()


@pytest.mark.parametrize("text,expected", CASES, ids=[c[0][:40] for c in CASES])
def test_dataset(text, expected):
    match = classify(text)
    got = match.category.value if match else None
    assert got == expected, f"reason={match.reason if match else None}"


def test_metrics_report(capsys):
    stats = Counter()
    for text, expected in CASES:
        m = classify(text)
        got = m.category.value if m else None
        if got and got == expected:
            stats["tp"] += 1
        elif got:
            stats["fp"] += 1
        elif expected:
            stats["fn"] += 1
    precision = stats["tp"] / max(stats["tp"] + stats["fp"], 1)
    recall = stats["tp"] / max(stats["tp"] + stats["fn"], 1)
    print(f"\nprecision={precision:.2f} recall={recall:.2f} {dict(stats)}")


def test_empty():
    assert classify("") is None


def test_yo_normalized():
    assert classify("Продам вторичный щебёнь").category is Category.SELL
