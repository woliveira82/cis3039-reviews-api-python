import os
import uuid
from datetime import UTC, datetime

from src.app.add_review import AddReviewDeps
from src.app.list_reviews import ListReviewsDeps
from src.domain.review_repo import ReviewRepo
from src.infra.cosmos_review_repo import CosmosReviewRepo, CosmosReviewRepoOptions

# These non-secret values remain hard-coded for the Part C student exercise.
COSMOS_OPTIONS = {
    "endpoint": "https://reviews-lab-ab47-cosmos-uksouth.documents.azure.com:443/",
    "database_id": "reviews-db",
    "container_id": "reviews",
}


def get_cosmos_target() -> dict[str, str]:
    """Keep command-line target summaries free from credentials."""
    return dict(COSMOS_OPTIONS)


_cached_review_repo: CosmosReviewRepo | None = None


# Importing the composition root must not require configuration or create a client.
def get_review_repo() -> ReviewRepo:
    global _cached_review_repo

    if _cached_review_repo is None:
        key = os.environ.get("COSMOS_KEY")
        if not key or key.strip() == "":
            raise RuntimeError(
                "COSMOS_KEY must be set to a non-empty Cosmos DB account key."
            )

        _cached_review_repo = CosmosReviewRepo(
            CosmosReviewRepoOptions(**COSMOS_OPTIONS, key=key)
        )
    return _cached_review_repo


async def close_review_repo() -> None:
    """Standalone scripts close the client before their event loop ends."""
    global _cached_review_repo

    if _cached_review_repo is not None:
        await _cached_review_repo.close()
        _cached_review_repo = None


def create_add_review_deps() -> AddReviewDeps:
    return AddReviewDeps(
        review_repo=get_review_repo(),
        generate_id=lambda: str(uuid.uuid4()),
        now=lambda: datetime.now(UTC),
    )


def create_list_reviews_deps() -> ListReviewsDeps:
    return ListReviewsDeps(review_repo=get_review_repo())
