from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account
from app.models import Account
from app.schemas import (
    LoginRequest,
    MeResponse,
    MeSensitiveResponse,
    TokenResponse,
)
from app.security import create_access_token, decrypt_sensitive_value, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    account = db.scalar(
        select(Account).where(Account.login_identifier == payload.login_identifier),
    )
    if account is None or not verify_password(payload.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if account.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Account is disabled.")
    token = create_access_token(
        account_id=account.account_id,
        login_identifier=account.login_identifier,
        role=account.role,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(
    current_account: Annotated[Account, Depends(get_current_account)],
) -> MeResponse:
    passenger = current_account.passenger
    return MeResponse(
        login_identifier=current_account.login_identifier,
        role=current_account.role,
        passenger_id=passenger.passenger_id if passenger else None,
        passenger_id_card_masked=passenger.id_card_masked if passenger else None,
        passenger_name_masked=passenger.name_masked if passenger else None,
        user_type=passenger.user_type.type_name if passenger and passenger.user_type else None,
        mileage_points=float(passenger.mileage_points) if passenger else None,
    )


@router.get("/me/sensitive", response_model=MeSensitiveResponse)
def me_sensitive(
    current_account: Annotated[Account, Depends(get_current_account)],
) -> MeSensitiveResponse:
    passenger = current_account.passenger
    if passenger is None:
        raise HTTPException(
            status_code=403,
            detail="Only passenger accounts can view full sensitive profile fields.",
        )

    return MeSensitiveResponse(
        passenger_name_full=decrypt_sensitive_value(passenger.name_encrypted),
        passenger_id_card_full=decrypt_sensitive_value(passenger.id_card_encrypted),
    )
