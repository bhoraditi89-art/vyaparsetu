from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class TransactionType(str, Enum):
    CREDIT = "CREDIT"
    PAYMENT = "PAYMENT"
    CASH_SALE = "CASH_SALE"

class VoiceTransactionIntent(BaseModel):
    customer_name: str = Field(..., description="Name of the customer")
    customer_phone: Optional[str] = Field(None, description="Phone number if mentioned")
    amount: float = Field(..., gt=0, description="Amount in INR")
    item_description: Optional[str] = Field(None, description="Product or service")
    transaction_type: TransactionType = Field(default=TransactionType.CREDIT)
    detected_language: Optional[str] = Field("hi-IN", description="Language code")

class LedgerResponse(BaseModel):
    status: str
    intent: VoiceTransactionIntent
    message: str