import uuid
from time import time
from typing import Dict, Any, Generator, List, TypedDict
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END, START

from app.core.config import settings
from app.core.logging import logger, log_exception
from app.models.ticket_dto import TicketRequest, TicketResponse
from app.tools.tools import Tools


class WorkflowState(TypedDict):
    """工作流状态类型定义"""
    messages: List[BaseMessage]
    context: Dict[str, Any]
    sender: str


class TicketWorkflowService:
    """工单处理工作流服务"""

    def __init__(self):
        """初始化服务"""
        self.llm = ChatOpenAI(
            model=settings.MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            temperature=0,
            streaming=True
        )
        self.tools = Tools.get_all_tools()
        self.graph = self.create_ticket_workflow()

    def _create_agent(self, system_message: str):
        """创建代理"""
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一个AI助手，与其他助手合作分析工单内容，调用工具获取信息，解决工单问题。"
                "如果你不能完全回答，另一个拥有不同工具的助手会继续帮助。"
                "如果你或其他助手有最终答案或交付物，在你的回答前加上FINAL ANSWER，以便团队知道停止。"
                "你可以使用以下工具: {tool_names}。\n{system_message}"
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        prompt = prompt.partial(
            system_message=system_message,
            tool_names=", ".join([tool.name for tool in self.tools])
        )
        return prompt | self.llm.bind_tools(self.tools)

    def create_ticket_workflow(self) -> StateGraph:
        """创建工作流图"""
        # 创建分析和解决方案代理
        analysis_agent = self._create_agent(
            "分析工单内容，确定问题所属系统和类型，并调用相应工具获取信息。"
        )
        resolution_agent = self._create_agent(
            "结合工单问题和工具返回的信息，分析问题原因并提供解决方案。"
        )

        # 创建工作流图
        workflow = StateGraph(state_schema=WorkflowState)

        # 添加节点
        workflow.add_node("analysis_agent", analysis_agent)
        workflow.add_node("resolution_agent", resolution_agent)
        workflow.add_node("call_tool", self._tool_node_with_context)

        # 添加边
        workflow.add_conditional_edges(
            "analysis_agent",
            self._router,
            {
                "call_tool": "call_tool",
                "resolution_agent": "resolution_agent",
                "__end__": END
            }
        )
        workflow.add_conditional_edges(
            "resolution_agent",
            self._router,
            {
                "call_tool": "call_tool",
                "resolution_agent": "resolution_agent",
                "__end__": END
            }
        )
        workflow.add_conditional_edges(
            "call_tool",
            lambda x: x["sender"],
            {
                "analysis_agent": "analysis_agent",
                "resolution_agent": "resolution_agent"
            }
        )
        workflow.add_edge(START, "analysis_agent")

        return workflow.compile()

    def _tool_node_with_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            logger.debug(f"Tool node state keys: {list(state.keys())}")

            # 为工具添加上下文
            for tool in self.tools:
                setattr(tool, '_calling_context', state)

            # 获取最后一条消息
            messages = state.get("messages", [])
            if not messages:
                logger.warning("No messages found in state")
                return state
                
            last_message = messages[-1]
            
            # 检查是否有工具调用
            if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                logger.warning("No tool calls found in last message")
                return state
                
            # 执行工具调用
            tool_calls = last_message.tool_calls
            tool_results = []
            
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("arguments", {})
                
                # 查找对应的工具
                tool = next((t for t in self.tools if t.name == tool_name), None)
                if not tool:
                    logger.warning(f"Tool {tool_name} not found")
                    continue
                    
                # 调用工具
                try:
                    result = tool.invoke(tool_args)
                    tool_results.append({
                        "name": tool_name,
                        "content": result
                    })
                except Exception as e:
                    logger.error(f"Error invoking tool {tool_name}: {str(e)}")
                    tool_results.append({
                        "name": tool_name,
                        "content": f"Error: {str(e)}"
                    })
            
            # 更新状态
            state["tool_results"] = tool_results
            return state
            
        except Exception as e:
            logger.error(f"Tool node error: {str(e)}")
            return state

    def _router(self, state: Dict[str, Any]) -> str:
        """路由决策"""
        messages = state["messages"]
        last_message = messages[-1]

        # 处理用户信息查询结果
        if isinstance(last_message, ToolMessage) and last_message.name == "query_user_info":
            try:
                user_id_match = re.search(r'\(\s*(\d+)\s*,', last_message.content)
                if user_id_match:
                    if "context" not in state:
                        state["context"] = {}
                    state["context"]["user_id"] = user_id_match.group(1)
                    logger.debug(f"Extracted user ID: {state['context']['user_id']}")
            except Exception as e:
                logger.error(f"Failed to extract user ID: {str(e)}")

        # 处理次数保护
        if len(messages) > 10:
            logger.warning("Maximum message limit reached")
            return "__end__"

        # 路由决策
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.debug(f"Found tool calls in message: {last_message.tool_calls}")
            return "call_tool"
        if hasattr(last_message, 'content') and "FINAL ANSWER" in last_message.content:
            logger.debug("Found FINAL ANSWER in message")
            return "__end__"
            
        logger.debug(f"Routing to resolution_agent, message type: {type(last_message).__name__}")
        return "resolution_agent"

    async def process_ticket(self, ticket: TicketRequest) -> TicketResponse:
        """
        处理工单请求

        Args:
            ticket: TicketRequest对象，包含工单信息

        Returns:
            TicketResponse对象，包含处理结果
        """
        request_id = str(uuid.uuid4())
        start_time = time()

        try:
            logger.info(f"Processing ticket {request_id}")
            logger.debug(f"Ticket content: {ticket.format_ticket_content()}")

            # 运行工作流
            events = []
            logger.debug("Starting workflow execution")
            for event in self.graph.stream({
                "messages": [
                    HumanMessage(content=ticket.format_ticket_content())
                ],
                "context": {
                    "request_id": request_id
                }
            }):
                logger.debug(f"Workflow event: {event.get('sender', 'unknown')} - {type(event).__name__}")
                events.append(event)

            # 提取结果
            logger.debug(f"Processing {len(events)} events")
            analysis = ""
            solution = ""
            messages = []

            for event in events:
                if isinstance(event.get("messages", [None])[0], AIMessage):
                    msg_content = event["messages"][0].content
                    if "FINAL ANSWER" in msg_content:
                        logger.debug("Found final answer")
                        solution = msg_content.replace("FINAL ANSWER", "").strip()
                    elif event.get("sender") == "analysis_agent":
                        logger.debug("Found analysis")
                        analysis = msg_content
                    messages.append({
                        "role": event["sender"],
                        "content": msg_content
                    })

            processing_time = time() - start_time
            logger.debug(f"Processing completed in {processing_time:.2f}s")

            # 构建响应
            response = TicketResponse(
                request_id=request_id,
                status="success",
                messages=messages,
                analysis=analysis,
                solution=solution,
                processing_time=processing_time
            )

            logger.info(f"Completed ticket {request_id} in {processing_time:.2f}s")
            return response

        except Exception as e:
            log_exception(logger, e, f"Error processing ticket {request_id}")
            raise
