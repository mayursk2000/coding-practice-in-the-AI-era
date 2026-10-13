from dataclasses import dataclass, field
from typing import Any, Protocol
import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass
class ToolCall(Protocol):
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)

class LLMClient(Protocol):
    async def complete(self, messages: list[dict],
                       tools: list[dict],
                       tool_choice: str = "auto") -> LLMResponse:
        ...

class Agent:
    def __init__(self, llm: LLMClient, tools: dict[str, Any], max_iterations: int = 5, timeout: float = 90.0,):
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations
        self.timeout = timeout

        async def run(
                self,
                user_query: str,
                history: list[dict],
        ) -> str:
            try:
                return await asyncio.wait_for(
                    self._run(user_query, history), timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                return " The agent timed out while processing your request. Please try again later."

        async def _run(
                self,
                user_query: str,
                history: list[dict],
        ) -> str:

            messages = list(history)
            messages.append({"role": "user", "content": user_query})

            tool_specs = self._build_tool_specs()

            #looks to be the loop here for the agent to keep calling the LLM until it gets a response or reaches max iterations
            for _ in range(self.max_iterations):
                response = await self.llm.complete(messages = messages, tool = tool_specs, tool_choice = "auto",)

                assistant_message = self.assistant_message(response)
                messages.append(assistant_message)

                if response.content and not response.tool_calls:
                    return response.content
                if not response.tool_calls:
                    return r"The agent did not provide a valid response. Please try again."

                tool_messages = await self._execute_tool_calls(response.tool_calls)
                messages.extend(tool_messages)

            #final message after the last tool call result sent to llm
            final_response = await self.llm.complete(messages = messages, tool = tool_specs, tool_choice = "none",)

            return final_response.content or "The model did not provide a final answer. Please try again."

        async def _execute_tool_calls(self, tool_calls: list[ToolCall],)->list[dict]:
            tasks=  [
                self._execute_single_tool_call(tool_call) for tool_call in tool_calls
            ]

            return await asyncio.gather(*tasks)

        async def _execute_single_tool_call(
                self,
                tool_call:ToolCall,
        ) -> dict:
            if tool_call.name not in self.tools:
                return self.tool_message(tool_call = tool_call, result = {"error": f"Unknown tool: {tool_call.name}"
                                },
                )

            tool= self.tools[tool_call.name]

            try:
                result = tool(**tool_call.arguments)

                if inspect.isawaitable(result):
                    result = await result

                return self.tool_message(
                    tool_call = tool_call,
                    result = result,
                )

            except Exception as e:
                return self.tool_message(
                    tool_call = tool_call,
                    result = {
                        "error": str(exc),
                        "type": type(exc).__name__,
                    },
                )

        def _tool_message(self, tool_call: ToolCall, result: Any, )-> dict:
            return {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_call.name,
                "content": self._serialize_result(result),
            }

        def _serialize_result(self, result: Any) -> str:
            try:
                return json.dumps(result)
            except TypeError:
                return json.dumps({"result": repr(result)})

        
        def _build_tool_specs(self) -> list[dict]:
            return [
                {
                    "name": name,
                    "description": getattr(tool, "__doc__", "")
                }
                for name, tool in self.tools.items()
            ]    

        #now we are done will tool calls, handling ,exceptions and tool message delivery to the llm

        #implementing the assistant message function to format LLM output back into LLM messages
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


#follow ups

#messages - maintains conversation messages ( local list + append every tool call and return as a message)
#never mutate caller's original history - list is creating only a shallow copy, deep one is intact
# due to checks, we are executing a tool call only if ita known one

#tool results populated with id - reference between llm tool call generated and results obtained

# supporting multiple tool calls per message output - due to async and gather for sequential result writes though execution in parallel

# exception handling done for tool failures

# final LLM analyze call with all tool calls and responses

#adding token usage tracking here - for each response, keep track of input and output tokens and updted after every llm response
# 


