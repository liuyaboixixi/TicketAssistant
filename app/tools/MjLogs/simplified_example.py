from TicketAssistant.Tools.MjLogs.mj_log_query_tool import query_logs_and_get_results

# 测试案例1：使用用户ID
test_case1 = """
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

print("=== 测试案例1 ===")
results1 = query_logs_and_get_results(test_case1)
print(results1)
print("\n")

# 测试案例2：仅有手机号
test_case2 = """
用户反馈无法登录系统，手机号:13518845492，请协助排查问题。
"""

print("=== 测试案例2 ===")
results2 = query_logs_and_get_results(test_case2)
print(results2)