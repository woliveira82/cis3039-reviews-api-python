import asyncio
import dataclasses
import json
import sys
from collections.abc import Sequence
from datetime import datetime

from src.app.add_review import AddReviewCommand, AddReviewDeps, add_review
from src.app.list_reviews import ListReviewsDeps, list_reviews
from src.domain.review import Review, to_iso_string
from src.infra.fake_review_repo import FakeReviewRepo

FIXED_ID = "demo-review-1"
FIXED_DATE = datetime.fromisoformat("2026-01-02T03:04:05.000Z")


class MarkingReviewRepo:
    """The marker makes it visible that add_review returns the value from save()."""

    def __init__(self, inner: FakeReviewRepo) -> None:
        self._inner = inner

    async def get_by_id(self, id: str) -> Review | None:
        return await self._inner.get_by_id(id)

    async def list(self) -> Sequence[Review]:
        return await self._inner.list()

    async def save(self, review: Review) -> Review:
        return await self._inner.save(
            dataclasses.replace(review, title=f"{review.title} (persisted)")
        )


async def main() -> None:
    review_repo = MarkingReviewRepo(FakeReviewRepo())

    added = await add_review(
        AddReviewDeps(
            review_repo=review_repo,
            generate_id=lambda: FIXED_ID,
            now=lambda: FIXED_DATE,
        ),
        AddReviewCommand(
            rating=5,
            title="Explicit dependencies",
            comment="This demonstration does not connect to Cosmos DB.",
        ),
    )

    if not added.success:
        raise RuntimeError("The add review demonstration unexpectedly failed.")

    print("Add returned persisted review:")
    print(json.dumps(to_dto(added.data), indent=2))

    listed = await list_reviews(ListReviewsDeps(review_repo=review_repo))
    print(f"\nList returned {len(listed.data)} review:")
    print(json.dumps([to_dto(review) for review in listed.data], indent=2))

    found = await review_repo.get_by_id(FIXED_ID)
    missing = await review_repo.get_by_id("missing")
    print(f"\nget_by_id found: {found.id if found else 'None'}")
    print(f"get_by_id missing returns None: {missing is None}")

    if found is None:
        raise RuntimeError("The saved review could not be read from the fake.")
    try:
        found.created_at = found.created_at.replace(year=2000)  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        print("Assigning to a returned review raises FrozenInstanceError.")

    read_again = await review_repo.get_by_id(FIXED_ID)
    if read_again is None:
        raise RuntimeError("The saved review disappeared from the fake.")
    print(
        f"Stored date after attempted mutation: {to_iso_string(read_again.created_at)}"
    )


def to_dto(review: Review) -> dict[str, object]:
    return {
        "id": review.id,
        "rating": review.rating,
        "title": review.title,
        "comment": review.comment,
        "createdAt": to_iso_string(review.created_at),
    }


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print(str(error) or "The review demonstration failed.", file=sys.stderr)
        sys.exit(1)
