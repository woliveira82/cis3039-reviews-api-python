from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from src.domain.review import (
    CreateReviewParams,
    Review,
    ReviewContent,
    ReviewValidationIssue,
    create_review,
)
from src.domain.review_repo import ReviewRepo

AddReviewCommand = ReviewContent


@dataclass(frozen=True)
class AddReviewSuccess:
    data: Review
    success: Literal[True] = True


@dataclass(frozen=True)
class AddReviewFailure:
    issues: tuple[ReviewValidationIssue, ...]
    success: Literal[False] = False


AddReviewResult = AddReviewSuccess | AddReviewFailure


@dataclass(frozen=True)
class AddReviewDeps:
    review_repo: ReviewRepo
    generate_id: Callable[[], str]
    now: Callable[[], datetime]


async def add_review(deps: AddReviewDeps, command: AddReviewCommand) -> AddReviewResult:
    id = deps.generate_id()
    created_at = deps.now()
    creation = create_review(
        CreateReviewParams(
            id=id,
            rating=command.rating,
            title=command.title,
            comment=command.comment,
            created_at=created_at,
        )
    )

    if not creation.success:
        # Generated values are operational failures, not client validation issues.
        invalid_generated_value = next(
            (issue for issue in creation.issues if issue.field in ("id", "created_at")),
            None,
        )

        if invalid_generated_value:
            raise RuntimeError(
                f"Generated review {invalid_generated_value.field} is invalid"
            )

        return AddReviewFailure(issues=creation.issues)

    saved = await deps.review_repo.save(creation.data)

    return AddReviewSuccess(data=saved)
