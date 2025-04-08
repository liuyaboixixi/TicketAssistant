import logging
from datetime import datetime
import sys
import os
import traceback

def setup_logger():
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    logger = logging.getLogger("ticket_assistant")
    logger.setLevel(logging.DEBUG)  # 设置为DEBUG级别

    # 创建更详细的日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)  # 控制台只显示INFO及以上级别
    logger.addHandler(console_handler)

    # 文件处理器 - 所有日志
    file_handler = logging.FileHandler(
        f"logs/ticket_assistant_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有DEBUG及以上级别
    logger.addHandler(file_handler)

    # 错误日志专用处理器
    error_handler = logging.FileHandler(
        f"logs/ticket_assistant_errors_{datetime.now().strftime('%Y%m%d')}.log"
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)  # 只记录ERROR及以上级别
    logger.addHandler(error_handler)

    return logger

def log_exception(logger, e, message="发生异常"):
    """详细记录异常信息，包括堆栈跟踪"""
    error_message = f"{message}: {str(e)}"
    stack_trace = traceback.format_exc()
    logger.error(f"{error_message}\n堆栈跟踪:\n{stack_trace}")

logger = setup_logger()