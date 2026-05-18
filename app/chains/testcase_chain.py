"""
Clarion — Test Case Generation Chain
LangChain chain: testcase_prompt | LLM | JsonOutputParser → list[TestCase]
"""
import os
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from loguru import logger

from app.prompts.gen_testcase import GEN_TESTCASE_SYSTEM_PROMPT, GEN_TESTCASE_USER_PROMPT

def _build_generation_llm():
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("GENERATION_LLM_MODEL", "openai/gpt-oss-120b")
    logger.info(f"Building generation LLM for Testcase: provider={provider} model={model}")

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, temperature=0, max_tokens=2048)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0, max_tokens=2048)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0, max_tokens=2048)

    from langchain_community.llms import HuggingFaceEndpoint
    from langchain_community.chat_models.huggingface import ChatHuggingFace
    endpoint = HuggingFaceEndpoint(
        repo_id=model,
        task="text-generation",
        max_new_tokens=2048,
    )
    return ChatHuggingFace(llm=endpoint)

_testcase_chain: Runnable | None = None

def get_testcase_chain() -> Runnable:
    global _testcase_chain
    if _testcase_chain is None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", GEN_TESTCASE_SYSTEM_PROMPT),
            ("human", GEN_TESTCASE_USER_PROMPT),
        ])
        llm = _build_generation_llm()
        parser = JsonOutputParser()
        _testcase_chain = prompt | llm | parser
        logger.info("Testcase generation chain built ✓")
    return _testcase_chain
