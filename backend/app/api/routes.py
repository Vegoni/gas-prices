"""
API routes for the gas price dashboard.

These endpoints serve data to the React frontend. They're intentionally
simple for the MVP — just reading from the database with some filters.

All routes are async and use dependency injection for the DB session,
which is FastAPI's recommended pattern.
"""

from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_session
from app.models.gas_price import GasPrice

router = APIRouter()


@router.get("/health")
async def health_check():
    """Simple health check — useful for monitoring later."""
    return {"status": "ok"}


@router.get("/prices")
async def get_prices(
    fuel_type: str = Query(default="gasoline", description="gasoline or diesel"),
    grade: str = Query(default="regular", description="regular, midgrade, premium, all, diesel"),
    area_name: str | None = Query(default=None, description="Filter by area name"),
    area_type: str | None = Query(default=None, description="national, region, or state"),
    days: int = Query(default=365, description="How many days of history to return"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get price data with filters.

    This is the main endpoint the frontend will call. It returns an array
    of price records sorted by date, filtered by fuel type, grade, and area.

    Example:
        GET /api/prices?fuel_type=gasoline&grade=regular&area_name=Pennsylvania&days=90
    """
    start_date = date.today() - timedelta(days=days)

    query = (
        select(GasPrice)
        .where(GasPrice.fuel_type == fuel_type)
        .where(GasPrice.grade == grade)
        .where(GasPrice.date >= start_date)
        .order_by(GasPrice.date.asc())
    )

    if area_name:
        query = query.where(GasPrice.area_name == area_name)
    if area_type:
        query = query.where(GasPrice.area_type == area_type)

    result = await session.execute(query)
    rows = result.scalars().all()

    return [
        {
            "date": row.date.isoformat(),
            "area_name": row.area_name,
            "area_type": row.area_type,
            "fuel_type": row.fuel_type,
            "grade": row.grade,
            "price": row.price,
        }
        for row in rows
    ]


@router.get("/prices/compare")
async def compare_areas(
    areas: str = Query(description="Comma-separated area names, e.g. 'Pennsylvania,Arizona'"),
    fuel_type: str = Query(default="gasoline"),
    grade: str = Query(default="regular"),
    days: int = Query(default=365),
    session: AsyncSession = Depends(get_session),
):
    """
    Compare prices across multiple areas.

    Returns data structured for easy charting — one series per area.

    Example:
        GET /api/prices/compare?areas=Pennsylvania,Arizona&grade=regular&days=180
    """
    area_list = [a.strip() for a in areas.split(",")]
    start_date = date.today() - timedelta(days=days)

    query = (
        select(GasPrice)
        .where(GasPrice.fuel_type == fuel_type)
        .where(GasPrice.grade == grade)
        .where(GasPrice.area_name.in_(area_list))
        .where(GasPrice.date >= start_date)
        .order_by(GasPrice.date.asc())
    )

    result = await session.execute(query)
    rows = result.scalars().all()

    # Group by area for the frontend
    grouped: dict[str, list] = {area: [] for area in area_list}
    for row in rows:
        if row.area_name in grouped:
            grouped[row.area_name].append({
                "date": row.date.isoformat(),
                "price": row.price,
            })

    return grouped


@router.get("/areas")
async def list_areas(
    area_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """List all available area names, optionally filtered by type."""
    query = select(distinct(GasPrice.area_name))
    if area_type:
        query = query.where(GasPrice.area_type == area_type)
    query = query.order_by(GasPrice.area_name)

    result = await session.execute(query)
    areas = [row[0] for row in result.all()]
    return areas
