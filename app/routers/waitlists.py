from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account
from app.models import Account
from app.schemas import WaitlistCreateRequest, WaitlistResponse
from app.services import create_waitlist

router = APIRouter(prefix="/waitlists", tags=["waitlists"])


@router.post("", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
def create(
    payload: WaitlistCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> WaitlistResponse:
    return create_waitlist(
        db,
        current_account,
        payload.flight_no,
        payload.flight_date,
        payload.start_segment_id,
        payload.end_segment_id,
        payload.cabin_class,
    )
