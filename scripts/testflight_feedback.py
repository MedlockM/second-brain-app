#!/usr/bin/env python3
"""Collect TestFlight beta feedback from App Store Connect, assets included.

The MCP server ``asc-testflight`` covers interactive questions ("show me this
week's crashes"). This script covers the three things it cannot do, all of which
the daily triage run depends on:

**Windowing.** App Store Connect has no date filter on the feedback collections
— ``filter[createdDate]`` answers 400 ``'createdDate' is not a valid filter
type``. The only accepted sort is ``-createdDate``, so bounding a window means
paginating from the newest and stopping client-side.

**Assets before they expire.** ``screenshots[].url`` is a presigned URL with an
``expirationDate`` roughly six days out, so a URL stored anywhere is a URL that
will 403 by the time anyone follows it. The bytes have to be pulled at collection
time. Same story for a crash: ``logText`` is reachable through a *second* call
because ``include=crashLog`` answers 400 (only ``build`` and ``tester`` are
includable), and Apple's 120-day retention drops the text before the submission
stops being listable.

**Build provenance.** A feedback filed against build 4 while build 6 is live may
already be fixed, and nothing in the submission says so — the build number comes
from the ``build`` relationship and the marketing version from that build's
``preReleaseVersion``.

Deliberately absent: **any grouping**. Two testers describing one bug in
different words, and two lexically similar reports about different screens, are
both indistinguishable to string matching and obvious to a reader. This script
emits raw comments and lets the triage agent judge; no similarity scoring, no
keyword bucketing, no "same screen" guessing.

The emitted fields are a whitelist, not a filtered dump: the repository is
public, and a tester's identity must not survive into a report or a commit. The
``tester`` relationship is never requested, so the payload has no name or email
to leak in the first place.

Credentials come from the environment, or failing that from the
``asc-testflight`` MCP registration in ``~/.claude.json`` — one source of truth,
so nothing about the key is duplicated on disk.

Usage:
    python3 scripts/testflight_feedback.py [--since-hours N] [--out DIR]
                                           [--skip-ids-file FILE] [--indent N]
    python3 scripts/testflight_feedback.py --check-credentials
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt

API_ROOT = "https://api.appstoreconnect.apple.com"
REPO_ROOT = Path(__file__).resolve().parent.parent
EAS_JSON = REPO_ROOT / "mobile" / "eas.json"
DEFAULT_OUT = REPO_ROOT / ".testflight-feedback"

# Apple rejects a token minted for more than 20 minutes. Fifteen leaves room for
# a slow run without ever approaching the ceiling.
TOKEN_TTL_SECONDS = 15 * 60

# The documented maximum. Anything larger answers 400.
PAGE_LIMIT = 200

# This key is shared with EAS Submit and RevenueCat, and the rate limit is
# per-key. A run costs a few dozen calls, so the guard exists to catch a genuine
# loop, not to ration normal use.
MAX_REQUESTS = 400


class AscError(RuntimeError):
    """An App Store Connect call failed in a way retrying will not fix."""


def _load_credentials() -> tuple[str, str, Path]:
    """Return ``(key_id, issuer_id, private_key_path)``.

    The environment wins so a one-off run can point at another key. Otherwise
    the values come from the MCP server registration, which is where they were
    entered once and where they stay.
    """
    key_id = os.environ.get("ASC_KEY_ID")
    issuer_id = os.environ.get("ASC_ISSUER_ID")
    key_path = os.environ.get("ASC_PRIVATE_KEY_PATH")

    if not (key_id and issuer_id and key_path):
        config = Path.home() / ".claude.json"
        try:
            servers = json.loads(config.read_text())["mcpServers"]["asc-testflight"]["env"]
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise AscError(
                "No App Store Connect credentials. Set ASC_KEY_ID, ASC_ISSUER_ID and "
                "ASC_PRIVATE_KEY_PATH, or register the asc-testflight MCP server "
                f"(see mobile/MOBILE_CI_CD.md). Reading {config} failed: {exc}"
            ) from exc
        key_id = key_id or servers.get("ASC_KEY_ID")
        issuer_id = issuer_id or servers.get("ASC_ISSUER_ID")
        key_path = key_path or servers.get("ASC_PRIVATE_KEY_PATH")

    if not (key_id and issuer_id and key_path):
        raise AscError("App Store Connect credentials are incomplete.")

    resolved = Path(os.path.expanduser(key_path))
    if not resolved.is_file():
        raise AscError(f"Private key not found at {resolved}.")
    return key_id, issuer_id, resolved


def _mint_token(key_id: str, issuer_id: str, key_path: Path) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": issuer_id,
            "iat": now,
            "exp": now + TOKEN_TTL_SECONDS,
            "aud": "appstoreconnect-v1",
        },
        key_path.read_text(),
        algorithm="ES256",
        headers={"kid": key_id, "typ": "JWT"},
    )


def _app_id() -> str:
    """Read ``ascAppId`` from ``mobile/eas.json`` rather than hardcoding it."""
    submit = json.loads(EAS_JSON.read_text())["submit"]
    for profile in ("internal", "production", "production-store"):
        app_id = submit.get(profile, {}).get("ios", {}).get("ascAppId")
        if app_id:
            return str(app_id)
    raise AscError(f"No ios.ascAppId in any submit profile of {EAS_JSON}.")


class Client:
    def __init__(self, token: str) -> None:
        self._token = token
        self.requests = 0
        self.rate_limit = ""

    def get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not url.startswith("http"):
            url = f"{API_ROOT}{url}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        self.requests += 1
        if self.requests > MAX_REQUESTS:
            raise AscError(
                f"Aborted after {MAX_REQUESTS} requests — this looks like a loop, and "
                "the key is shared with EAS Submit and RevenueCat."
            )

        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                self.rate_limit = response.headers.get("X-Rate-Limit", "") or self.rate_limit
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:500]
            if exc.code == 429:
                raise AscError(
                    f"Rate limited by App Store Connect ({self.rate_limit}). This key is "
                    "shared with EAS Submit and RevenueCat — do not retry in a loop."
                ) from exc
            raise AscError(f"GET {url} -> {exc.code}: {body}") from exc

    def paginate(self, path: str, params: dict[str, Any], cutoff: datetime) -> list[dict[str, Any]]:
        """Walk ``-createdDate`` pages until a row predates ``cutoff``.

        Apple offers no server-side date filter, so the stop is ours to make.
        ``included`` is merged across pages because the ``build`` of a row on
        page 2 is described on page 2.
        """
        rows: list[dict[str, Any]] = []
        included: dict[str, dict[str, Any]] = {}
        url: str | None = path
        query: dict[str, Any] | None = params

        while url:
            payload = self.get(url, query)
            query = None  # links.next carries the query already
            for item in payload.get("included", []):
                included[f"{item['type']}:{item['id']}"] = item

            reached_cutoff = False
            for row in payload.get("data", []):
                created = _parse_date(row.get("attributes", {}).get("createdDate"))
                if created and created < cutoff:
                    reached_cutoff = True
                    break
                rows.append(row)
            if reached_cutoff:
                break
            url = payload.get("links", {}).get("next")

        for row in rows:
            row["_included"] = included
        return rows


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _resolve_build(client: Client, row: dict[str, Any]) -> dict[str, Any]:
    """Return the build number and marketing version a feedback was filed on."""
    reference = row.get("relationships", {}).get("build", {}).get("data") or {}
    build_id = reference.get("id")
    if not build_id:
        return {"id": None, "version": None, "pre_release_version": None}

    included = row.get("_included", {})
    build = included.get(f"builds:{build_id}")
    if build is None:
        build = client.get(f"/v1/builds/{build_id}").get("data", {})

    version = (build.get("attributes") or {}).get("version")
    pre_release = None
    try:
        payload = client.get(f"/v1/builds/{build_id}/preReleaseVersion")
        pre_release = (payload.get("data") or {}).get("attributes", {}).get("version")
    except AscError:
        pass  # A build whose pre-release version has been reaped is still usable.
    return {"id": build_id, "version": version, "pre_release_version": pre_release}


def _latest_build(client: Client, app_id: str) -> dict[str, Any]:
    """The newest build, so a report can say how stale a feedback's build is.

    Through ``/v1/builds`` with ``filter[app]``, not ``/v1/apps/{id}/builds``,
    which answers 400 on both ``sort`` and ``include``. And sorted on
    ``-uploadedDate`` rather than ``-version``: build numbers are strings to
    Apple, so ``-version`` would rank build 9 above build 10.
    """
    payload = client.get(
        "/v1/builds",
        {
            "filter[app]": app_id,
            "sort": "-uploadedDate",
            "limit": 1,
            "include": "preReleaseVersion",
        },
    )
    rows = payload.get("data") or []
    if not rows:
        return {"version": None, "pre_release_version": None, "uploaded_date": None}
    attributes = rows[0].get("attributes", {})
    pre_release = next(
        (
            item["attributes"]["version"]
            for item in payload.get("included", [])
            if item["type"] == "preReleaseVersions"
        ),
        None,
    )
    return {
        "version": attributes.get("version"),
        "pre_release_version": pre_release,
        "uploaded_date": attributes.get("uploadedDate"),
        "processing_state": attributes.get("processingState"),
    }


def _download(url: str, destination: Path) -> bool:
    """Fetch a presigned asset. No Authorization header — it is pre-signed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            destination.write_bytes(response.read())
        return True
    except (urllib.error.URLError, OSError) as exc:
        print(f"  ! asset non téléchargé ({destination.name}): {exc}", file=sys.stderr)
        return False


def _collect_kind(
    client: Client,
    app_id: str,
    kind: str,
    cutoff: datetime,
    out_dir: Path,
    skip_ids: set[str],
) -> list[dict[str, Any]]:
    collection = (
        "betaFeedbackCrashSubmissions" if kind == "crash" else "betaFeedbackScreenshotSubmissions"
    )
    rows = client.paginate(
        f"/v1/apps/{app_id}/{collection}",
        {"sort": "-createdDate", "limit": PAGE_LIMIT, "include": "build"},
        cutoff,
    )

    feedbacks = []
    for row in rows:
        attributes = row.get("attributes", {})
        feedback_id = row["id"]
        skipped = feedback_id in skip_ids
        assets: list[str] = []
        crash_log: str | None = None

        if not skipped:
            target = out_dir / feedback_id
            if kind == "screenshot":
                for index, shot in enumerate(attributes.get("screenshots") or [], start=1):
                    url = shot.get("url")
                    if not url:
                        continue
                    suffix = Path(urllib.parse.urlparse(url).path).suffix or ".png"
                    path = target / f"shot-{index}{suffix}"
                    if _download(url, path):
                        assets.append(str(path))
            else:
                # include=crashLog answers 400, so the text needs its own call.
                try:
                    payload = client.get(f"/v1/{collection}/{feedback_id}/crashLog")
                    text = ((payload.get("data") or {}).get("attributes") or {}).get("logText")
                    if text:
                        path = target / "crash.log"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(text)
                        crash_log = str(path)
                except AscError as exc:
                    # Expected on older submissions: Apple reaps logText before
                    # the submission itself stops being listable.
                    print(f"  ! crash log indisponible pour {feedback_id}: {exc}", file=sys.stderr)

        # Whitelist, not a filtered dump: nothing that could carry an identity
        # is ever placed in the payload.
        feedbacks.append(
            {
                "id": feedback_id,
                "kind": kind,
                "created_date": attributes.get("createdDate"),
                "comment": attributes.get("comment"),
                "device_model": attributes.get("deviceModel"),
                "os_version": attributes.get("osVersion"),
                "locale": attributes.get("locale"),
                "device_platform": attributes.get("devicePlatform"),
                "app_platform": attributes.get("appPlatform"),
                "app_uptime_millis": attributes.get("appUpTimeInMilliseconds"),
                "battery_percentage": attributes.get("batteryPercentage"),
                "screen_width": attributes.get("screenWidthInPoints"),
                "screen_height": attributes.get("screenHeightInPoints"),
                "build": _resolve_build(client, row),
                "assets": assets,
                "crash_log": crash_log,
                "assets_skipped": skipped,
            }
        )
    return feedbacks


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect TestFlight beta feedback and its assets from App Store Connect."
    )
    parser.add_argument(
        "--since-hours",
        type=int,
        default=168,
        help=(
            "How far back to look. Only bounds API cost: deduplication is keyed on "
            "feedback ids, not on time, so a wide window is safe (default: 168)."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Where assets are written; gitignored (default: {DEFAULT_OUT}).",
    )
    parser.add_argument(
        "--skip-ids-file",
        type=Path,
        help=(
            "File of already-decided feedback ids, one per line. Those rows are still "
            "reported but their assets are not re-downloaded."
        ),
    )
    parser.add_argument("--indent", type=int, default=2, help="JSON indent (default: 2).")
    parser.add_argument(
        "--check-credentials",
        action="store_true",
        help=(
            "Resolve the key, mint a token and exit. Costs zero API calls, so the timer's "
            "wrapper can fail fast instead of spending an agent run to discover a missing key."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.check_credentials:
        try:
            key_id, issuer_id, key_path = _load_credentials()
            _mint_token(key_id, issuer_id, key_path)
            app_id = _app_id()
        except (AscError, OSError, ValueError, KeyError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        # The key id identifies which key, not how to use it, and the app id is
        # already in the tracked mobile/eas.json — neither is a secret. The
        # issuer id stays unprinted: it is half of an auth pair.
        print(f"App Store Connect: clé {key_id} lisible, token signé, app {app_id}.")
        return 0

    skip_ids: set[str] = set()
    if args.skip_ids_file and args.skip_ids_file.is_file():
        skip_ids = {
            line.strip()
            for line in args.skip_ids_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

    try:
        key_id, issuer_id, key_path = _load_credentials()
        client = Client(_mint_token(key_id, issuer_id, key_path))
        app_id = _app_id()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)

        latest = _latest_build(client, app_id)
        feedbacks = _collect_kind(client, app_id, "crash", cutoff, args.out, skip_ids)
        feedbacks += _collect_kind(client, app_id, "screenshot", cutoff, args.out, skip_ids)
    except AscError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for feedback in feedbacks:
        feedback["build_is_latest"] = bool(
            latest.get("version") and feedback["build"].get("version") == latest["version"]
        )
    feedbacks.sort(key=lambda item: item.get("created_date") or "", reverse=True)

    json.dump(
        {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "app_id": app_id,
            "window_hours": args.since_hours,
            "latest_build": latest,
            "asset_dir": str(args.out),
            "feedback_count": len(feedbacks),
            "feedbacks": feedbacks,
        },
        sys.stdout,
        indent=args.indent,
        ensure_ascii=False,
    )
    print()
    print(
        f"  {len(feedbacks)} feedback(s), {client.requests} requête(s) — {client.rate_limit}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
