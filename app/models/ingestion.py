from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, desc
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class IngestionRun(Base, TimestampMixin):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_source_id_started_at_desc", "source_id", desc("started_at")),
        Index("ix_ingestion_runs_status_started_at_desc", "status", desc("started_at")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="started")
    error_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    notes: Mapped[dict] = mapped_column(JSON, default=dict)

    # Relationships
    source = relationship("Source", back_populates="ingestion_runs")

    def __repr__(self) -> str:
        return f"<IngestionRun(id={self.id}, source_id={self.source_id}, status='{self.status}')>"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate duration in seconds if run is completed."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_running(self) -> bool:
        """Check if the ingestion run is currently running."""
        return self.status in ("started", "running")

    @property
    def is_completed(self) -> bool:
        """Check if the ingestion run completed successfully."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if the ingestion run failed."""
        return self.status == "failed"
