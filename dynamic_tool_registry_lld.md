# LLD Case Study: Dynamic Tool Registry

## Problem Shape

We need a runtime tool management layer. The orchestrator should not know every tool in advance. It should ask a registry:

```text
Which tools can this Space see?
What schemas should I send to the LLM?
Can I execute this requested tool with these arguments?
```

The core idea is to separate:

- tool storage,
- tool discovery,
- authorization,
- argument validation,
- execution.

That separation is what makes new tools registerable without modifying the orchestrator.

## Design Pattern View

Use the Registry pattern:

```text
ToolRegistry
    owns name -> ToolDefinition
```

Use the Strategy pattern:

```text
ToolDefinition.handler
    is the executable behavior for that tool
```

Use a capability gate:

```text
SpaceConfig.capabilities
    decides which tools are visible and executable
```

The orchestrator should depend only on the registry API:

```python
schemas = registry.get_llm_schemas(space)
result = await registry.execute(space, tool_name, arguments)
```

It should not care whether the tool came from local code, config, a plugin, or a remote MCP server.

## Data Model

```python
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    capability: str


@dataclass(frozen=True)
class SpaceConfig:
    space_id: str
    capabilities: set[str]
```

`ToolDefinition` is the metadata plus behavior.

`SpaceConfig` is the authorization context.

Example:

```python
space_a = SpaceConfig("marketing", {"sql", "rag"})
space_b = SpaceConfig("documentation", {"rag"})
```

Expected visibility:

```text
marketing     -> run_sql, rag_search
documentation -> rag_search
```

## Main API

```python
class ToolRegistry:
    def register(self, tool: ToolDefinition) -> None:
        ...

    def unregister(self, name: str) -> None:
        ...

    def list_tools(self, space: SpaceConfig) -> list[ToolDefinition]:
        ...

    def get_llm_schemas(self, space: SpaceConfig) -> list[dict]:
        ...

    async def execute(
        self,
        space: SpaceConfig,
        tool_name: str,
        arguments: dict,
    ) -> Any:
        ...
```

## Reference Implementation

See `dynamic_tool_registry.py`.

The registry stores tools privately:

```python
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
```

The underscore is not security by itself, but it communicates ownership: callers should use the API.

## Register

```python
def register(self, tool: ToolDefinition) -> None:
    if tool.name in self._tools:
        raise DuplicateToolError(f"Tool already registered: {tool.name}")

    self._tools[tool.name] = self._copy_tool(tool)
```

Why this matters:

- tool names must be unique because the LLM references tools by name,
- duplicate names should fail loudly,
- the registry stores a defensive copy so the caller cannot mutate the registered schema later.

## Unregister

```python
def unregister(self, name: str) -> None:
    if name not in self._tools:
        raise ToolNotFoundError(f"Tool is not registered: {name}")

    del self._tools[name]
```

This makes the registry dynamic. Tools can be added and removed while the application is running.

In an interview, call out the behavior explicitly:

```text
Unregistering a missing tool is treated as a configuration error.
```

## List Tools

```python
def list_tools(self, space: SpaceConfig) -> list[ToolDefinition]:
    return [
        self._copy_tool(tool)
        for tool in self._tools.values()
        if tool.capability in space.capabilities
    ]
```

This method applies the visibility rule:

```text
Only expose tools whose required capability exists in the Space.
```

Important detail: returned tools are copies. That prevents this bug:

```python
tools = registry.list_tools(space)
tools[0].parameters["required"] = []
```

Without defensive copying, external code could mutate internal registry state.

## LLM Schemas

```python
def get_llm_schemas(self, space: SpaceConfig) -> list[dict]:
    schemas = []

    for tool in self.list_tools(space):
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": copy.deepcopy(tool.parameters),
                },
            }
        )

    return schemas
```

The orchestrator uses this before calling the model:

```python
tools = registry.get_llm_schemas(space)
response = await llm.complete(messages, tools=tools)
```

The orchestrator does not need to know which tools exist.

## Execute

Execution must repeat the authorization check.

```python
async def execute(self, space, tool_name, arguments):
    tool = self._tools.get(tool_name)

    if tool is None:
        raise ToolNotFoundError(...)

    if tool.capability not in space.capabilities:
        raise UnauthorizedToolError(...)

    self._validate_arguments(tool.parameters, arguments)
    return await tool.handler(arguments)
```

Why check authorization again?

Because discovery is not a security boundary.

The LLM may request a hidden tool explicitly:

```text
Model requests: run_sql
Space has only: rag
```

The registry must reject it even if the model asks confidently.

Also, capabilities can change between discovery and execution:

```text
T1: registry exposes run_sql
T2: admin removes sql capability from the Space
T3: model asks for run_sql
T4: execute rejects it
```

## Argument Validation

For interviews, implement a practical subset of JSON Schema:

- required fields,
- unexpected fields,
- primitive JSON types.

```python
missing = required - arguments.keys()
if missing:
    raise ToolValidationError(...)

unexpected = set(arguments.keys()) - set(properties.keys())
if unexpected and not allow_extra:
    raise ToolValidationError(...)
```

This catches:

```text
Missing required argument
Unexpected argument
Wrong primitive type
```

You do not need to implement the full JSON Schema spec unless the interviewer asks.

## Example Usage

```python
registry = build_example_registry()

marketing = SpaceConfig("marketing", {"sql", "rag"})
docs = SpaceConfig("documentation", {"rag"})

print([tool.name for tool in registry.list_tools(marketing)])
# ["rag_search", "run_sql"]

print([tool.name for tool in registry.list_tools(docs)])
# ["rag_search"]

await registry.execute(
    docs,
    "run_sql",
    {"query": "SELECT * FROM campaigns"},
)
# raises UnauthorizedToolError
```

## Edge Cases

Duplicate registration:

```python
raise DuplicateToolError
```

Unregistering a nonexistent tool:

```python
raise ToolNotFoundError
```

Missing required arguments:

```python
raise ToolValidationError
```

Unexpected arguments:

```python
raise ToolValidationError
```

Tool raises an exception:

```python
raise ToolExecutionError
```

Capability changes between discovery and execution:

```python
execute(...) checks capability again
```

## How To Explain In An LLD Round

Start with the separation of concerns:

```text
I would keep the orchestrator independent from concrete tools. The orchestrator asks a ToolRegistry for the LLM-visible schemas for the current Space. The registry filters tools by capability, validates arguments, checks authorization again at execution time, and invokes the registered handler.
```

Then describe the patterns:

```text
This is primarily a Registry pattern. Each handler is a Strategy. The SpaceConfig acts as the authorization context.
```

Then show the security detail:

```text
I would not trust discovery alone. Even if the LLM asks for an unauthorized tool by name, execute() checks the Space capability again and rejects it.
```

That last point is a strong interview signal.

## Follow-Up: Versioned Tools

Two common approaches:

```text
Option 1: Encode version in the name
run_sql_v1
run_sql_v2
```

This is simple and LLM-friendly.

Or:

```python
@dataclass(frozen=True)
class ToolKey:
    name: str
    version: str
```

Then the registry stores:

```python
dict[ToolKey, ToolDefinition]
```

For interviews, I would usually start with versioned names because tool-calling models already address tools by name.

## Follow-Up: Loading MCP Tools Remotely

Treat remote tools as another registration source:

```text
MCP server -> discover tool metadata -> create ToolDefinition -> register()
```

The handler becomes an adapter:

```python
async def handler(arguments):
    return await mcp_client.call_tool(remote_tool_name, arguments)
```

This keeps the orchestrator unchanged.

Design pattern language:

```text
Use Adapter pattern to wrap MCP tool calls behind the same ToolHandler interface.
```

## Follow-Up: Concurrent Registration And Execution

If registration and execution happen concurrently, protect registry state.

Simple approach:

```python
import asyncio

self._lock = asyncio.Lock()
```

Then use the lock around mutations:

```python
async with self._lock:
    self._tools[name] = tool
```

For high-read systems, use copy-on-write:

```text
register creates a new dict snapshot
execute reads from an immutable snapshot
```

This avoids holding a lock while a slow tool executes.

Important rule:

```text
Do not hold the registry lock during handler execution.
```

Otherwise one slow tool could block all registration and discovery.

## Follow-Up: Should Tool Errors Be Returned Or Raised?

Inside the registry, raising typed exceptions is clean:

```python
UnauthorizedToolError
ToolValidationError
ToolExecutionError
```

The agent/orchestrator can decide how to convert those into LLM-visible tool error messages.

That keeps the registry reusable outside LLM agents too.
