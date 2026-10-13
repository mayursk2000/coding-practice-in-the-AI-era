# Coding Practice in the AI Era

Practice notes and implementations for low-level design, async agent orchestration, and interview preparation.

## Contents

- `agentic_lld_tool_calling_agent.md` - walkthrough for designing an asynchronous LLM tool-calling agent in an LLD interview.
- `dynamic_tool_registry_lld.md` - case study for a capability-aware dynamic tool registry.
- `LLM_tool_calling_pattern.py` - original scratch implementation and notes for the tool-calling agent pattern.
- `dynamic_tool_registry.py` - commented Python reference implementation for the dynamic registry.
- `src/main/java/lld` - Java low-level design practice problems.

## Java LLD Practice

The Java examples currently include:

- `In_mem_KV` - in-memory key-value store.
- `job_scheduler` - job scheduling model and scheduler implementation.
- `MessagingQueue` - messaging queue implementation.
- `parkinglot` - parking lot entities, spots, tickets, and demo flow.
- `rate_limiter` - token bucket rate limiter.
- `ThreadSafeLRU` - thread-safe LRU cache.

## Agentic LLD Focus

The agentic LLD material covers:

- maintaining conversation history across LLM calls,
- distinguishing assistant tool requests from tool results,
- executing multiple tools concurrently,
- preserving tool-call IDs,
- converting tool failures into tool messages,
- enforcing max iterations and global timeouts,
- explaining the design clearly in an interview round.

## Dynamic Tool Registry Focus

The registry material covers:

- registry and strategy pattern usage,
- runtime registration and unregistration,
- LLM-compatible schema generation,
- Space-based capability filtering,
- execution-time authorization,
- argument validation,
- defensive copies to protect internal state,
- versioning, MCP loading, and concurrency follow-ups.
