from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_limit: Mapped[int] = mapped_column(Integer, default=60)
    config: Mapped[dict] = mapped_column(JSON, default={})
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    items = relationship("ContentItem", back_populates="source")
    ingestion_runs = relationship("IngestionRun", back_populates="source")
