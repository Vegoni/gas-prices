"""
Data ingestion service.

This is the "glue" between the EIA client and the database. It:
1. Calls the EIA client to fetch new price data
2. Converts PriceRecord objects into GasPrice model instances
3. Upserts them into the database (insert-or-ignore to handle duplicates)

WHY UPSERT?
EIA data is released weekly but past weeks can get revised. Using
INSERT OR IGNORE (via SQLAlchemy's unique constraint) means:
- First run: all rows insert normally
- Subsequent runs: duplicates are silently skipped
- If you need to handle revisions later, you can switch to
  INSERT ... ON CONFLICT ... UPDATE (a future enhancement).

RUNNING THIS:
    python -m app.services.ingest          # one-time run (all history)
    python -m app.services.ingest --days 90  # only last 90 days
"""

import asyncio
import argparse
from datetime import date, timedelta

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.database import async_session, init_db
from app.models.gas_price import GasPrice
from app.services.eia_client import EIAClient, PriceRecord


def record_to_dict(record: PriceRecord) -> dict:
    """Convert a PriceRecord dataclass to a dict matching GasPrice columns."""
    return {
        "date": record.date,
        "area_name": record.area_name,
        "area_type": record.area_type,
        "fuel_type": record.fuel_type,
        "grade": record.grade,
        "price": record.price,
        "eia_series_id": record.eia_series_id,
    }


async def ingest_prices(days_back: int | None = None) -> dict:
    """
    Fetch prices from EIA and store them in the database.

    Args:
        days_back: If set, only fetch data from this many days ago.
                   If None, fetch all available history.

    Returns:
        Summary dict with counts of fetched and inserted records.
    """
    # Calculate date range
    start_date = None
    if days_back:
        start_date = (date.today() - timedelta(days=days_back)).isoformat()

    # Make sure tables exist
    await init_db()

    summary = {
        "records_fetched": 0,
        "rows_inserted": 0,
    }

    async with EIAClient() as client:
        print(f"Fetching gas & diesel prices (start={start_date or 'all'})...")
        records = await client.fetch_prices(start_date=start_date)
        summary["records_fetched"] = len(records)
        print(f"  Got {len(records)} records from EIA")

    # Write to database
    if not records:
        print("No records to insert.")
        return summary

    print(f"Writing {len(records)} records to database...")

    async with async_session() as session:
        rows_data = [record_to_dict(r) for r in records]

        # Process in batches of 500 to avoid overwhelming SQLite
        batch_size = 500
        inserted = 0

        for i in range(0, len(rows_data), batch_size):
            batch = rows_data[i : i + batch_size]

            stmt = sqlite_insert(GasPrice).values(batch)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["date", "area_name", "fuel_type", "grade"]
            )

            result = await session.execute(stmt)
            inserted += result.rowcount
            await session.commit()

        summary["rows_inserted"] = inserted
        print(f"  Inserted {inserted} new rows ({len(records) - inserted} duplicates skipped)")

    return summary


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Ingest EIA gas price data")
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Only fetch data from the last N days (default: all history)",
    )
    args = parser.parse_args()

    from app.config import settings
    settings.validate()

    summary = await ingest_prices(days_back=args.days)
    print("\n--- Ingestion Summary ---")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
