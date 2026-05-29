from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ReconciliationSummary(BaseModel):
    app_source: str = Field(..., description="The booking source (MumbaiOne, MetroConnect3, ONDC)")
    total_records: int = Field(..., description="Total records analyzed")
    settled: int = Field(..., description="Present in all 3 systems")
    liable_for_refund: int = Field(..., description="Liable for refund")
    failed_transaction: int = Field(..., description="Failed transaction")
    refunded: int = Field(..., description="Refunded transactions")
    discrepancy: int = Field(..., description="Unclassified discrepancies")
    revenue: float = Field(0.0, description="Total Mobile Revenue")
    settled_revenue: float = Field(0.0, description="Total Settled Revenue")
    afc_revenue: float = Field(0.0, description="Total AFC Revenue")
    refund_amount: float = Field(0.0, description="Total Refunded Amount")

class ReconciliationRunResponse(BaseModel):
    success: bool
    message: str
    summaries: List[ReconciliationSummary]

class ReconciliationRecordSchema(BaseModel):
    id: int
    app_source: str
    order_id: Optional[str]
    ticket_no: Optional[str]
    pg_ref_no: Optional[str]
    amount: Optional[float]
    transaction_time: Optional[str]
    recon_status: str
    notes: Optional[str]
    data_sources: Optional[str]
    reconciled_at: datetime

    class Config:
        from_attributes = True

class PaginatedReconciliationResults(BaseModel):
    total: int
    page: int
    limit: int
    results: List[ReconciliationRecordSchema]

class DatabaseTableMetrics(BaseModel):
    table_name: str
    row_count: int

class DatabaseStatusSchema(BaseModel):
    connected: bool
    message: str
    metrics: List[DatabaseTableMetrics]

class RevertRequestSchema(BaseModel):
    log_id: int

