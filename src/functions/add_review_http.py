import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

import azure.functions as func

from src.app.add_review import AddReviewCommand, add_review
from src.config.composition_root import create_add_review_deps
from src.domain.review import Review, to_iso_string

bp = func.Blueprint()
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestIssue:
    field: Literal["body", "rating", "title", "comment"]
    message: str


@dataclass(frozen=True)
class ParseCommandSuccess:
    data: AddReviewCommand
    success: Literal[True] = True


@dataclass(frozen=True)
class ParseCommandFailure:
    issues: tuple[RequestIssue, ...]
    success: Literal[False] = False


ParseCommandResult = ParseCommandSuccess | ParseCommandFailure

AddReviewStage = Literal[
    "request-parsing",
    "dependency-construction",
    "use-case-execution",
    "response-mapping",
]


@bp.function_name("addReviewHttp")
@bp.route(route="reviews", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
async def add_review_http(req: func.HttpRequest) -> func.HttpResponse:
    stage: AddReviewStage = "request-parsing"

    try:
        try:
            body = req.get_json()
        except ValueError:
            return _bad_request(
                [RequestIssue("body", "Request body must contain valid JSON")]
            )

        parsed = _parse_command(body)
        if not parsed.success:
            return _bad_request(parsed.issues)

        stage = "dependency-construction"
        deps = create_add_review_deps()

        stage = "use-case-execution"
        result = await add_review(deps, parsed.data)
        if not result.success:
            return _bad_request(result.issues)

        stage = "response-mapping"
        return _json_response(201, {"review": _to_review_dto(result.data)})
    except Exception:
        logger.error(
            "Review API request failed",
            extra={"operation": "add-review", "stage": stage, "category": "unexpected"},
        )
        return _internal_server_error()


def _parse_command(body: Any) -> ParseCommandResult:
    if not isinstance(body, dict):
        return ParseCommandFailure(
            issues=(RequestIssue("body", "Request body must be a JSON object"),)
        )

    issues: list[RequestIssue] = []
    rating = body.get("rating")
    title = body.get("title")
    comment = body.get("comment")

    # bool is a subclass of int, but JSON true is not a number.
    if not isinstance(rating, int | float) or isinstance(rating, bool):
        issues.append(RequestIssue("rating", "Rating must be a number"))

    if not isinstance(title, str):
        issues.append(RequestIssue("title", "Title must be a string"))

    if not isinstance(comment, str):
        issues.append(RequestIssue("comment", "Comment must be a string"))

    if issues:
        return ParseCommandFailure(issues=tuple(issues))

    return ParseCommandSuccess(
        data=AddReviewCommand(rating=rating, title=title, comment=comment)
    )


def _to_review_dto(review: Review) -> dict[str, Any]:
    return {
        "id": review.id,
        "rating": review.rating,
        "title": review.title,
        "comment": review.comment,
        "createdAt": to_iso_string(review.created_at),
    }


def _bad_request(issues) -> func.HttpResponse:
    return _json_response(
        400,
        {
            "issues": [
                {"field": issue.field, "message": issue.message} for issue in issues
            ]
        },
    )


def _internal_server_error() -> func.HttpResponse:
    return _json_response(500, {"error": "Internal server error"})


def _json_response(status: int, body: dict[str, Any]) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body), status_code=status, mimetype="application/json"
    )
