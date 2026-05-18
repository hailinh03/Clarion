"""
Clarion — Task Generation Chain
LangChain chain: task_prompt | LLM | JsonOutputParser → list[TechTask]
"""
import os
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from loguru import logger

from app.prompts.gen_tech_task import GEN_TASK_SYSTEM_PROMPT, GEN_TASK_USER_PROMPT

def _build_generation_llm():
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("GENERATION_LLM_MODEL", "openai/gpt-oss-120b")
    logger.info(f"Building generation LLM: provider={provider} model={model}")

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, temperature=0, max_tokens=3000)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, temperature=0, max_tokens=3000)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0, max_tokens=3000)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )

    from langchain_community.llms import HuggingFaceEndpoint
    from langchain_community.chat_models.huggingface import ChatHuggingFace
    endpoint = HuggingFaceEndpoint(
        repo_id=model,
        task="text-generation",
        max_new_tokens=3000,
    )
    return ChatHuggingFace(llm=endpoint)

_task_chain: Runnable | None = None

def get_task_chain() -> Runnable:
    global _task_chain
    if _task_chain is None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", GEN_TASK_SYSTEM_PROMPT),
            ("human", GEN_TASK_USER_PROMPT),
        ])
        llm = _build_generation_llm()
        parser = JsonOutputParser()
        _task_chain = prompt | llm | parser
        logger.info("Task generation chain built ✓")
    return _task_chain
