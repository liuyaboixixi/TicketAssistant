from pydantic import BaseModel, Field, validator
from typing import Dict, Any, List, Optional
from datetime import datetime

class TicketRequest(BaseModel):
    """工单请求模型"""
    description: Optional[str] = Field(default="", description="工单内容描述")
    user_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="用户信息")
    
    @validator('description')
    def validate_description(cls, v):
        """验证工单描述不为空"""
        if v is None:
            return ""
        return v.strip()

    def format_ticket_content(self) -> str:
        """格式化工单内容"""
        content = f"""工单内容：
{self.description if self.description else "无描述"}"""
            
        if self.user_info:
            content += f"\n\n用户信息：\n{self.user_info}"
            
        return content

class TicketResponse(BaseModel):
    """工单响应模型"""
    request_id: str = Field(..., description="请求ID")
    status: str = Field(default="success", description="处理状态")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="处理过程消息")
    analysis: str = Field(default="", description="分析结果")
    solution: str = Field(default="", description="解决方案")
    processing_time: float = Field(..., description="处理耗时(秒)")
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow(), description="创建时间")
    
    @validator('status')
    def validate_status(cls, v):
        """验证状态值"""
        allowed_status = ["success", "error", "processing"]
        if v not in allowed_status:
            raise ValueError(f"状态值必须是以下之一: {', '.join(allowed_status)}")
        return v