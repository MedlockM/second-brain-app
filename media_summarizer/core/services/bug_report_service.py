"""
Bug Report Service — hexagonal domain service for bug report intake.

Handles persistence (DynamoDB) as the storage adapter.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# Configuration
BUG_REPORTS_TABLE = required_env("BUG_REPORTS_TABLE")


class BugReportStatus(str, Enum):
    """Status of a bug report."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class BugReport(BaseModel):
    """Domain model for a bug report.

    The media block (``media_item_id`` through ``media_type``) is what a report
    filed from the failure screen of one item carries (task-381), and it is
    optional for the same reason ``attachment_key`` is: a report filed from the
    Account tab is about the app, not about a media, and has nothing to put
    there.

    ``error_code`` is captured at submission rather than read back later:
    ``processing_jobs`` carries a TTL, so the job row can be gone by the time the
    owner reads the report. ``source_url`` is resolved server-side from the
    caller's library row and stays ``None`` when that row cannot be read — or
    when it genuinely has no URL, which is the case for every uploaded document.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    subject: str
    description: str
    attachment_key: Optional[str] = None
    status: BugReportStatus = BugReportStatus.OPEN
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_app_version: Optional[str] = None
    source_platform: Optional[str] = None

    # --- The media this report is about, when it is about one (task-381) ------
    media_item_id: Optional[str] = None
    error_code: Optional[str] = None
    source_url: Optional[str] = None
    media_key: Optional[str] = None
    media_type: Optional[str] = None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Serialize to DynamoDB item format."""
        item: Dict[str, Any] = {
            "id": self.id,
            "user_id": self.user_id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
        }
        if self.attachment_key:
            item["attachment_key"] = self.attachment_key
        if self.source_app_version:
            item["source_app_version"] = self.source_app_version
        if self.source_platform:
            item["source_platform"] = self.source_platform
        if self.media_item_id:
            item["media_item_id"] = self.media_item_id
        if self.error_code:
            item["error_code"] = self.error_code
        if self.source_url:
            item["source_url"] = self.source_url
        if self.media_key:
            item["media_key"] = self.media_key
        if self.media_type:
            item["media_type"] = self.media_type
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "BugReport":
        """Deserialize from DynamoDB item."""
        return cls(
            id=item["id"],
            user_id=item["user_id"],
            subject=item["subject"],
            description=item["description"],
            attachment_key=item.get("attachment_key"),
            status=BugReportStatus(item.get("status", "open")),
            created_at=item["created_at"],
            source_app_version=item.get("source_app_version"),
            source_platform=item.get("source_platform"),
            media_item_id=item.get("media_item_id"),
            error_code=item.get("error_code"),
            source_url=item.get("source_url"),
            media_key=item.get("media_key"),
            media_type=item.get("media_type"),
        )


class BugReportService:
    """
    Service layer for bug report operations.
    Adapter: DynamoDB persistence.
    """

    async def create_report(
        self,
        user_id: str,
        subject: str,
        description: str,
        attachment_key: Optional[str] = None,
        source_app_version: Optional[str] = None,
        source_platform: Optional[str] = None,
        media_item_id: Optional[str] = None,
        error_code: Optional[str] = None,
        source_url: Optional[str] = None,
        media_key: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> BugReport:
        """Create and persist a new bug report."""
        report = BugReport(
            user_id=user_id,
            subject=subject,
            description=description,
            attachment_key=attachment_key,
            source_app_version=source_app_version,
            source_platform=source_platform,
            media_item_id=media_item_id,
            error_code=error_code,
            source_url=source_url,
            media_key=media_key,
            media_type=media_type,
        )

        await self._persist(report)
        log_event(
            logger,
            logging.INFO,
            "bug_report.created",
            f"Bug report created: id={report.id}",
            report_id=report.id,
            user_id=user_id,
            source_platform=report.source_platform,
            source_app_version=report.source_app_version,
            media_item_id=report.media_item_id,
            error_code=report.error_code,
        )
        return report

    async def _persist(self, report: BugReport) -> None:
        """Persist a bug report to DynamoDB."""
        from media_summarizer.utils.database_async import _dynamodb_client_kwargs, get_session

        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(BUG_REPORTS_TABLE)
            await table.put_item(Item=report.to_dynamodb_item())
