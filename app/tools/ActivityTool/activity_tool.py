from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
import chromadb
import os
from langchain.prompts import PromptTemplate


@tool
def analyze_ticket_subject(query: str) -> str:
    """
    工单活动科目号分析工具：根据用户输入的问题内容，查找最相似的活动描述，辅助判断工单属于哪一个活动。
    """
    # 设置向量库本地存储路径
    PERSIST_DIRECTORY = "C:\\liuyb\\pythonCode\\ai-llm-study\\chroma\\chroma_db"

    # 初始化 embeddings
    embeddings = DashScopeEmbeddings(
        dashscope_api_key="sk-1644b0e12c664989b4765e115b06a3fa",
        model="text-embedding-v3"
    )

    # 使用 PersistentClient 并指定存储路径
    persistent_client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)

    # 加载已存在的向量库
    loaded_vectorstore = Chroma(
        client=persistent_client,
        embedding_function=embeddings,
        collection_name="my_collection",
        persist_directory=PERSIST_DIRECTORY
    )

    # 执行 MMR 多样性搜索
    docs = loaded_vectorstore.max_marginal_relevance_search(
        query=query,
        k=10,
        fetch_k=15,
        lambda_mult=0.5
    )

    # 整合结果为字符串返回
    results = []
    for i, doc in enumerate(docs, 1):
        results.append(f"结果 {i}:\n{doc.page_content}")

    # 将找到的活动描述传给大模型，分析出最可能的 3 个活动
    results_str = "\n\n".join(results)
    # print("向量数据库检索出的活动"+results_str)
    prompt_template = (
        "以下是多个科目号活动描述，请根据这些描述分析出最可能的 3 个活动：\n\n"
        "{results_str}\n\n"
        "请返回最相关的 3 个活动"
    )

    # 使用模板
    prompt = PromptTemplate.from_template(prompt_template)

    # 使用 OpenAI 的大语言模型进行分析
    llm = ChatOpenAI(
        model="qwq-32b",
        openai_api_key="sk-1644b0e12c664989b4765e115b06a3fa",
        openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0,
        streaming=True,
    )
    # 创建 LLMChain 来执行大模型推理
    chain = prompt | llm | StrOutputParser()

    # 直接传递字符串而不是字典
    analysis_result = chain.invoke(results_str)
    print("最相关的三个活动"+ analysis_result)
    return analysis_result


# 假设你已经设置了环境变量
if __name__ == "__main__":
    query = """工单类型：1  信息来源：B  证件类型：null  证件号：00003788904697  联系人姓名：王  卡号：125957259810651790018919351  性别：M
    烦请核实3月蜜雪冰城奖励点情况。
    活动名称： 邮储小绿卡 蜜雪冰城天天1分购（2025年3
    客户致电表示在信用卡APP进行抢兑，邮储小绿卡 蜜雪冰城天天1分购（2025年3月-6月）活动的兑换券未成功，客户称在进行支付最后一步输入验证码后提示，账户异常，为保证资金安全请前往网点咨询。客户前往网点咨询无果后致电，现客户要求核实原因。请相关部门进行协助处理，谢谢。"""

    result = analyze_ticket_subject(query)
    print(result)
