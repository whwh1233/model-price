"""Refresh the local v2 pricing snapshot without starting FastAPI."""

import asyncio
import logging

from services.offering_merger import run_refresh_pipeline


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    _, report, _ = await run_refresh_pipeline(force_network=True)
    counts = report.counts
    print(
        "snapshot refreshed: "
        f"{counts.entities_total} entities, "
        f"{counts.offerings_total} offerings, "
        f"{counts.entities_new} new, "
        f"{counts.entities_removed} removed"
    )


if __name__ == "__main__":
    asyncio.run(main())
