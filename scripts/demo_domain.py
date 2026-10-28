import json
from datetime import datetime

from src.domain.review import CreateReviewParams, Review, create_review, to_iso_string


def main() -> None:
    valid = create_review(
        CreateReviewParams(
            id="demo-review-1",
            rating=5,
            title="Clear architecture",
            comment="The domain factory returns a validated review.",
            created_at=datetime.fromisoformat("2026-01-02T03:04:05.000Z"),
        )
    )

    if not valid.success:
        raise RuntimeError("The valid domain demonstration unexpectedly failed.")

    print("Valid review:")
    print(json.dumps(to_dto(valid.data), indent=2))

    invalid = create_review(
        CreateReviewParams(
            id=" ",
            rating=2.5,  # type: ignore[arg-type]
            title=" ",
            comment="",
            # Naive datetimes have no timezone, so they are rejected.
            created_at=datetime(2026, 1, 2, 3, 4, 5),
        )
    )

    if invalid.success:
        raise RuntimeError("The invalid domain demonstration unexpectedly succeeded.")

    print("\nInvalid review issues:")
    for issue in invalid.issues:
        print(f"- {issue.field}: {issue.message}")


def to_dto(review: Review) -> dict[str, object]:
    return {
        "id": review.id,
        "rating": review.rating,
        "title": review.title,
        "comment": review.comment,
        "createdAt": to_iso_string(review.created_at),
    }


if __name__ == "__main__":
    main()
