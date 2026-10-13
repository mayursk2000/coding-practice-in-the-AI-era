import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_choice: str = "auto",
    ) -> LLMResponse:
        ...


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        tools: dict[str, Any],
        max_iterations: int = 5,
        timeout: float = 90.0,
    ):
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations
        self.timeout = timeout

    async def run(self, user_query: str, history: list[dict]) -> str:
        try:
            return await asyncio.wait_for(
                self._run(user_query=user_query, history=history),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            return "The agent timed out before completing the request."

    async def _run(self, user_query: str, history: list[dict]) -> str:
        messages = list(history)
        messages.append({"role": "user", "content": user_query})

        tool_specs = self._build_tool_specs()

        for _ in range(self.max_iterations):
            response = await self.llm.complete(
                messages=messages,
                tools=tool_specs,
                tool_choice="auto",
            )

            messages.append(self._assistant_message(response))

            if response.content and not response.tool_calls:
                return response.content

            if not response.tool_calls:
                return response.content or "The model returned no response."

            tool_messages = await self._execute_tool_calls(response.tool_calls)
            messages.extend(tool_messages)

        final_response = await self.llm.complete(
            messages=messages,
            tools=tool_specs,
            tool_choice="none",
        )

        return final_response.content or "The model did not produce a final answer."

    async def _execute_tool_calls(self, tool_calls: list[ToolCall]) -> list[dict]:
        tasks = [
            self._execute_single_tool_call(tool_call)
            for tool_call in tool_calls
        ]
        return await asyncio.gather(*tasks)

    async def _execute_single_tool_call(self, tool_call: ToolCall) -> dict:
        if tool_call.name not in self.tools:
            return self._tool_message(
                tool_call=tool_call,
                result={"error": f"Unknown tool: {tool_call.name}"},
            )

        tool = self.tools[tool_call.name]

        try:
            result = tool(**tool_call.arguments)

            if inspect.isawaitable(result):
                result = await result

            return self._tool_message(tool_call=tool_call, result=result)
        except Exception as exc:
            return self._tool_message(
                tool_call=tool_call,
                result={
                    "error": str(exc),
                    "type": type(exc).__name__,
                },
            )

    def _assistant_message(self, response: LLMResponse) -> dict:
        message = {
            "role": "assistant",
            "content": response.content,
        }

        if response.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                }
                for call in response.tool_calls
            ]

        return message

    def _tool_message(self, tool_call: ToolCall, result: Any) -> dict:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.name,
            "content": self._serialize_tool_result(result),
        }

    def _serialize_tool_result(self, result: Any) -> str:
        try:
            return json.dumps(result)
        except TypeError:
            return json.dumps({"result": repr(result)})

    def _build_tool_specs(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": getattr(tool, "__doc__", "") or "",
            }
            for name, tool in self.tools.items()
        ]
