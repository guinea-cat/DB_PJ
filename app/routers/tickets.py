from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account
from app.models import Account, TicketSale
from app.schemas import PurchaseTicketRequest, TicketResponse
from app.services import cancel_pending_ticket, purchase_ticket, refund_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/purchase", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def purchase(
    payload: PurchaseTicketRequest,
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> TicketResponse:
    return purchase_ticket(
        db,
        current_account,
        payload.flight_no,
        payload.flight_date,
        payload.start_segment_id,
        payload.end_segment_id,
        payload.cabin_class,
    )


@router.post("/{ticket_no}/refund", response_model=TicketResponse)
def refund(
    ticket_no: str,
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> TicketResponse:
    ticket = db.get(TicketSale, ticket_no)
    if ticket is None or ticket.passenger_id != current_account.passenger_id:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    ticket = refund_ticket(db, ticket, current_account)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_no}/cancel", response_model=TicketResponse)
def cancel(
    ticket_no: str,
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> TicketResponse:
    ticket = db.get(TicketSale, ticket_no)
    if ticket is None or ticket.passenger_id != current_account.passenger_id:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    ticket = cancel_pending_ticket(db, ticket, current_account)
    db.commit()
    db.refresh(ticket)
    return ticket
