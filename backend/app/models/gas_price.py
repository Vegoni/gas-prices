"""
SQLAlchemy model for gas/diesel price data.

DESIGN DECISIONS:
- One table for all fuel types (regular, midgrade, premium, diesel).
  Why? The EIA data has the same shape regardless of fuel type, and
  a single table makes comparison queries much simpler.

- area_name stores both state names ("Pennsylvania") and region names
  ("East Coast (PADD 1)"). The area_type column ("state", "region",
  "national") lets you filter.

- price is stored as Float, not Integer-cents. EIA reports prices as
  dollars with 3 decimal places (e.g., 3.456). Float is fine here —
  we're reading/displaying, not doing financial math.

- Composite unique constraint on (date, area_name, fuel_type, grade)
  prevents duplicate rows if ingestion runs twice for the same period.
"""

from datetime import date
from sqlalchemy import Column, Integer, Float, String, Date, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class GasPrice(Base):
    __tablename__ = "gas_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # When: the week this price represents
    date = Column(Date, nullable=False)

    # Where: geographic area
    area_name = Column(String, nullable=False)       # e.g., "Pennsylvania", "U.S.", "East Coast (PADD 1)"
    area_type = Column(String, nullable=False)        # "national", "region", "state"

    # What: fuel classification
    fuel_type = Column(String, nullable=False)        # "gasoline" or "diesel"
    grade = Column(String, nullable=False)            # "regular", "midgrade", "premium", "all", "diesel"

    # The actual data point
    price = Column(Float, nullable=True)              # $/gallon — nullable because EIA sometimes has gaps

    # Where did this come from (for debugging/auditing)
    eia_series_id = Column(String, nullable=True)     # e.g., "EMM_EPMR_PTE_SPA_DPG"

    # Prevent duplicate rows for the same date/area/fuel combo
    __table_args__ = (
        UniqueConstraint("date", "area_name", "fuel_type", "grade", name="uq_price_record"),
        # Speed up the most common queries
        Index("ix_date", "date"),
        Index("ix_area_fuel", "area_name", "fuel_type"),
        Index("ix_area_type", "area_type"),
    )

    def __repr__(self):
        return (
            f"<GasPrice {self.date} | {self.area_name} | "
            f"{self.fuel_type}/{self.grade} | ${self.price}>"
        )
