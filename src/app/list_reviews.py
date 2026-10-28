from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from src.domain.review import Review
from src.domain.review_repo import ReviewRepo


@dataclass(frozen=True)
class ListReviewsResult:
    data: Sequence[Review]
    success: Literal[True] = True


@dataclass(frozen=True)
class ListReviewsDeps:
    review_repo: ReviewRepo


async def list_reviews(deps: ListReviewsDeps) -> ListReviewsResult:
    reviews = await deps.review_repo.list()
    return ListReviewsResult(data=reviews)
