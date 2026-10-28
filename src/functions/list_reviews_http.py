import json
import logging
from typing import Any, Literal

import azure.functions as func

from src.app.list_reviews import list_reviews
from src.config.composition_root import create_list_reviews_deps
from src.domain.review import Review, to_iso_string

bp = func.Blueprint()
logger = logging.getLogger(__name__)

ListReviewsStage = Literal[
    "dependency-construction",
    "use-case-execution",
    "response-mapping",
]


@bp.function_name("listReviewsHttp")
@bp.route(route="reviews", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
async def list_reviews_http(req: func.HttpRequest) -> func.HttpResponse:
    stage: ListReviewsStage = "dependency-construction"

    try:
        deps = create_list_reviews_deps()

        stage = "use-case-execution"
        result = await list_reviews(deps)

        stage = "response-mapping"
        reviews = [_to_review_dto(review) for review in result.data]
        return _json_response(200, {"reviews": reviews, "totalCount": len(reviews)})
    except Exception:
        logger.error(
            "Review API request failed",
            extra={
                "operation": "list-reviews",
                "stage": stage,
                "category": "unexpected",
            },
        )
        return _json_response(500, {"error": "Internal server error"})


def _to_review_dto(review: Review) -> dict[str, Any]:
    return {
        "id": review.id,
        "rating": review.rating,
        "title": review.title,
        "comment": review.comment,
        "createdAt": to_iso_string(review.created_at),
    }


def _json_response(status: int, body: dict[str, Any]) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body), status_code=status, mimetype="application/json"
    )
