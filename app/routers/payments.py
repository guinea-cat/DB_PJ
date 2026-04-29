from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_account
from app.models import Account
from app.schemas import PaymentConfirmRequest, PaymentResponse
from app.services import confirm_payment

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/{payment_id}/confirm", response_model=PaymentResponse)
def confirm(
    payment_id: str,
    payload: PaymentConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    current_account: Annotated[Account, Depends(get_current_account)],
) -> PaymentResponse:
    payment = confirm_payment(
        db,
        current_account,
        payment_id,
        payload.payment_method,
        payload.payer_account,
    )
    return PaymentResponse(
        payment_id=payment.payment_id,
        ticket_no=payment.ticket_no,
        payment_method=payment.payment_method,
        payment_status=payment.payment_status,
        pay_amount=float(payment.pay_amount),
        mock_trade_no=payment.mock_trade_no,
        payer_account_masked=payment.payer_account_masked,
        created_at=payment.created_at,
        paid_at=payment.paid_at,
        refunded_at=payment.refunded_at,
    )
