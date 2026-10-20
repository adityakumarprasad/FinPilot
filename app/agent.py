"""A tool-calling agent built as a small LangGraph graph:

    START -> model --(asked for a tool?)-- yes --> tools --+
               ^          | no                             |
               |         END                               |
               +-------------------------------------------+
"""
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app import config, llm


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]     # add_messages APPENDS new messages instead of replacing the list


def build_agent(name: str, tools: list):
    def call_model(state: AgentState):
        return {"messages": [llm.invoke(state["messages"], tools=tools, name=name)]}

    graph = StateGraph(AgentState)
    graph.add_node("model", call_model, retry_policy=llm.RETRY_POLICY)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))   # errors -> message back to the model
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition)               # tool calls -> "tools", else -> END
    graph.add_edge("tools", "model")
    return graph.compile()


def run_agent(name: str, instructions: str, task: str, tools: list) -> str:
    agent = build_agent(name, tools)
    result = agent.invoke({"messages": [SystemMessage(instructions), HumanMessage(task)]},
                          {"recursion_limit": config.MAX_AGENT_STEPS})
    return result["messages"][-1].text
