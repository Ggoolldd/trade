"""Local authentication routes; no public registration or default owner password."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.auth import AuthenticationDenied, AuthService, Identity
from app.domain_types import UtcTimestamp
from app.errors import ErrorResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"], responses={401: {"model": ErrorResponse}})
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,64}$")
    password: SecretStr = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: UtcTimestamp


class UserResponse(BaseModel):
    id: UUID
    username: str


def service(request: Request) -> AuthService:
    return AuthService(request.app.state.database)


def rejection(error: AuthenticationDenied) -> HTTPException:
    headers = {"Retry-After": "900"} if error.status_code == 429 else {"WWW-Authenticate": "Bearer"}
    return HTTPException(error.status_code, detail="Authentication rejected", headers=headers)


def current_identity(
    auth: Annotated[AuthService, Depends(service)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Identity:
    if credentials is None:
        raise rejection(AuthenticationDenied())
    try:
        return auth.identify(SecretStr(credentials.credentials))
    except AuthenticationDenied as error:
        raise rejection(error) from None


@router.post("/login", response_model=TokenResponse, responses={429: {"model": ErrorResponse}})
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    auth: Annotated[AuthService, Depends(service)],
) -> TokenResponse:
    try:
        token = auth.login(
            username=payload.username,
            password=payload.password,
            source=request.client.host if request.client else "unknown",
            correlation_id=request.state.request_id,
        )
    except AuthenticationDenied as error:
        raise rejection(error) from None
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=token.access_token.get_secret_value(), expires_at=token.expires_at
    )


@router.get("/me", response_model=UserResponse)
def me(identity: Annotated[Identity, Depends(current_identity)]) -> UserResponse:
    return UserResponse(id=identity.user_id, username=identity.username)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    identity: Annotated[Identity, Depends(current_identity)],
    auth: Annotated[AuthService, Depends(service)],
) -> Response:
    try:
        auth.logout(identity, request.state.request_id)
    except AuthenticationDenied as error:
        raise rejection(error) from None
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
