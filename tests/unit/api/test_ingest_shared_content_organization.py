"""Integration tests for POST /api/media/ingest-shared-content folder_id + tag_ids support.

These tests verify that:
- AC#5: folder_id and tag_ids Form fields are accepted with the same validation as /ingest-url
- AC#6: folder_id and tag_ids are passed through to the domain command (and thus the ProcessingJob)
- AC#7: absent folder_id defaults to None (use-case default behavior)
- AC#8: text and audio submissions with folder_id + tag_ids create jobs with those values
- AC#9: validation errors (folder not found, tag not owned, > MAX_TAGS) return HTTP 400
- AC#11: submissions without folder/tags continue to work (no regression)
"""

from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from media_summarizer.core.constants import MAX_TAGS_PER_MEDIA

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_user():
    """A mock user object simulating a DB user row."""
    user = MagicMock()
    user.id = "user-123"
    user.email = "test@example.com"
    return user


@pytest.fixture()
def mock_folder():
    """A mock folder belonging to the test user."""
    folder = MagicMock()
    folder.id = "folder-abc"
    folder.user_id = "user-123"
    return folder


@pytest.fixture()
def mock_tags():
    """Mock user tags."""
    tag1 = MagicMock()
    tag1.id = "tag-1"
    tag2 = MagicMock()
    tag2.id = "tag-2"
    tag3 = MagicMock()
    tag3.id = "tag-3"
    return [tag1, tag2, tag3]


@pytest.fixture()
def auth_user():
    """Auth user injected via Depends(get_current_user)."""
    from media_summarizer.core.models.auth import AuthUser

    return AuthUser(id="user-123", email="test@example.com")


@pytest.fixture()
def mock_outcome():
    """A successful ingestion outcome from the use case."""
    from media_summarizer.core.media_ingestion.domain import (
        IngestionOutcome,
        ProcessingLifecycleStatus,
    )

    return IngestionOutcome(
        media_item_id="job-xyz",
        job_id="job-xyz",
        status=ProcessingLifecycleStatus.COMPLETED,
        media_key="mk-123",
        normalized_url="share://whatsapp/text/abc123",
        deduplicated=False,
    )


@pytest.fixture()
def client(auth_user, mock_user, mock_folder, mock_tags, mock_outcome):
    """Create a test client with all dependencies mocked."""
    with patch(
        "media_summarizer.api.endpoints.media.get_current_user",
        return_value=auth_user,
    ), patch(
        "media_summarizer.api.endpoints.media.database_async"
    ) as mock_db, patch(
        "media_summarizer.api.endpoints.media.s3"
    ) as mock_s3, patch(
        "media_summarizer.api.endpoints.media.sqs"
    ) as mock_sqs, patch(
        "media_summarizer.api.endpoints.media.bind_log_context",
        return_value="token",
    ), patch(
        "media_summarizer.api.endpoints.media.reset_log_context"
    ), patch(
        "media_summarizer.api.endpoints.media.log_event"
    ):
        # Configure mock DB
        mock_db.get_user_by_id = AsyncMock(return_value=mock_user)
        mock_db.get_folder_by_id = AsyncMock(return_value=mock_folder)
        mock_db.get_tags_by_user_id = AsyncMock(return_value=mock_tags)

        # Configure mock S3
        mock_s3.upload_file_object = AsyncMock()

        # Mock the use case
        with patch(
            "media_summarizer.core.media_ingestion.wiring.build_default_ingest_shared_content_use_case"
        ) as mock_build_uc:
            mock_uc = AsyncMock()
            mock_uc.execute = AsyncMock(return_value=mock_outcome)
            mock_build_uc.return_value = mock_uc

            from media_summarizer.api.main import create_app

            try:
                app = create_app()
            except Exception:
                # If create_app doesn't exist, build from the router directly
                from fastapi import FastAPI

                from media_summarizer.api.endpoints.media import router

                app = FastAPI()
                app.include_router(router, prefix="/api/media")

                # Override auth dependency
                from media_summarizer.api.dependencies.auth import get_current_user

                app.dependency_overrides[get_current_user] = lambda: auth_user

            yield TestClient(app), mock_db, mock_uc


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _text_form_data(
    folder_id: Optional[str] = None,
    tag_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build multipart form fields for a text share."""
    data: Dict[str, Any] = {
        "share_type": "text",
        "source_platform": "whatsapp",
        "source_app": "android-share-intent",
        "text": "Hello, this is a shared text message for testing.",
    }
    if folder_id is not None:
        data["folder_id"] = folder_id
    if tag_ids is not None:
        data["tag_ids"] = json.dumps(tag_ids)
    return data


def _audio_form_data(
    folder_id: Optional[str] = None,
    tag_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build multipart form fields for an audio share."""
    data: Dict[str, Any] = {
        "share_type": "audio",
        "source_platform": "whatsapp",
        "source_app": "android-share-intent",
        "content_mime_type": "audio/ogg",
        "original_name": "voice-message.ogg",
    }
    if folder_id is not None:
        data["folder_id"] = folder_id
    if tag_ids is not None:
        data["tag_ids"] = json.dumps(tag_ids)
    return data


# ---------------------------------------------------------------------------
# Tests: AC#8 - Text with folder_id + tag_ids
# ---------------------------------------------------------------------------


class TestIngestSharedTextWithOrganization:
    """Verify that text shares accept and propagate folder_id + tag_ids."""

    def test_text_with_folder_and_tags_returns_202(self, client):
        test_client, mock_db, mock_uc = client
        data = _text_form_data(folder_id="folder-abc", tag_ids=["tag-1", "tag-2"])
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["media_item_id"] == "job-xyz"

    def test_text_with_folder_and_tags_passes_to_use_case(self, client):
        test_client, mock_db, mock_uc = client
        data = _text_form_data(folder_id="folder-abc", tag_ids=["tag-1", "tag-2"])
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 202

        # Verify the use case was called with the correct folder_id and tag_ids
        mock_uc.execute.assert_called_once()
        command = mock_uc.execute.call_args[0][0]
        assert command.request.folder_id == "folder-abc"
        assert command.request.tag_ids == ["tag-1", "tag-2"]

    def test_text_without_folder_or_tags_returns_202(self, client):
        """AC#11: No regression - text without folder/tags still works."""
        test_client, mock_db, mock_uc = client
        data = _text_form_data()
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 202
        command = mock_uc.execute.call_args[0][0]
        assert command.request.folder_id is None
        assert command.request.tag_ids is None


# ---------------------------------------------------------------------------
# Tests: AC#8 - Audio with folder_id + tag_ids
# ---------------------------------------------------------------------------


class TestIngestSharedAudioWithOrganization:
    """Verify that audio shares accept and propagate folder_id + tag_ids."""

    def test_audio_with_folder_and_tags_returns_202(self, client):
        test_client, mock_db, mock_uc = client
        data = _audio_form_data(folder_id="folder-abc", tag_ids=["tag-1", "tag-3"])
        # Create a minimal audio file
        audio_content = b"\x00" * 1024  # 1KB dummy audio
        files = {"audio_file": ("voice.ogg", io.BytesIO(audio_content), "audio/ogg")}
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
            files=files,
        )
        assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["media_item_id"] == "job-xyz"

    def test_audio_with_folder_and_tags_passes_to_use_case(self, client):
        test_client, mock_db, mock_uc = client
        data = _audio_form_data(folder_id="folder-abc", tag_ids=["tag-2"])
        audio_content = b"\x00" * 1024
        files = {"audio_file": ("voice.ogg", io.BytesIO(audio_content), "audio/ogg")}
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
            files=files,
        )
        assert resp.status_code == 202

        command = mock_uc.execute.call_args[0][0]
        assert command.request.folder_id == "folder-abc"
        assert command.request.tag_ids == ["tag-2"]

    def test_audio_without_folder_or_tags_returns_202(self, client):
        """AC#11: No regression - audio without folder/tags still works."""
        test_client, mock_db, mock_uc = client
        data = _audio_form_data()
        audio_content = b"\x00" * 1024
        files = {"audio_file": ("voice.ogg", io.BytesIO(audio_content), "audio/ogg")}
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
            files=files,
        )
        assert resp.status_code == 202
        command = mock_uc.execute.call_args[0][0]
        assert command.request.folder_id is None
        assert command.request.tag_ids is None


# ---------------------------------------------------------------------------
# Tests: AC#9 - Validation errors
# ---------------------------------------------------------------------------


class TestIngestSharedContentValidationErrors:
    """Verify validation errors match /ingest-url behavior."""

    def test_folder_not_found_returns_400(self, client):
        test_client, mock_db, mock_uc = client
        # Make get_folder_by_id return None (folder doesn't exist)
        mock_db.get_folder_by_id = AsyncMock(return_value=None)
        data = _text_form_data(folder_id="nonexistent-folder")
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 400
        assert "Folder not found" in resp.json()["detail"]

    def test_folder_owned_by_another_user_returns_400(self, client):
        test_client, mock_db, mock_uc = client
        # Folder exists but belongs to a different user
        other_folder = MagicMock()
        other_folder.id = "folder-other"
        other_folder.user_id = "user-999"
        mock_db.get_folder_by_id = AsyncMock(return_value=other_folder)
        data = _text_form_data(folder_id="folder-other")
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 400
        assert "Folder not found" in resp.json()["detail"]

    def test_tag_not_owned_returns_400(self, client):
        test_client, mock_db, mock_uc = client
        data = _text_form_data(tag_ids=["tag-1", "tag-unknown"])
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 400
        assert "Tag(s) not found" in resp.json()["detail"]
        assert "tag-unknown" in resp.json()["detail"]

    def test_too_many_tags_returns_400(self, client):
        test_client, mock_db, mock_uc = client
        # Create more tags than MAX_TAGS_PER_MEDIA
        too_many_tags = [f"tag-{i}" for i in range(MAX_TAGS_PER_MEDIA + 1)]
        data = _text_form_data(tag_ids=too_many_tags)
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 400
        assert f"Cannot assign more than {MAX_TAGS_PER_MEDIA} tags" in resp.json()["detail"]

    def test_invalid_tag_ids_json_returns_400(self, client):
        test_client, mock_db, mock_uc = client
        data = _text_form_data()
        data["tag_ids"] = "not-valid-json"
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 400
        assert "tag_ids must be a valid JSON array" in resp.json()["detail"]

    def test_tag_ids_not_array_returns_400(self, client):
        test_client, mock_db, mock_uc = client
        data = _text_form_data()
        data["tag_ids"] = json.dumps("single-string")
        resp = test_client.post(
            "/api/media/ingest-shared-content",
            data=data,
        )
        assert resp.status_code == 400
        assert "tag_ids must be a JSON array" in resp.json()["detail"]
