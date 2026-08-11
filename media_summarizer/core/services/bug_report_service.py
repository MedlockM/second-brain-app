"""
Bug Report Service — hexagonal domain service for bug report intake.

Handles persistence (DynamoDB) and routing (Discord webhook) as separate
adapters behind the service interface.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel, Field

from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

# Configuration
BUG_REPORTS_TABLE = required_env("BUG_REPORTS_TABLE")
BUG_REPORT_ROUTING_WEBHOOK = os.environ.get("BUG_REPORT_ROUTING_WEBHOOK", "")


class BugReportStatus(str, Enum):
    """Status of a bug report."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class BugReport(BaseModel):
    """Domain model for a bug report."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    subject: str
    description: str
    attachment_key: Optional[str] = None
    status: BugReportStatus = BugReportStatus.OPEN
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_app_version: Optional[str] = None
    source_platform: Optional[str] = None

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
        )


class BugReportService:
    """
    Service layer for bug report operations.
    Adapters: DynamoDB persistence, Discord webhook routing.
    """

    async def create_report(
        self,
        user_id: str,
        subject: str,
        description: str,
        attachment_key: Optional[str] = None,
        source_app_version: Optional[str] = None,
        source_platform: Optional[str] = None,
    ) -> BugReport:
        """Create and persist a new bug report."""
        report = BugReport(
            user_id=user_id,
            subject=subject,
            description=description,
            attachment_key=attachment_key,
            source_app_version=source_app_version,
            source_platform=source_platform,
        )

        await self._persist(report)
        logger.info(f"Bug report created: id={report.id}, user={user_id}")
        return report

    async def _persist(self, report: BugReport) -> None:
        """Persist a bug report to DynamoDB."""
        from media_summarizer.utils.database_async import _dynamodb_client_kwargs, get_session

        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(BUG_REPORTS_TABLE)
            await table.put_item(Item=report.to_dynamodb_item())

    async def route_to_triage(self, report: BugReport) -> None:
        """Route the report to the configured triage channel (Discord webhook V1)."""
        webhook_url = BUG_REPORT_ROUTING_WEBHOOK
        if not webhook_url:
            logger.debug("No BUG_REPORT_ROUTING_WEBHOOK configured, skipping routing.")
            return

        # Build Discord embed
        embed = {
            "title": f"Bug Report: {report.subject}",
            "description": report.description[:2000],  # Discord embed limit
            "color": 0xFFCB05,  # Amber primary
            "fields": [
                {"name": "Report ID", "value": report.id, "inline": True},
                {"name": "Platform", "value": report.source_platform or "unknown", "inline": True},
                {"name": "App Version", "value": report.source_app_version or "unknown", "inline": True},
            ],
            "timestamp": report.created_at,
        }

        if report.attachment_key:
            embed["fields"].append(
                {"name": "Attachment", "value": f"`{report.attachment_key}`", "inline": False}
            )

        payload = {
            "embeds": [embed],
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code not in (200, 204):
                logger.warning(
                    f"Discord webhook returned {response.status_code}: {response.text[:200]}"
                )
            else:
                logger.info(f"Bug report {report.id} routed to Discord successfully.")
