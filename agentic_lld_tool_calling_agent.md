# Agentic LLD: Tool-Calling Agent

## Problem Shape

Design an asynchronous agent that repeatedly calls an LLM. The LLM can either:

1. return a final answer, or
2. request one or more tool calls.

When tools are requested, the agent executes them, appends tool results to the message history, and calls the LLM again.

The core loop is:

```text
copy history
add user query
while under iteration limit:
    call LLM
    append assistant response
    if final answer:
        return it
    execute requested tools
    append tool results
make final LLM call with tool_choice="none"
return final synthesis
```

## Key Design Decisions

The agent owns a local copy of messages:

```python
messages = list(history)
messages.append({"role": "user", "content": user_query})
```

This avoids mutating the caller's original history.

The assistant message records what the model asked for:

```python
{
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "call_1",
            "name": "run_sql",
            "arguments": {"query": "SELECT ..."},
        }
    ],
}
```

The tool message records the result:

```python
{
    "role": "tool",
    "tool_call_id": "call_1",
    "name": "run_sql",
    "content": "{\"campaign\": \"Campaign A\", \"revenue\": 50000}",
}
```

These are separate because the model first asks for a tool, then the agent runs it.

## Reference Implementation

See `agent_tool_calling_agent.py`.

Important parts:

```python
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
```

The final synthesis call is made only after the tool-calling loop is exhausted:

```python
final_response = await self.llm.complete(
    messages=messages,
    tools=tool_specs,
    tool_choice="none",
)
```

## Why `_assistant_message` Exists

`_assistant_message` stores the model's response in the conversation history.

If the model requested tools, it stores the tool request, not the tool result:

```python
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
```

Tool results are populated later by `_tool_message`:

```python
def _tool_message(self, tool_call: ToolCall, result: Any) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "name": tool_call.name,
        "content": self._serialize_tool_result(result),
    }
```

This gives the next LLM call a complete transcript:

```text
user asked question
assistant requested tool call call_1
tool returned result for call_1
assistant gives final answer
```

## Handling Unknown Tools

Never execute a tool unless it is registered:

```python
if tool_call.name not in self.tools:
    return self._tool_message(
        tool_call=tool_call,
        result={"error": f"Unknown tool: {tool_call.name}"},
    )
```

The unknown tool becomes a normal tool result, so the LLM can recover.

## Handling Tool Exceptions

Tool errors should not crash the agent:

```python
try:
    result = tool(**tool_call.arguments)
    if inspect.isawaitable(result):
        result = await result
except Exception as exc:
    result = {
        "error": str(exc),
        "type": type(exc).__name__,
    }
```

In an interview, explain that tool failures are part of the conversation state.

## Multiple Tool Calls

The agent supports several tool calls in one LLM response:

```python
tasks = [
    self._execute_single_tool_call(tool_call)
    for tool_call in tool_calls
]

return await asyncio.gather(*tasks)
```

`asyncio.gather` runs tasks concurrently but returns results in the same order as the input list.

That preserves message ordering even if tools finish at different times.

## Deadline and Termination

Termination is guaranteed by:

1. returning when the LLM gives final content,
2. limiting tool-calling rounds with `max_iterations`,
3. wrapping the entire run in `asyncio.wait_for`.

```python
return await asyncio.wait_for(
    self._run(user_query=user_query, history=history),
    timeout=self.timeout,
)
```

This timeout includes LLM calls, tool execution, and the final synthesis call.

## Edge Cases

No content and no tools:

```python
return response.content or "The model returned no response."
```

Unknown tool:

```python
{"error": "Unknown tool: some_tool"}
```

Tool returns a non-JSON-serializable object:

```python
try:
    return json.dumps(result)
except TypeError:
    return json.dumps({"result": repr(result)})
```

LLM loops forever:

```python
for _ in range(self.max_iterations):
    ...
```

Deadline expires during LLM call:

```python
except asyncio.TimeoutError:
    return "The agent timed out before completing the request."
```

## How To Explain In An LLD Round

Use this structure:

1. Clarify the expected LLM response shape.
2. Define `ToolCall`, `LLMResponse`, and `LLMClient`.
3. Describe the agent loop.
4. Explain assistant messages versus tool messages.
5. Explain concurrent tool execution.
6. Explain exception handling.
7. Explain termination guarantees.
8. Mention extensions such as token tracking and observability.

Strong interview phrasing:

```text
I would model this as a bounded async orchestration loop. The agent keeps a local copy of the message history, sends it to the LLM, records the assistant response, executes any requested registered tools, appends tool result messages using the original tool-call IDs, and repeats. It terminates on final content, iteration limit, or global timeout.
```

## Follow-Up: Token Tracking

Extend the response model:

```python
@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
```

Then return a richer result:

```python
@dataclass
class AgentResult:
    content: str
    iterations: int
    input_tokens: int
    output_tokens: int
    timed_out: bool = False
```

For an interview, say that production systems should return metadata rather than only a string.
