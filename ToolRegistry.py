import copy
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


# Strategy interface: every tool has different behavior, but the registry
# executes all tools through the same handler shape.
ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class DuplicateToolError(Exception):
    pass


class ToolNotFoundError(Exception):
    pass


class UnauthorizedToolError(Exception):
    pass


class ToolValidationError(Exception):
    pass


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


class ToolRegistry:

    def __init__(self):
        # Registry pattern: central lookup table for all registered tools.
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        # Tool names must be unique because the LLM calls tools by name.
        if tool.name in self._tools:
            raise DuplicateToolError(tool.name)

        self._tools[tool.name] = self._copy_tool(tool)

    def unregister(self, name: str) -> None:
        # Removing a missing tool is treated as a configuration error.
        if name not in self._tools:
            raise ToolNotFoundError(name)

        del self._tools[name]

    def list_tools(self, space: SpaceConfig) -> list[ToolDefinition]:
        # Discovery-time filtering: only expose tools this Space can use.
        return [
            self._copy_tool(tool)
            for tool in self._tools.values()
            if tool.capability in space.capabilities
        ]

    def get_llm_schemas(self, space: SpaceConfig) -> list[dict]:
        # Convert visible tools into LLM-compatible function schemas.
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": copy.deepcopy(tool.parameters),
                },
            }
            for tool in self.list_tools(space)
        ]

    async def execute(
        self,
        space: SpaceConfig,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        tool = self._tools.get(tool_name)

        if tool is None:
            raise ToolNotFoundError(tool_name)

        # Discovery is convenience. Execution is enforcement.
        # The model may request a tool it was never shown.
        if tool.capability not in space.capabilities:
            raise UnauthorizedToolError(tool_name)

        self._validate_arguments(tool.parameters, arguments)

        # Strategy pattern: selected behavior is delegated to the tool handler.
        return await tool.handler(copy.deepcopy(arguments))

    def _copy_tool(self, tool: ToolDefinition) -> ToolDefinition:
        # Defensive copy prevents callers from mutating registry internals.
        return ToolDefinition(
            name=tool.name,
            description=tool.description,
            parameters=copy.deepcopy(tool.parameters),
            handler=tool.handler,
            capability=tool.capability,
        )

    def _validate_arguments(
        self,
        schema: dict[str, Any],
        arguments: dict[str, Any],
    ) -> None:
        # Interview-sized JSON schema validation: required fields,
        # unexpected fields, and primitive type checks.
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        allow_extra = schema.get("additionalProperties", False)

        missing = required - set(arguments.keys())
        if missing:
            raise ToolValidationError(f"Missing args: {sorted(missing)}")

        unexpected = set(arguments.keys()) - set(properties.keys())
        if unexpected and not allow_extra:
            raise ToolValidationError(f"Unexpected args: {sorted(unexpected)}")

        for name, value in arguments.items():
            expected_type = properties.get(name, {}).get("type")
            if expected_type:
                self._validate_type(name, value, expected_type)

    def _validate_type(
        self,
        name: str,
        value: Any,
        expected_type: str,
    ) -> None:
        type_map = {
            "string": str,
            "boolean": bool,
            "object": dict,
            "array": list,
        }

        if expected_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ToolValidationError(f"{name} must be integer")
            return

        if expected_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ToolValidationError(f"{name} must be number")
            return

        python_type = type_map.get(expected_type)
        if python_type is None:
            raise ToolValidationError(f"Unsupported type: {expected_type}")

        if not isinstance(value, python_type):
            raise ToolValidationError(f"{name} must be {expected_type}")
