# tools.py
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, StructuredTool
from typing import Annotated, List
import re
from app.core.logging import logger
from app.tools.ActivityTool.activity_tool import analyze_ticket_subject
from app.tools.MjLogs.mj_log_query_tool import query_logs_and_get_results, query_system_logs
from app.tools.PointsDetails.query_points_details import query_points_details
from app.tools.sql_db_query_tool import SQLQueryTool


class Tools:
    """工具集合类，用于管理和组织所有可用的工具"""

    @staticmethod
    @tool
    def query_ones_rag(ticket_id: Annotated[str, "工单ID"]) -> str:
        """获取ONES工单背景信息。"""
        try:
            logger.info(f"开始查询工单背景信息，工单ID：{ticket_id}")
            return f"该工具无法使用，请使用其他工具。"
            # return f"工单 {ticket_id} 的背景信息已获取。"
        except Exception as e:
            logger.error(f"工单背景信息查询失败：{str(e)}")
            return f"工单背景信息查询失败：{str(e)}"

    @staticmethod
    @tool
    def query_system_logs(params: Annotated[str, "查询系统日志的参数"]) -> str:
        """从明觉日志系统中查询相关信息的日志，整合已知用户数据优化查询精确度。"""
        try:
            logger.info(f"开始查询系统日志，参数：{params}")
            
            # 优化查询参数
            enhanced_params = params
            user_id = None
            
            # 从上下文获取用户ID（如果可用）
            try:
                calling_context = getattr(query_system_logs, '_calling_context', None)
                if calling_context and 'messages' in calling_context:
                    for msg in calling_context['messages']:
                        if isinstance(msg, ToolMessage) and msg.name == 'query_user_info':
                            id_match = re.search(r'\(\s*(\d+)\s*,', msg.content)
                            if id_match:
                                user_id = id_match.group(1)
                                logger.info(f"从上下文提取到用户ID: {user_id}")
                                break
            except Exception as e:
                logger.warning(f"从上下文提取用户ID失败：{str(e)}")

            if user_id:
                enhanced_params = f"用户ID:{user_id} {params}"
                logger.info(f"增强日志查询参数: {enhanced_params}")

            # 执行查询
            query_logs = query_logs_and_get_results(enhanced_params)
            return query_logs
        except Exception as e:
            logger.error(f"系统日志查询失败：{str(e)}")
            return f"系统日志查询失败：{str(e)}"

    @staticmethod
    @tool
    def query_user_info(user_query: Annotated[str, "用户信息查询条件"]) -> str:
        """从mysql数据库中，查询用户的详细信息。"""
        try:
            logger.info(f"开始查询用户信息，查询条件：{user_query}")
            sql_tool = SQLQueryTool()
            result = sql_tool.generate_sql_query(user_query)
            
            logger.debug(f"SQL查询：{result['sql_query']}")
            logger.debug(f"查询结果：{result['query_result']}")
            
            if result["query_result"]:
                return f"用户 {result['query_result']} 的详细信息已成功查询。"
            else:
                return "未找到匹配的用户信息，请使用其他工具进行查询。"
        except Exception as e:
            logger.error(f"用户信息查询失败：{str(e)}")
            return f"用户信息查询失败：{str(e)}"

    @staticmethod
    @tool
    def query_ticket_background(ticket_id: Annotated[str, "工单ID"]) -> str:
        """从ones平台，获取工单的背景信息。"""
        try:
            logger.info(f"抱歉，当前该工具不支持工单查询，请使用其他工具")
            return f"抱歉，当前该工具不支持工单查询，请使用其他工具。"
        except Exception as e:
            logger.error(f"工单背景信息查询失败：{str(e)}")
            return f"工单背景信息查询失败：{str(e)}"

    @classmethod
    def get_all_tools(cls) -> List[StructuredTool]:
        """返回所有工具的列表"""
        return [
            # cls.query_mj_logs,
            # cls.query_sso_db_info,
            cls.query_ones_rag,
            cls.query_system_logs,
            cls.query_user_info,
            cls.query_ticket_background,
            query_points_details,
            analyze_ticket_subject
        ]
