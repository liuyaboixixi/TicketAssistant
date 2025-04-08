import os
import re
import json
import requests
from typing import Annotated, List, Dict, Any, Optional, Tuple

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
def extract_user_identifiers(text: str) -> Dict[str, str]:
    """
    从文本中提取用户标识符，并按类型分类
    返回格式: {"user_id": "xxx", "id_number": "xxx", "phone": "xxx"}
    """
    identifiers = {}
    
    # 提取用户ID (通常是数字，可能前缀为"用户id:"等)
    user_id_patterns = [
        r'用户[iI][dD][：:]\s*(\d+)',
        r'用户标识符[：:]\s*(\d+)',
        r'[uU]ser[_\s]*[iI][dD][：:]\s*(\d+)',
        r'用户\s*(?:编号|号码)?[：:]\s*(\d+)'
    ]
    
    for pattern in user_id_patterns:
        match = re.search(pattern, text)
        if match:
            identifiers["user_id"] = match.group(1).strip()
            break
    
    # 提取证件号 (通常是18位)
    id_patterns = [
        r'证件号[码]?[：:]\s*([0-9X]{18})',
        r'身份证[：:]\s*([0-9X]{18})',
        r'[iI][dD][：:]\s*([0-9X]{18})'
    ]
    
    for pattern in id_patterns:
        match = re.search(pattern, text)
        if match:
            identifiers["id_number"] = match.group(1).strip()
            break
    
    # 提取手机号 (11位数字，通常以1开头)
    phone_patterns = [
        r'手机号[码]?[：:]\s*(1[3-9]\d{9})',
        r'电话[：:]\s*(1[3-9]\d{9})',
        r'联系方式[：:]\s*(1[3-9]\d{9})'
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            identifiers["phone"] = match.group(1).strip()
            break
    
    # 如果上面的模式都没有匹配到，尝试更宽松的模式
    if not identifiers:
        # 尝试找任何看起来像用户ID的长数字 (至少10位)
        general_id_match = re.search(r'\b(\d{10,})\b', text)
        if general_id_match:
            identifiers["user_id"] = general_id_match.group(1)
        
        # 尝试找任何看起来像手机号的11位数字
        general_phone_match = re.search(r'\b(1[3-9]\d{9})\b', text)
        if general_phone_match:
            identifiers["phone"] = general_phone_match.group(1)
    
    return identifiers

def select_best_identifier(identifiers: Dict[str, str]) -> Optional[str]:
    """根据优先级选择最佳的用户标识符: user_id > id_number > phone"""
    if "user_id" in identifiers:
        return identifiers["user_id"]
    elif "id_number" in identifiers:
        return identifiers["id_number"]
    elif "phone" in identifiers:
        return identifiers["phone"]
    return None

def extract_trace_ids(log_content: str) -> List[str]:
    """从日志内容中提取traceID"""
    # 针对格式: xxxxx:sso:traceID:xxxxx
    trace_pattern = r':[a-z]{3}:([0-9a-f]{12}):'
    matches = re.findall(trace_pattern, log_content)
    
    if not matches:
        # 尝试备用模式，针对其他可能的格式
        fallback_pattern = r'[0-9a-f]{8}(?:[0-9a-f]{4}){3}[0-9a-f]{12}|[0-9a-f]{12}'
        fallback_matches = re.findall(fallback_pattern, log_content)
        return list(set(fallback_matches))
    
    return list(set(matches))  # 去重

def parse_log_response(response: str) -> List[Dict[str, Any]]:
    """解析日志查询结果，提取日志记录"""
    try:
        # 首先判断是否已经是字典类型(已解析的JSON)
        if isinstance(response, dict):
            if "rows" in response and isinstance(response["rows"], list):
                print(f"已解析的JSON数据，找到 {len(response['rows'])} 条日志")
                return response["rows"]
            else:
                print(f"已解析的JSON数据，但未找到有效日志记录")
                return []
        
        # 如果是字符串类型，尝试提取并解析JSON
        if isinstance(response, str):
            # 检查是否是API响应格式
            if "系统日志查询成功，返回结果：" in response:
                json_start = response.find("系统日志查询成功，返回结果：") + len("系统日志查询成功，返回结果：")
                try:
                    # 尝试解析JSON部分
                    json_data = json.loads(response[json_start:])
                    if json_data.get("code") == 0 and "rows" in json_data:
                        print(f"成功解析日志响应，找到 {len(json_data['rows'])} 条日志")
                        return json_data["rows"]
                    else:
                        print(f"解析成功但无有效数据: {json_data.get('code')}")
                except json.JSONDecodeError as e:
                    print(f"JSON解析错误: {e}")
                    
                    # 尝试使用ast.literal_eval作为后备方案
                    try:
                        import ast
                        json_text = response[json_start:]
                        python_obj = ast.literal_eval(json_text)
                        if isinstance(python_obj, dict) and "rows" in python_obj:
                            return python_obj["rows"]
                    except:
                        pass
            
            # 如果上面的方法失败，尝试直接从字符串中找到JSON对象
            json_start = response.find("{")
            json_end = response.rfind("}")
            if json_start >= 0 and json_end > json_start:
                try:
                    json_text = response[json_start:json_end+1]
                    json_data = json.loads(json_text)
                    if "rows" in json_data:
                        print(f"通过直接提取JSON找到 {len(json_data['rows'])} 条日志")
                        return json_data["rows"]
                except:
                    pass
    except Exception as e:
        print(f"日志解析出错: {str(e)}")
    
    # 最后尝试使用传入的原始内容
    try:
        # 直接尝试将整个响应作为字符串解析为JSON
        if isinstance(response, str):
            import ast
            # 使用ast.literal_eval安全地解析Python字面量
            try:
                data = ast.literal_eval(response)
                if isinstance(data, dict) and "rows" in data:
                    print(f"通过literal_eval找到 {len(data['rows'])} 条日志")
                    return data["rows"]
            except:
                # 最后的尝试：只选择与日志格式匹配的行
                log_entries = []
                for line in response.split('\n'):
                    if '{"type":' in line or '"timestamp":' in line:
                        try:
                            entry = json.loads(line)
                            log_entries.append(entry)
                        except:
                            pass
                if log_entries:
                    return log_entries
    except:
        pass
    
    print("无法解析日志响应")
    return []

def query_system_logs(params: Annotated[str, "查询系统日志的参数"]) -> str:
    """从系统日志中获取相关信息，使用POST请求模拟curl查询日志。"""
    # 清理参数 - 去除额外空格、引号等
    cleaned_params = params.strip().strip('"\'').strip()
    
    # 设置请求的 URL
    url = "https://web.rong-data.com/mjlog/elasticsearch/log/list"

    cookie = os.getenv("cookie")
    # 设置请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://web.rong-data.com",
        "Connection": "keep-alive",
        "Referer": "https://web.rong-data.com/mjlog/elasticsearch/log",
        "Cookie": cookie,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=0"
    }
    
    print(f"查询参数: {cleaned_params}")
    
    # 设置请求体
    data = {
        "doc_id": "",
        "doc_id_new": "",
        "timestamp": "",
        "ip": "",
        "projects": "uum-api",
        "project": "uum-api",
        "beginTime": "2025-03-28 00:00:00",
        "endTime": "2025-03-29 23:59:59",  # 扩大时间范围以提高找到日志的概率
        "level": "",
        "message": cleaned_params,
        "tranceId": "and",
        "sort": "asc",
        "pageSize": "100",
        "pageNum": "1",
        "orderByColumn": "",
        "isAsc": "asc"
    }

    # 发送POST请求
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200 and response.json().get("code") == 0:
            return f"系统日志查询成功，返回结果：{response.json()}"
        else:
            return f"查询失败，状态码：{response.status_code},{response.text}"
    except requests.exceptions.RequestException as e:
        return f"请求发生错误: {str(e)}"


def query_logs_and_get_results(ticket_text: str) -> Dict[str, Any]:
    """
    处理完整的日志查询流程：
    1. 提取和选择用户标识符
    2. 使用标识符查询日志
    3. 提取traceID并进行级联查询（最多20个）
    4. 格式化并返回结果
    """
    # 1. 提取用户标识符
    identifiers = extract_user_identifiers(ticket_text)
    best_identifier = select_best_identifier(identifiers)

    if not best_identifier:
        return {
            "status": "error",
            "message": "未从工单中提取到有效的用户标识符",
            "logs": []
        }

    # 2. 使用标识符查询日志
    print(f"使用标识符查询日志: {best_identifier}")
    log_response = query_system_logs(best_identifier)
    logs = parse_log_response(log_response)

    all_logs = logs.copy()  # 保存所有日志的副本
    trace_ids = []

    # 3. 从日志中提取traceID并进行级联查询（最多20个）
    if logs:
        # 提取所有traceID
        for log in logs:
            if "message" in log:
                trace_ids.extend(extract_trace_ids(log["message"]))

        # 去重并限制最多20个traceID
        trace_ids = list(set(trace_ids))[:20]
        print(f"提取到的traceID: {trace_ids}")

        # 使用每个traceID进行查询
        for trace_id in trace_ids:
            trace_response = query_system_logs(trace_id)
            trace_logs = parse_log_response(trace_response)

            # 添加新的日志记录
            all_logs.extend(trace_logs)

    # 4. 去重并返回结果
    unique_logs = []
    seen_messages = set()

    for log in all_logs:
        if "message" in log:
            msg = log["message"]
            if msg not in seen_messages:
                seen_messages.add(msg)
                unique_logs.append(log)

    all_logs = {
        "status": "success" if unique_logs else "no_logs",
        "message": f"查询完成，共找到 {len(unique_logs)} 条日志记录" if unique_logs else "未找到任何相关日志，请使用其他工具",
        "logs": unique_logs,
        "identifiers": identifiers,
        "selected_identifier": best_identifier,
        "trace_ids": trace_ids
    }

    # 5. 格式化并返回结果
    return format_log_results(all_logs);



def format_log_results(results: Dict[str, Any]) -> str:
    """将查询结果格式化为易读的文本格式"""
    if results["status"] == "error":
        return f"错误：{results['message']}"
    
    if results["status"] == "no_logs":
        return f"查询结果：{results['message']}"
    
    output = [f"查询结果：{results['message']}"]
    output.append(f"使用的标识符：{results['selected_identifier']} (类型: {list(results['identifiers'].keys())[list(results['identifiers'].values()).index(results['selected_identifier'])]})")
    
    if results["trace_ids"]:
        output.append(f"发现的 traceID: {', '.join(results['trace_ids'])}")
    
    output.append("")
    for i, log in enumerate(results["logs"], 1):
        # 提取时间戳和日志内容
        timestamp = log.get("timestamp", "未知时间")
        message = log.get("message", "无内容")
        
        # 移除可能的ANSI颜色代码
        message = re.sub(r'\033\[[0-9;]+m', '', message)
        
        # 格式化输出 - 显示完整日志内容
        # output.append(f"{i}. [{timestamp}] {message}")
        output.append(f"{message}")

    return "\n".join(output)

# 示例使用
if __name__ == "__main__":
    # 测试用例
    ticket = """
    请分析以下工单：
    自助交易渠道：（信用卡APP）
    卡片状态：正常
    操作步骤：点击超值优惠券等
    报错内容：手机号校验有误，请重新输入您的信用卡预留手机号，更改后短信验证码及部分券码将默认发放该手机号
    操作交易时间： 2025.1.3日18.00分左右
    客户致电反馈登录信用卡APP点击超值优惠券等提示上述的报错，手机号核对无误，现在客户需要核实原因，要求加急处理，请相关部门协助处理，谢谢！
    用户信息 用户id:1763739554902667264 性别 男，手机号：13518845492
    请获取相关信息并给出分析结果。
    """
    
    results = query_logs_and_get_results(ticket)
    formatted_output = format_log_results(results)
    print(formatted_output) 