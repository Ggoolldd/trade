"""Authenticated read-only job status with stable keyset order and bound filters."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, tuple_

from app.auth import AuthService, Identity
from app.auth_api import service
from app.authorization import Permission, require_permission
from app.domain_types import UtcTimestamp
from app.errors import ErrorResponse
from app.models.jobs import Job, JobKind, JobStatus
from app.pagination import JobCursor, Page, PageQuery

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["jobs"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: JobKind
    status: JobStatus
    queue_name: str
    attempts: int
    max_attempts: int
    correlation_id: UUID
    created_at: UtcTimestamp
    next_attempt_at: UtcTimestamp


class JobListQuery(PageQuery):
    status: JobStatus | None = None
    queue_name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9:-]{0,99}$")


@router.get("", response_model=Page[JobView])
def list_jobs(
    identity: Annotated[Identity, Depends(require_permission(Permission.STATUS_READ))],
    auth: Annotated[AuthService, Depends(service)],
    params: Annotated[JobListQuery, Query()],
) -> Page[JobView]:
    limit, cursor, status, queue_name = (
        params.limit,
        params.cursor,
        params.status,
        params.queue_name,
    )
    position = None
    if cursor:
        try:
            position = JobCursor.decode(cursor)
            if (position.status, position.queue_name) != (status, queue_name):
                raise ValueError("cursor filters do not match")
        except ValueError:
            raise HTTPException(422, detail="Invalid cursor") from None
    query = select(Job)
    if status is not None:
        query = query.where(Job.status == status)
    if queue_name is not None:
        query = query.where(Job.queue_name == queue_name)
    if position is not None:
        query = query.where(tuple_(Job.created_at, Job.id) > (position.created_at, position.id))
    with auth.database.transaction() as session:
        rows = list(session.scalars(query.order_by(Job.created_at, Job.id).limit(limit + 1)))
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more:
        last = visible[-1]
        next_cursor = JobCursor(
            created_at=last.created_at, id=last.id, status=status, queue_name=queue_name
        ).encode()
    return Page(
        items=[JobView.model_validate(row) for row in visible],
        limit=limit,
        next_cursor=next_cursor,
        has_more=has_more,
    )
