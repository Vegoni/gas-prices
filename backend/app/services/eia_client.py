"""
EIA API v2 client.

This module handles all communication with the U.S. Energy Information
Administration's open data API. It knows how to build the right URLs,
parse the responses, and return clean Python objects.

EIA API v2 PRIMER:
- Base: https://api.eia.gov/v2/
- Auth: api_key query parameter on every request
- Gas + Diesel prices: /petroleum/pri/gnd/ (Weekly Retail Gasoline and Diesel Prices)
  This single endpoint contains BOTH gasoline and diesel data, differentiated by product code.
- Responses are paginated (default 5000 rows, max 5000)
- Data comes back as {"response": {"data": [...]}}

PRODUCT CODES (the ones we care about):
  EPMR     = Regular Gasoline
  EPMM     = Midgrade Gasoline
  EPMP     = Premium Gasoline
  EPM0     = Total Gasoline (all grades combined)
  EPD2DXL0 = No 2 Diesel Ultra Low Sulfur (the standard diesel at pumps)

ARCHITECTURE NOTE:
This is a "service" — it talks to an external system but has no knowledge
of our database. The ingestion script (ingest.py) will call this client,
then write results to the DB. Keeping these separate means you can test
the API client without a database, and swap data sources later.
"""

import httpx
from datetime import date
from dataclasses import dataclass
from app.config import settings


# Map EIA product codes to our human-readable grade names
PRODUCT_TO_GRADE = {
    "EPMR": "regular",
    "EPMM": "midgrade",
    "EPMP": "premium",
    "EPM0": "all",           # all gasoline grades combined
    "EPD2DXL0": "diesel",    # ultra low sulfur diesel (standard pump diesel)
}

# Which product codes are gasoline vs diesel
GASOLINE_PRODUCTS = {"EPMR", "EPMM", "EPMP", "EPM0"}
DIESEL_PRODUCTS = {"EPD2DXL0"}

# All the product codes we want to fetch
ALL_PRODUCTS = list(GASOLINE_PRODUCTS | DIESEL_PRODUCTS)


@dataclass
class PriceRecord:
    """
    A single price observation from the EIA.

    This is a plain data container — no database dependency.
    The ingestion layer converts these into GasPrice model instances.
    """
    date: date
    area_name: str
    area_type: str       # "national", "region", "state"
    fuel_type: str       # "gasoline" or "diesel"
    grade: str           # "regular", "midgrade", "premium", "all", "diesel"
    price: float | None
    eia_series_id: str


class EIAClient:
    """
    Async client for the EIA Open Data API v2.

    Usage:
        async with EIAClient() as client:
            records = await client.fetch_prices(start_date="2024-01-01")
    """

    def __init__(self):
        self.base_url = settings.EIA_BASE_URL
        self.api_key = settings.EIA_API_KEY
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Set up the HTTP client when entering the 'async with' block."""
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args):
        """Clean up the HTTP client when leaving the block."""
        if self._client:
            await self._client.aclose()

    async def _get(self, endpoint: str, params: dict) -> dict:
        """
        Make a GET request to the EIA API.

        Adds the API key automatically. Raises on HTTP errors.
        """
        params["api_key"] = self.api_key

        response = await self._client.get(
            f"{self.base_url}/{endpoint}",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def fetch_prices(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        products: list[str] | None = None,
    ) -> list[PriceRecord]:
        """
        Fetch weekly retail gas and diesel prices from the gnd endpoint.

        The gnd (Gasoline and Diesel) endpoint has everything in one place.
        We filter by product code to get the grades we care about, and
        paginate through results since the API caps at 5000 rows per request.

        Args:
            start_date: "YYYY-MM-DD" — only get data from this date forward.
            end_date:   "YYYY-MM-DD" — only get data up to this date.
            products:   List of EIA product codes to fetch. Defaults to ALL_PRODUCTS.

        Returns:
            List of PriceRecord objects, one per data point.
        """
        if products is None:
            products = ALL_PRODUCTS

        all_records = []
        offset = 0
        page_size = 5000  # EIA max per request

        while True:
            params = {
                "frequency": "weekly",
                "data[0]": "value",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": page_size,
                "offset": offset,
            }

            # Filter to only the products we want (EIA accepts repeated keys via list)
            params["facets[product][]"] = products

            if start_date:
                params["start"] = start_date
            if end_date:
                params["end"] = end_date

            data = await self._get("petroleum/pri/gnd/data/", params)
            rows = data.get("response", {}).get("data", [])
            total = int(data.get("response", {}).get("total", 0))

            records = self._parse_response(rows)
            all_records.extend(records)

            # Check if we need more pages
            offset += page_size
            if offset >= total or len(rows) < page_size:
                break

            print(f"  Fetched {len(all_records)}/{total} records so far...")

        return all_records

    def _parse_response(self, rows: list[dict]) -> list[PriceRecord]:
        """
        Convert raw EIA JSON rows into PriceRecord objects.

        A typical row looks like:
        {
            "period": "2026-04-27",
            "duoarea": "NUS",
            "area-name": "U.S.",
            "product": "EPMR",
            "product-name": "Regular Gasoline",
            "process": "PTE",
            "process-name": "Retail Sales",
            "series": "EMM_EPMR_PTE_NUS_DPG",
            "value": "3.456",
            "units": "$/GAL"
        }
        """
        records = []

        for row in rows:
            product_code = row.get("product", "")

            # Skip products we don't track
            if product_code not in PRODUCT_TO_GRADE:
                continue

            grade = PRODUCT_TO_GRADE[product_code]
            fuel_type = "diesel" if product_code in DIESEL_PRODUCTS else "gasoline"
            area_type = self._classify_area(row.get("duoarea", ""))

            # EIA returns value as a string; convert to float
            try:
                price_val = float(row["value"]) if row.get("value") is not None else None
            except (ValueError, TypeError):
                price_val = None

            records.append(PriceRecord(
                date=date.fromisoformat(row["period"]),
                area_name=row.get("area-name", "Unknown"),
                area_type=area_type,
                fuel_type=fuel_type,
                grade=grade,
                price=price_val,
                eia_series_id=row.get("series", ""),
            ))

        return records

    @staticmethod
    def _classify_area(area_code: str) -> str:
        """
        Determine if an area is national, regional (PADD), or a state.

        EIA uses:
        - "NUS" for national (U.S. average)
        - "R10", "R1X", "R1Y", "R1Z", "R20", etc. for PADD regions/sub-regions
        - "SPA" (Pennsylvania), "SAZ" (Arizona), etc. for states
        """
        if area_code == "NUS":
            return "national"
        elif area_code.startswith("R"):
            return "region"
        else:
            return "state"
