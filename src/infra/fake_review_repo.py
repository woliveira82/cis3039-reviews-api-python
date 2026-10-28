from collections.abc import Iterable, Sequence

from src.domain.review import Review


class FakeReviewRepo:
    # Reviews are frozen dataclasses with immutable fields, so stored values
    # cannot be changed through the references this fake returns.
    def __init__(self, initial_reviews: Iterable[Review] = ()) -> None:
        self._reviews: dict[str, Review] = {
            review.id: review for review in initial_reviews
        }

    async def get_by_id(self, id: str) -> Review | None:
        return self._reviews.get(id)

    async def list(self) -> Sequence[Review]:
        return list(self._reviews.values())

    async def save(self, review: Review) -> Review:
        self._reviews[review.id] = review
        return review
