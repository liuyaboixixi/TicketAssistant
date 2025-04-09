import functools
import uuid
from time import time
from typing import Dict, Any, Generator, List, TypedDict, Literal
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

    @staticmethod
    def agent_node(state, agent, name):
        """
        调用指定的代理，并处理其返回的消息。
        """
        result = agent.invoke(state)
        if isinstance(result, ToolMessage):
            pass
        else:
            result = AIMessage(**result.model_dump(exclude={"type", "name"}), name=name)
        return {
            "messages": [result],
            "sender": name,
        }

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
        analysis_node = functools.partial(self.agent_node, agent=analysis_agent, name="analysis_agent")
        resolution_node = functools.partial(self.agent_node, agent=resolution_agent, name="resolution_agent")
        # 创建工作流图
        workflow = StateGraph(state_schema=WorkflowState)

        # 添加节点
        workflow.add_node("analysis_agent", analysis_node)
        workflow.add_node("resolution_agent", resolution_node)
        workflow.add_node("call_tool", self._tool_node_with_context)

        # 添加边
        workflow.add_conditional_edges(
            "analysis_agent",
            self._router, {"call_tool": "call_tool", "resolution_agent": "resolution_agent", "__end__": END}
        )
        workflow.add_conditional_edges(
            "resolution_agent",
            self._router, {"call_tool": "call_tool", "resolution_agent": "resolution_agent", "__end__": END}
        )
        workflow.add_conditional_edges(
            "call_tool",
            lambda x: x["sender"], {"analysis_agent": "analysis_agent", "resolution_agent": "resolution_agent"}
        )
        workflow.add_edge(START, "analysis_agent")

        return workflow.compile()

    def _tool_node_with_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            logger.debug(f"工具节点状态键值: {list(state.keys())}")

            # 为工具添加上下文
            for tool in self.tools:
                setattr(tool, '_calling_context', state)

            # 获取最后一条消息
            messages = state.get("messages", [])
            if not messages:
                logger.warning("状态中未找到消息")
                return state

            last_message = messages[-1]

            # 检查是否有工具调用
            if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                logger.warning("最后一条消息中未找到工具调用")
                return state

            # 执行工具调用
            tool_calls = last_message.tool_calls
            tool_results = []

            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})

                # 查找对应的工具
                tool = next((t for t in self.tools if t.name == tool_name), None)
                if not tool:
                    logger.warning(f"未找到工具: {tool_name}")
                    continue

                # 调用工具
                try:
                    result = tool.invoke(tool_args)
                    tool_results.append({
                        "name": tool_name,
                        "content": result
                    })
                except Exception as e:
                    logger.error(f"工具 {tool_name} 调用失败: {str(e)}")
                    tool_results.append({
                        "name": tool_name,
                        "content": f"错误: {str(e)}"
                    })

            # 更新状态
            state["tool_results"] = tool_results
            return state

        except Exception as e:
            logger.error(f"工具节点执行错误: {str(e)}")
            return state

    def _router(self, state: Dict[str, Any]) -> Literal["call_tool", "resolution_agent", "__end__"]:
        """路由决策"""
        # 添加迭代计数
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        messages = state["messages"]
        last_message = messages[-1]

        # 检查终止条件
        if state["iteration_count"] > 10:
            logger.warning(f"【终止】工作流超过最大迭代次数: {state['iteration_count']}")
            return "__end__"
        
        if len(messages) > 15:
            logger.warning(f"【终止】工作流超过最大消息数: {len(messages)}")
            return "__end__"
        
        if any("FINAL ANSWER" in str(getattr(m, 'content', '')) for m in messages):
            logger.info("【完成】工作流获得最终答案，正常结束")
            return "__end__"

        # 处理用户信息
        if isinstance(last_message, ToolMessage) and last_message.name == "query_user_info":
            try:
                user_id_match = re.search(r'\(\s*(\d+)\s*,', last_message.content)
                if user_id_match:
                    if "context" not in state:
                        state["context"] = {}
                    state["context"]["user_id"] = user_id_match.group(1)
                    logger.debug(f"【用户】成功提取用户ID: {state['context']['user_id']}")
            except Exception as e:
                logger.error(f"【错误】提取用户ID失败: {str(e)}")

        # 路由决策
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.debug(f"【路由】发现工具调用，转向工具节点: {last_message.tool_calls}")
            return "call_tool"
        
        if hasattr(last_message, 'content') and "FINAL ANSWER" in last_message.content:
            logger.debug("【路由】发现最终答案标记，工作流结束")
            return "__end__"

        logger.debug(f"【路由】转向解决方案代理，消息类型: {type(last_message).__name__}")
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
            logger.info(f"【开始】处理工单 {request_id}")
            logger.debug(f"【工单】内容: {ticket.format_ticket_content()}")

            # 运行工作流
            events = []
            logger.debug("【工作流】开始执行")
            for event in self.graph.stream({
                "messages": [
                    HumanMessage(content=ticket.format_ticket_content())
                ],
                "context": {
                    "request_id": request_id
                }
            }, {"recursion_limit": 20}):
                logger.debug(f"【事件】{event.get('sender', 'unknown')} - {type(event).__name__}")
                events.append(event)

            # 提取结果
            logger.debug(f"【处理】共 {len(events)} 个事件")
            analysis = ""
            solution = ""
            messages = []

            for event in events:
                if isinstance(event.get("messages", [None])[0], AIMessage):
                    msg_content = event["messages"][0].content
                    if "FINAL ANSWER" in msg_content:
                        logger.debug("【结果】找到最终答案")
                        solution = msg_content.replace("FINAL ANSWER", "").strip()
                    elif event.get("sender") == "analysis_agent":
                        logger.debug("【结果】找到分析内容")
                        analysis = msg_content
                    messages.append({
                        "role": event["sender"],
                        "content": msg_content
                    })

            processing_time = time() - start_time
            logger.debug(f"【完成】处理耗时: {processing_time:.2f}秒")

            # 构建响应
            response = TicketResponse(
                request_id=request_id,
                status="success",
                messages=messages,
                analysis=analysis,
                solution=solution,
                processing_time=processing_time
            )

            logger.info(f"【完成】工单 {request_id} 处理完成，耗时: {processing_time:.2f}秒")
            return response

        except Exception as e:
            log_exception(logger, e, f"【错误】处理工单 {request_id} 失败")
            raise
