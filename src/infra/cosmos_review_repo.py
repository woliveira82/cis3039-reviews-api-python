from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from src.domain.review import (
    CreateReviewParams,
    Review,
    create_review,
    to_iso_string,
)


@dataclass(frozen=True)
class CosmosReviewRepoOptions:
    endpoint: str
    key: str
    database_id: str
    container_id: str


class CosmosReviewDocument(TypedDict):
    """
    Cosmos stores dates as ISO strings and uses /id as the partition key for
    this teaching example. The SDK does not validate returned data.
    """

    id: str
    rating: int
    title: str
    comment: str
    createdAt: str


OPTION_NAMES = ("endpoint", "key", "database_id", "container_id")


class CosmosReviewRepo:
    def __init__(self, options: CosmosReviewRepoOptions) -> None:
        _validate_options(options)

        self._client = CosmosClient(options.endpoint, credential=options.key)
        self._container = self._client.get_database_client(
            options.database_id
        ).get_container_client(options.container_id)

    async def get_by_id(self, id: str) -> Review | None:
        try:
            resource = await self._container.read_item(item=id, partition_key=id)
        except CosmosResourceNotFoundError:
            return None
        except Exception as error:
            raise RuntimeError("Failed to read review from Cosmos DB") from error
        return _from_document(resource)

    async def list(self) -> Sequence[Review]:
        """
        Loads the complete small teaching collection. Results have no ordering
        or pagination guarantee.
        """
        try:
            resources = [item async for item in self._container.read_all_items()]
            return [_from_document(resource) for resource in resources]
        except Exception as error:
            raise RuntimeError("Failed to list reviews from Cosmos DB") from error

    async def save(self, review: Review) -> Review:
        try:
            document = _to_document(review)
            resource = await self._container.upsert_item(dict(document))

            if resource is None:
                raise RuntimeError("Cosmos DB upsert returned no review resource")

            return _from_document(resource)
        except Exception as error:
            raise RuntimeError("Failed to save review to Cosmos DB") from error

    async def close(self) -> None:
        await self._client.close()


def _validate_options(options: CosmosReviewRepoOptions) -> None:
    if not isinstance(options, CosmosReviewRepoOptions):
        raise TypeError("CosmosReviewRepo requires a CosmosReviewRepoOptions object")

    invalid_options = [
        name
        for name in OPTION_NAMES
        if not isinstance(getattr(options, name), str)
        or len(getattr(options, name).strip()) == 0
    ]

    if invalid_options:
        raise ValueError(
            "CosmosReviewRepo requires non-empty options: " + ", ".join(invalid_options)
        )


def _to_document(review: Review) -> CosmosReviewDocument:
    result = create_review(
        CreateReviewParams(
            id=review.id,
            rating=review.rating,
            title=review.title,
            comment=review.comment,
            created_at=review.created_at,
        )
    )
    if not result.success:
        fields = ", ".join(issue.field for issue in result.issues)
        raise ValueError(f"Cannot persist invalid review fields: {fields}")

    return {
        "id": result.data.id,
        "rating": result.data.rating,
        "title": result.data.title,
        "comment": result.data.comment,
        "createdAt": to_iso_string(result.data.created_at),
    }


def _from_document(document: Any) -> Review:
    if not isinstance(document, dict):
        raise ValueError("Cosmos DB returned an invalid review document")

    if (
        not isinstance(document.get("id"), str)
        or not isinstance(document.get("rating"), int | float)
        or isinstance(document.get("rating"), bool)
        or not isinstance(document.get("title"), str)
        or not isinstance(document.get("comment"), str)
        or not isinstance(document.get("createdAt"), str)
    ):
        raise ValueError("Cosmos DB returned invalid review field types")

    try:
        created_at = datetime.fromisoformat(document["createdAt"])
    except ValueError:
        # Let domain validation report the unparseable timestamp.
        created_at = None

    result = create_review(
        CreateReviewParams(
            id=document["id"],
            rating=document["rating"],
            title=document["title"],
            comment=document["comment"],
            created_at=created_at,  # type: ignore[arg-type]
        )
    )

    if not result.success:
        fields = ", ".join(issue.field for issue in result.issues)
        raise ValueError(f"Cosmos DB returned invalid review fields: {fields}")

    return result.data
