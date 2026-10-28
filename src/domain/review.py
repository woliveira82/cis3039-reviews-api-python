import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal


@dataclass(frozen=True)
class Review:
    """
    A review is valid only when all of its identity, content and timestamp
    fields satisfy the domain rules below.
    """

    id: str
    # product_id would be the partition key in a production application.
    rating: int
    title: str
    comment: str
    created_at: datetime


@dataclass(frozen=True)
class ReviewContent:
    rating: int
    title: str
    comment: str


@dataclass(frozen=True)
class CreateReviewParams:
    id: str
    rating: int
    title: str
    comment: str
    created_at: datetime


ReviewField = Literal["id", "rating", "title", "comment", "created_at"]


@dataclass(frozen=True)
class ReviewValidationIssue:
    field: ReviewField
    message: str


@dataclass(frozen=True)
class CreateReviewSuccess:
    data: Review
    success: Literal[True] = True


@dataclass(frozen=True)
class CreateReviewFailure:
    issues: tuple[ReviewValidationIssue, ...]
    success: Literal[False] = False


CreateReviewResult = CreateReviewSuccess | CreateReviewFailure

RATING_MIN = 1
RATING_MAX = 5
TITLE_MAX_LENGTH = 200
COMMENT_MAX_LENGTH = 5000


def create_review(params: CreateReviewParams) -> CreateReviewResult:
    """
    Creates a review through the single domain validation flow. Runtime checks
    remain necessary because type hints are not enforced by Python.
    """
    issues: list[ReviewValidationIssue] = []

    if not isinstance(params.id, str) or len(params.id.strip()) == 0:
        issues.append(ReviewValidationIssue("id", "ID is required and cannot be empty"))

    if not _is_integer(params.rating) or not (
        RATING_MIN <= params.rating <= RATING_MAX
    ):
        issues.append(
            ReviewValidationIssue(
                "rating",
                f"Rating must be an integer between {RATING_MIN} and {RATING_MAX}",
            )
        )

    if (
        not isinstance(params.title, str)
        or len(params.title.strip()) == 0
        or len(params.title) > TITLE_MAX_LENGTH
    ):
        issues.append(
            ReviewValidationIssue(
                "title", f"Title must be between 1 and {TITLE_MAX_LENGTH} characters"
            )
        )

    if (
        not isinstance(params.comment, str)
        or len(params.comment.strip()) == 0
        or len(params.comment) > COMMENT_MAX_LENGTH
    ):
        issues.append(
            ReviewValidationIssue(
                "comment",
                f"Comment must be between 1 and {COMMENT_MAX_LENGTH} characters",
            )
        )

    # Naive datetimes have no defined instant, so they cannot be stored safely.
    if (
        not isinstance(params.created_at, datetime)
        or params.created_at.utcoffset() is None
    ):
        issues.append(
            ReviewValidationIssue(
                "created_at", "Created date must be a timezone-aware datetime"
            )
        )

    if issues:
        return CreateReviewFailure(issues=tuple(issues))

    return CreateReviewSuccess(
        data=Review(
            id=params.id,
            rating=int(params.rating),
            title=params.title,
            comment=params.comment,
            created_at=params.created_at,
        )
    )


def _is_integer(value: object) -> bool:
    # bool is a subclass of int, but True is not a valid rating.
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value) and value.is_integer()


def to_iso_string(value: datetime) -> str:
    """Formats a timestamp like JavaScript's toISOString: 2025-10-01T10:00:00.000Z."""
    return (
        value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )
