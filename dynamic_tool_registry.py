import copy
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class ToolRegistryError(Exception):
    """Base class for registry-specific failures."""


class DuplicateToolError(ToolRegistryError):
    """Raised when a tool name is registered more than once."""


class ToolNotFoundError(ToolRegistryError):
    """Raised when a requested tool is not registered."""


class UnauthorizedToolError(ToolRegistryError):
    """Raised when a Space does not have the required capability."""


class ToolValidationError(ToolRegistryError):
    """Raised when tool arguments do not match the tool schema."""


class ToolExecutionError(ToolRegistryError):
    """Raised when the underlying tool handler fails."""


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
    """
    Dynamic registry for LLM tools.

    Design pattern view:
    - Registry pattern: one place owns tool discovery and lookup.
    - Strategy pattern: each tool's handler is pluggable behavior.
    - Authorization gate: SpaceConfig decides what each agent Space can see/use.
    """

    def __init__(self) -> None:
        # Keep mutable state private. Callers only receive defensive copies.
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """
        Register a new tool at runtime.

        Tool names are unique because the LLM will reference tools by name.
        Duplicate names are rejected instead of silently replacing behavior.
        """
        if tool.name in self._tools:
            raise DuplicateToolError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = self._copy_tool(tool)

    def unregister(self, name: str) -> None:
        """
        Remove a tool at runtime.

        This keeps the registry dynamic. A missing tool is treated as a caller
        error because silently ignoring it can hide configuration bugs.
        """
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool is not registered: {name}")

        del self._tools[name]

    def list_tools(self, space: SpaceConfig) -> list[ToolDefinition]:
        """
        Return only the tools this Space is allowed to discover.

        Discovery is capability-filtered so the LLM should not even see tools
        that the current Space cannot use. Returned definitions are copies, so
        callers cannot mutate the registry's internal schema objects.
        """
        return [
            self._copy_tool(tool)
            for tool in self._tools.values()
            if tool.capability in space.capabilities
        ]

    def get_llm_schemas(self, space: SpaceConfig) -> list[dict]:
        """
        Convert visible tools into LLM-compatible function schemas.

        The orchestrator can pass this result directly to an LLM client without
        knowing how tools are registered or authorized.
        """
        schemas: list[dict] = []

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

    async def execute(
        self,
        space: SpaceConfig,
        tool_name: str,
        arguments: dict,
    ) -> Any:
        """
        Validate authorization and arguments, then execute the tool.

        Authorization is checked again at execution time because capabilities
        can change after discovery, and the model may request a hidden tool
        explicitly. Discovery filtering is helpful, but execution-time checks
        are the real security boundary.
        """
        tool = self._tools.get(tool_name)

        if tool is None:
            raise ToolNotFoundError(f"Tool is not registered: {tool_name}")

        if tool.capability not in space.capabilities:
            raise UnauthorizedToolError(
                f"Space {space.space_id} cannot execute tool {tool_name}"
            )

        self._validate_arguments(tool.parameters, arguments)

        try:
            result = tool.handler(copy.deepcopy(arguments))

            if inspect.isawaitable(result):
                result = await result

            return result
        except ToolRegistryError:
            raise
        except Exception as exc:
            raise ToolExecutionError(
                f"Tool {tool_name} failed: {type(exc).__name__}: {exc}"
            ) from exc

    def _copy_tool(self, tool: ToolDefinition) -> ToolDefinition:
        """
        Create a defensive copy of a tool definition.

        The handler is intentionally shared because functions are behavior, but
        the parameter schema is deep-copied because it is mutable data.
        """
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
        """
        Validate a practical subset of JSON Schema.

        For interviews, implementing the whole JSON Schema spec is usually too
        much. This covers the common LLM tool schema fields: object type,
        required fields, declared properties, primitive types, and whether extra
        fields are allowed.
        """
        if schema.get("type") != "object":
            raise ToolValidationError("Tool schema must have type='object'")

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        allow_extra = schema.get("additionalProperties", False)

        missing = required - arguments.keys()
        if missing:
            raise ToolValidationError(
                f"Missing required argument(s): {sorted(missing)}"
            )

        unexpected = set(arguments.keys()) - set(properties.keys())
        if unexpected and not allow_extra:
            raise ToolValidationError(
                f"Unexpected argument(s): {sorted(unexpected)}"
            )

        for name, value in arguments.items():
            if name in properties:
                self._validate_type(name, value, properties[name])

    def _validate_type(
        self,
        name: str,
        value: Any,
        field_schema: dict[str, Any],
    ) -> None:
        """Validate a single argument against a simple JSON Schema type."""
        expected_type = field_schema.get("type")

        if expected_type is None:
            return

        validators = {
            "string": lambda item: isinstance(item, str),
            "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
            "number": lambda item: (
                isinstance(item, (int, float)) and not isinstance(item, bool)
            ),
            "boolean": lambda item: isinstance(item, bool),
            "object": lambda item: isinstance(item, dict),
            "array": lambda item: isinstance(item, list),
        }

        validator = validators.get(expected_type)
        if validator is None:
            raise ToolValidationError(f"Unsupported schema type: {expected_type}")

        if not validator(value):
            raise ToolValidationError(
                f"Argument {name} must be of type {expected_type}"
            )


async def rag_search(arguments: dict[str, Any]) -> dict[str, Any]:
    """Example async tool."""
    query = arguments["query"]
    return {"matches": [f"Result for {query}"]}


async def run_sql(arguments: dict[str, Any]) -> dict[str, Any]:
    """Example async tool."""
    return {"rows": [{"campaign": "Campaign A", "revenue": 50000}]}


def build_example_registry() -> ToolRegistry:
    """Small factory showing how new tools are added outside the orchestrator."""
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="rag_search",
            description="Search indexed documents.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=rag_search,
            capability="rag",
        )
    )

    registry.register(
        ToolDefinition(
            name="run_sql",
            description="Run a read-only SQL query.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=run_sql,
            capability="sql",
        )
    )

    return registry
