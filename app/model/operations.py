from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union, Any
from pydantic import BaseModel, Field

from ..shuffle import constrained_shuffle, stable_shuffle, random_shuffle

def _parse_sort_key(entry: str) -> tuple[str, bool]:
    field, _, direction = entry.partition(" ")
    return field, direction.strip().lower() == "desc"

class ShuffleKind(str, Enum):
    RANDOM = 'random'
    CONSTRAINED = 'constrained'
    STABLE = 'stable'

class BaseOperator(BaseModel):
    def apply(self, items: list[Any]) -> list[Any]:
        return items

class SortOp(BaseOperator):
    sort: list[str] = Field(min_length=1)

    def apply(self, items: list[Any]) -> list[Any]:
        for field, desc in reversed([ _parse_sort_key(e) for e in self.sort ]):
            items.sort(key = lambda s: getattr(s, field), reverse=desc)
        return items

class PartitionOp(BaseOperator):
    partition: list[str] = Field(min_length=1)

    def apply(self, items: list[Any]) -> list[Any]:
        partition = 0
        previous = None
        result = []

        for song in items:
            current = tuple(getattr(song, field) for field in self.partition)

            if previous is not None and current != previous:
                partition += 1

            result.append(song.model_copy(update={
                "partition": partition
            }))

            previous = current

        return result

class ConstrainedShuffleOp(BaseOperator):
    shuffle: Literal["constrained"]
    by: list[str] = Field(min_length=1)

    def apply(self, items: list[Any]) -> list[Any]:
        key_fn = lambda s: tuple(getattr(s, field) for field in self.by)
        return list(constrained_shuffle(items, key_fn))

class StableShuffleOp(BaseOperator):
    shuffle: Literal["stable"]
    by: list[str] = Field(min_length=1)

    def apply(self, items: list[Any]) -> list[Any]:
        key_fn = lambda s: tuple(getattr(s, field) for field in self.by)
        return list(stable_shuffle(items, key_fn))

class RandomShuffleOp(BaseOperator):
    shuffle: Literal["random"]

    def apply(self, items: list[Any]) -> list[Any]:
        return list(random_shuffle(items))

class TopOp(BaseOperator):
    top: int = Field(ge=0)

    def apply(self, items: list[Any]) -> list[Any]:
        return items[:self.top]

ShuffleOp = Annotated[
    Union[ConstrainedShuffleOp, StableShuffleOp, RandomShuffleOp],
    Field(discriminator = "shuffle")
]

Operation = Union[SortOp, PartitionOp, ShuffleOp, TopOp]
