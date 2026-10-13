# Coding Practice in the AI Era

Practice notes and implementations for low-level design, async agent orchestration, and interview preparation.

## Contents

- `agentic_lld_tool_calling_agent.md` - walkthrough for designing an asynchronous LLM tool-calling agent in an LLD interview.
- `LLM_tool_calling_pattern.py` - original scratch implementation and notes for the tool-calling agent pattern.
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
