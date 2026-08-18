"""
Account endpoint: in-app deletion of the caller's own account.

There is no ``user_id`` in the path, by design. The account deleted is the one the
bearer token authenticates, so an authorization check is not something the handler
can forget: the route this replaces (``DELETE /api/users/{user_id}``) took an
id and compared it to the session, which is a check that has to be written
correctly every time instead of being structurally impossible to get wrong.

Reading and updating the current account stays on ``/api/auth/me``.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services.account_deletion_service import purge_account
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

router = APIRouter()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current_user: AuthUser = Depends(get_current_user),
) -> None:
    """Erase the authenticated account and everything it owns.

    Irreversible, and required in-app by App Store guideline 5.1.1(v). Returns 204
    once every store has been purged; on failure it returns 500 and the account is
    left usable so the client can retry, because the purge is idempotent and the
    identity rows are the last thing it removes.
    """
    try:
        report = await purge_account(current_user.id)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "account_deletion.failed",
            "Account deletion failed; account left intact for retry",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            detail=str(exc)[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account deletion failed. Please try again.",
        ) from exc

    log_event(
        logger,
        logging.INFO,
        "account_deletion.completed",
        "Account deleted by user request",
        user_id=current_user.id,
        records_removed=report.total(),
    )
