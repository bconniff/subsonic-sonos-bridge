import math
from collections import defaultdict
from dataclasses import dataclass, field
from random import Random
from typing import Any

@dataclass(slots=True)
class Bucket:
    key: Any
    items: list
    spacing: float
    due: float

    last_seen: float = -math.inf
    count: int = 0
    age: float = 0.0
    gate: int = 0
    lateness: float = 0.0
    slack: float = 0.0

class BaseConstrainedShuffle:
    def __init__(self, key_fn, rng=None):
        self.key_fn = key_fn
        self.rng = rng if rng is not None else Random()

    def gate(self, count, remaining):
        return 0

    def score(self, bucket):
        return bucket.lateness

    def fallback(self, buckets):
        return buckets

    def shuffle(self, items):
        grouped = defaultdict(list)
        for item in items:
            grouped[self.key_fn(item)].append(item)
        for group in grouped.values():
            self.rng.shuffle(group)

        total = sum(len(group) for group in grouped.values())
        buckets = {}
        for key, group in grouped.items():
            gap = total / len(group)
            buckets[key] = Bucket(key, group, gap, self.rng.random() * gap)

        remaining = total
        position = 0

        while buckets:
            rows = list(buckets.values())

            for b in rows:
                b.count = len(b.items)
                b.age = position - b.last_seen
                b.gate = self.gate(b.count, remaining)
                b.lateness = (position - b.due) / b.spacing

                earliest = max(position + 1, b.last_seen + b.gate)
                b.slack = (total - 1) - (earliest + (b.count - 1) * b.gate)

            ready = [ b for b in rows if b.age >= b.gate ] or self.fallback(rows)

            forced = [ b for b in ready if b.slack < 0 ]
            if forced:
                ready = [ max(forced, key = lambda b: b.count) ]

            scores = [ self.score(b) for b in ready ]
            top = max(scores)
            weights = [ math.exp(s - top) for s in scores ]
            chosen = self.rng.choices(ready, weights=weights)[0]

            yield chosen.items.pop()

            if chosen.items:
                chosen.due += chosen.spacing
                chosen.last_seen = position
            else:
                del buckets[chosen.key]

            position += 1
            remaining -= 1

class ConstrainedShuffle(BaseConstrainedShuffle):
    def __init__(self, key_fn, min_distance=2, sharpness=10.0, rng=None):
        super().__init__(key_fn, rng=rng)
        self.target = min_distance + 1
        self.sharpness = sharpness

    def gate(self, count, remaining):
        if count <= 1:
            return self.target
        return max(1, min(self.target, (remaining - 1) // (count - 1)))

    def fallback(self, buckets):
        best = max(b.age / b.gate for b in buckets)
        return [b for b in buckets if b.age / b.gate == best]

    def score(self, bucket):
        return self.sharpness * bucket.lateness

def constrained_shuffle(items, key_fn):
    return ConstrainedShuffle(key_fn).shuffle(items)

def stable_shuffle(items, key_fn):
    rng = Random()

    grouped = defaultdict(list)
    for item in items:
        grouped[key_fn(item)].append(item)

    grouped_list = list(grouped.items())
    rng.shuffle(grouped_list)

    for key, values in grouped_list:
        for value in values:
            yield value

def random_shuffle(items):
    rng = Random()
    items = items.copy()
    rng.shuffle(items)
    return items
