import requests
import json
from datetime import datetime

def call_ticket_assistant(ticket_data: dict):
    """
    调用工单助手API的示例
    """
    url = "http://localhost:8000/api/v1/tickets/process"
    
    # 添加当前时间和用户信息
    ticket_data.update({
        "created_by": "liuyaboixixi",
        "created_at": datetime.utcnow().isoformat()
    })
    
    # 发送请求
    response = requests.post(
        url,
        json=ticket_data,
        headers={"Content-Type": "application/json"}
    )
    
    # 处理响应
    if response.status_code == 200:
        result = response.json()
        print("工单处理成功：")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 输出处理时间
        process_time = float(response.headers.get("X-Process-Time", 0))
        print(f"\n处理耗时: {process_time:.2f}秒")
    else:
        print(f"错误: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    # 示例工单数据
    ticket_data = {
        "channel": "信用卡APP",
        "card_status": "正常",
        "steps": "点击超值优惠券等",
        "error_message": "手机号校验有误，请重新输入您的信用卡预留手机号",
        "operation_time": "2025.1.3日18.00分左右",
        "description": "客户致电反馈登录信用卡APP点击超值优惠券等提示上述的报错",
        "user_info": {
            "gender": "男",
            "phone": "13518845492"
        }
    }
    
    call_ticket_assistant(ticket_data)