"""Request schemas for Analytics endpoints."""

from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExecutionAnalyticsQuery(BaseModel):
    """Query parameters for execution analytics endpoint."""

    # Filters
    test_case_id: UUID | None = Field(
        default=None,
        description="Optional test case UUID to filter by. If omitted, aggregates all test cases in architecture."
    )
    
    date_from: datetime | None = Field(
        default=None,
        description="Start date (ISO8601). Defaults to 7 days ago."
    )
    
    date_to: datetime | None = Field(
        default=None,
        description="End date (ISO8601). Defaults to now."
    )
    
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of items in rankings (1-50)."
    )
    
    include: list[str] = Field(
        default_factory=lambda: ["summary", "rankings", "trend"],
        description="List of blocks to include: 'summary', 'rankings', 'trend'. "
                    "Example: ['summary', 'trend'] to get only summary and trend (no rankings)."
    )

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        """Allow string datetime parsing."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Try ISO format
            return datetime.fromisoformat(v)
        raise ValueError(f"Invalid datetime: {v}")

    @field_validator("date_to")
    @classmethod
    def validate_date_range(cls, v, info):
        """Ensure date_to >= date_from and max range is 90 days."""
        if v is None or "date_from" not in info.data:
            return v
        
        date_from = info.data.get("date_from")
        if date_from is None:
            return v
        
        if v < date_from:
            raise ValueError("date_to must be >= date_from")
        
        # Max 90 days
        max_range = timedelta(days=90)
        if v - date_from > max_range:
            raise ValueError("Date range cannot exceed 90 days")
        
        return v

    @field_validator("include", mode="before")
    @classmethod
    def parse_include(cls, v):
        """Parse comma-separated include list or accept list directly."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Support both comma-separated and bracket notation
            items = [item.strip() for item in v.split(",") if item.strip()]
            return items if items else ["summary", "rankings", "trend"]
        if v is None:
            return ["summary", "rankings", "trend"]
        raise ValueError("include must be a list or comma-separated string")

    @field_validator("include")
    @classmethod
    def validate_include_values(cls, v):
        """Ensure all include values are valid."""
        valid = {"summary", "rankings", "trend"}
        invalid = set(v) - valid
        if invalid:
            raise ValueError(f"Invalid include blocks: {invalid}. Valid: {valid}")
        return v
