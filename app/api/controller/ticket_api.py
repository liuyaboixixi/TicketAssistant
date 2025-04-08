from fastapi import APIRouter, HTTPException

from typing import Optional
from datetime import datetime

from app.core.logging import logger, log_exception
from app.models.ticket_dto import TicketResponse, TicketRequest
from app.services.ticket_workflow import TicketWorkflowService

router = APIRouter()
workflow_service = TicketWorkflowService()

@router.post("/process", response_model=TicketResponse)
async def process_ticket(ticket: TicketRequest):
    """
    处理工单请求
    
    Args:
        ticket: 工单请求信息
    
    Returns:
        TicketResponse: 工单处理结果
    """
    try:
        logger.info("Received ticket request")
        logger.debug(f"Ticket content: {ticket.format_ticket_content()}")
        response = await workflow_service.process_ticket(ticket)
        return response
        
    except Exception as e:
        log_exception(logger, e, "Error processing ticket")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }