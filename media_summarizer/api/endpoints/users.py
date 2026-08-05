"""
User account endpoints.

Only account deletion lives here. Reading and updating the current account is
served by ``/api/v1/auth/me`` and account creation by ``/api/v1/auth/register``;
the legacy unauthenticated CRUD routes that duplicated them have been removed
(task-222).

Note: this route closes the public surface only. It deletes the user row and
nothing else — the full GDPR-grade cascade (artifacts, S3 objects, Algolia
records, folders, tags, jobs, subscriptions) is owned by task-224.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.utils import database_async
from media_summarizer.utils.database_async import get_db

router = APIRouter()


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: AuthUser = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Delete the authenticated caller's own account.

    Requires authentication. A caller may only delete their own account: any
    other ``user_id`` yields 404, the same status as a genuinely unknown
    account, so account existence is never leaked.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await database_async.delete_user(current_user.id)
