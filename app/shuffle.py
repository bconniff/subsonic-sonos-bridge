import math

from collections import defaultdict
from random import shuffle, choices

def linear_recovery(min_distance = 2, window = 4):
    def _recovery(distance):
        if distance <= min_distance:
            return 0
        return min(distance - min_distance, window + 1)

    return _recovery

def default_weight(age, bucket_size):
    return age * bucket_size**2

def constrained_shuffle(items, key_fn, recovery_fn=linear_recovery(), weight_fn=default_weight):
    buckets = defaultdict(list)

    for item in items:
        buckets[key_fn(item)].append(item)
    for bucket in buckets.values():
        shuffle(bucket)

    last_seen = {}
    position = 0

    while buckets:
        candidates, weights = [], []

        for key, bucket in buckets.items():
            last = last_seen.get(key)
            age = max(position - last, 1) if last is not None else 1
            distance = age if last is not None else math.inf
            recovery = recovery_fn(distance)

            if not recovery:
                continue

            candidates.append(key)
            weights.append(weight_fn(age, len(bucket)) * recovery)

        if not candidates:
            candidates = list(buckets)
            weights = [
                weight_fn(max(position - last_seen.get(key, position), 1), len(buckets[key]))
                for key in candidates
            ]

        key = choices(candidates, weights=weights)[0]
        yield buckets[key].pop()

        if not buckets[key]:
            del buckets[key]

        last_seen[key] = position
        position += 1
