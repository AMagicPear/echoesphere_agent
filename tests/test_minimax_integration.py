from phoenix.otel import register
import os
from typing import Literal
from tavily import TavilyClient
from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic
from opentelemetry import trace
from openinference.instrumentation.langchain import LangChainInstrumentor

tracer_provider = register(
    project_name="echoesphere-debug",
    auto_instrument=False,
)

LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
tracer = trace.get_tracer(__name__)


tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

client = ChatAnthropic(
    model_name="MiniMax-M2.7",
    base_url="https://api.minimaxi.com/anthropic",  # ty:ignore[unknown-argument]
    api_key=os.environ["MINIMAX_API_KEY"],  # ty:ignore[unknown-argument]
)


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


# System prompt to steer the agent to be an expert researcher
research_instructions = """You are an expert researcher. Your job is to conduct thorough research and then write a polished report.

You have access to an internet search tool as your primary means of gathering information.

## `internet_search`

Use this to run an internet search for a given query. You can specify the max number of results to return, the topic, and whether raw content should be included.
"""

agent = create_deep_agent(
    model=client,
    tools=[internet_search],
    system_prompt=research_instructions,
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What is langgraph? Reply in Chinese."}]}
)

# Print the agent's response
print(result)
