import asyncio
import json
import sys

from scripts.load_settings import load_settings
from scripts.test_reviews import TEST_REVIEWS
from src.config.composition_root import (
    close_review_repo,
    get_cosmos_target,
    get_review_repo,
)


async def main() -> None:
    print("Seed target:", json.dumps(get_cosmos_target(), indent=2))
    print("Reruns overwrite the five sample IDs and retain unrelated records.")
    print(
        "Writes are sequential, not transactional; "
        "a failure can leave earlier writes saved."
    )

    try:
        review_repo = get_review_repo()
        for review in TEST_REVIEWS:
            await review_repo.save(review)
            print(f"Seeded review {review.id}")
    finally:
        await close_review_repo()

    print("Completed seeding reviews.")


if __name__ == "__main__":
    # Settings load before seeding, like a preload: an optional environment
    # name selects <name>.settings.json, and "shell" loads no file.
    load_settings(sys.argv[1] if len(sys.argv) > 1 else None)

    try:
        asyncio.run(main())
    except Exception as error:
        print(
            "Failed to seed reviews:",
            str(error) or "Unexpected seeding failure",
            file=sys.stderr,
        )
        sys.exit(1)
