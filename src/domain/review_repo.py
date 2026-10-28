from collections.abc import Sequence
from typing import Protocol

from src.domain.review import Review


class ReviewRepo(Protocol):
    """
    Persistence contract for reviews. Save is an unconditional upsert;
    concurrency protection is not part of this teaching example.
    """

    async def get_by_id(self, id: str) -> Review | None: ...

    async def list(self) -> Sequence[Review]: ...

    async def save(self, review: Review) -> Review: ...
