"""AutoMemory adapters for agent frameworks. Each module imports its framework only when used, so the core stays free
of dependencies; install the matching extra, for example ``pip install "efficient-agent-memory[langgraph]"``.

    eam.adapters.base              MemoryHooks: the framework-neutral hooks every adapter calls
    eam.adapters.anthropic         Claude API (Messages): memory-tool storage and a middleware for your own loop
    eam.adapters.claude_agent_sdk  Claude Agent SDK: hooks and in-process memory tools
    eam.adapters.langgraph         LangGraph / LangChain agents
    eam.adapters.openai_agents     OpenAI Agents SDK

Every adapter passes the same offline conformance suite (tests/adapters/conformance.py).
"""

from eam.adapters.base import MemoryHooks

__all__ = ["MemoryHooks"]
