from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain_openai import ChatOpenAI
import os
from langchain.prompts import PromptTemplate


class SQLQueryTool:
    def __init__(self):
        load_dotenv()
        self.db = self._setup_db_connection()
        self.llm = self._setup_llm()

    def _setup_db_connection(self):
        db_user = os.getenv("db_user")
        db_password = os.getenv("db_password")
        db_host = os.getenv("db_host")
        db_name = os.getenv("db_name")
        return SQLDatabase.from_uri(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")

    def _setup_llm(self):
        return ChatOpenAI(
            model=os.getenv("MODEL"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_API_BASE"),
            temperature=0,
            streaming=True,
        )

    def generate_sql_query(self, user_query):
        table_info = self.db.get_table_info()

        sql_template = PromptTemplate(
            input_variables=["input", "table_info"],
            template="""
            你是一名专业的数据库工程师，精通SQL查询和数据库结构分析。请基于用户的问题，生成准确的SQL查询语句。

            ## 数据库结构
            以下是数据库中的表及其结构：
            {table_info}

            ## 用户查询
            {input}

            ## 分析思路
            请按以下步骤分析问题并构建查询：
            1. 分析用户查询，确定需要查询哪些信息
            2. 确定涉及的表和字段
            3. 判断是否需要表连接,若需要多表查询，t_member表必须为主表，t_member表id是最重要的用户数据
            4. 确定筛选条件
            5. 考虑排序、分组和聚合需求
            6. 检查SQL性能，确保使用了适当的索引

            ## SQL查询
            请直接生成一个干净的SQL查询语句，只提供SQL代码，不要附加任何解释：
            """
        )

        db_chain = SQLDatabaseChain.from_llm(
            llm=self.llm,
            db=self.db,
            prompt=sql_template,
            return_direct=False,
            return_intermediate_steps=True,
            output_key="result",
            verbose=True
        )

        result = db_chain.invoke({"query": user_query, "table_info": table_info})
        return {"sql_query": result["result"], "query_result": result["intermediate_steps"][3]}


# 示例调用
if __name__ == "__main__":
    sql_tool = SQLQueryTool()
    user_query = "查询用户 ID 为 1763739554902667264 的用户信息。"
    result = sql_tool.generate_sql_query(user_query)
    print("\n----- SQL查询 -----")
    print(result["sql_query"])
    print("\n----- 查询结果 -----")
    print(result["query_result"])
