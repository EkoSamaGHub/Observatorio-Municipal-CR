# Claude Prompt Engineering — Conversation Log & Best Practices

## Purpose
This document serves as a living knowledge base for:
- Conversation summaries
- Lessons learned
- Claude optimization techniques
- Token efficiency strategies
- Prompt engineering patterns
- Architectural decisions
- Workflow improvements
- Reusable prompt structures
- Common failure modes and fixes

---

# Core Principles

## 1. Role Separation
Always define:
- Role
- Objective
- Constraints
- Expected output format
- Success criteria

Example:
```xml
<Role>
You are a senior systems architect and prompt engineer.
</Role>
```

---

## 2. XML Structure Improves Reliability
Claude performs significantly better with:
- XML tags
- Clearly separated sections
- Explicit instructions
- Hierarchical organization

Preferred structure:
```xml
<context>
</context>

<task>
</task>

<constraints>
</constraints>

<output_format>
</output_format>
```

---

## 3. Front-Load Constraints
Critical instructions should appear EARLY.

Bad:
- Put constraints at the end.

Good:
- Put constraints near the top.
- Repeat critical constraints.

---

## 4. Specify What NOT To Do
Claude responds well to:
- Positive instructions
- Negative constraints

Example:
```xml
<constraints>
- Do NOT simplify architecture
- Do NOT remove existing functionality
- Do NOT hallucinate APIs
- Do NOT change unrelated files
</constraints>
```

---

## 5. Demand Explicit Reasoning
Useful for:
- Architecture
- Debugging
- Security
- Performance optimization
- Tradeoff analysis

Example:
```xml
<reasoning_requirements>
Explain:
1. Root cause
2. Why current implementation fails
3. Proposed solution
4. Tradeoffs
5. Scalability implications
</reasoning_requirements>
```

---

# Claude Token Optimization

## 1. Reduce Redundant Context
Avoid repeating:
- Project descriptions
- Stack information
- Constraints
- Goals

Instead:
- Use compact reusable templates
- Reference prior sections
- Store stable context once

---

## 2. Use Progressive Disclosure
Bad:
- Dump entire architecture immediately.

Good:
- Start with:
  - Goal
  - Current issue
  - Constraints
- Then add:
  - Logs
  - Files
  - Edge cases
  - Examples

---

## 3. Ask Claude To Plan Before Coding
Highly effective.

Example:
```xml
<workflow>
1. Analyze current system
2. Identify root causes
3. Propose architecture
4. Wait for approval
5. Implement changes
</workflow>
```

This prevents:
- Large wasted outputs
- Incorrect implementations
- Token burn from retries

---

## 4. Use Diffs Instead of Full Rewrites
Prefer:
- File patches
- Targeted edits
- Component-level changes

Avoid:
- Rewriting entire codebases

Example:
```xml
Only return:
- Changed files
- Exact code blocks
- Minimal modifications
```

---

## 5. Compress Repeated Rules
Instead of repeating:
- “Do not hallucinate”
- “Do not remove features”
- “Preserve compatibility”

Create reusable constraint blocks.

---

# Debugging Best Practices

## 1. Provide:
- Expected behavior
- Actual behavior
- Logs
- Stack traces
- Reproduction steps
- Environment details

---

## 2. Ask For Root Cause Analysis First
Better than:
- “Fix this.”

Use:
```xml
Analyze root causes before proposing fixes.
```

---

## 3. Force Verification Steps
Example:
```xml
<verification>
After implementation:
- Verify crawler completion
- Verify retry handling
- Verify database writes
- Verify concurrency limits
</verification>
```

---

# Architecture Prompting Patterns

## Pattern: System Audit
```xml
<task>
Audit the entire system architecture.
</task>

<focus_areas>
- Scalability
- Failure points
- Bottlenecks
- Security
- Technical debt
- Token inefficiencies
</focus_areas>
```

---

## Pattern: Refactor Request
```xml
<task>
Refactor without changing functionality.
</task>

<constraints>
- Preserve APIs
- Preserve database schema
- Preserve UX
</constraints>
```

---

## Pattern: Admin Dashboard Generation
```xml
<requirements>
- Real-time monitoring
- Logs
- Queue visibility
- Retry controls
- Crawl management
- Token usage visibility
</requirements>
```

---

# Lessons Learned

## Railway / Crawler Issue
### Observation
Crawler stalled around 68% completion.

### Suspected Causes
- Queue deadlocks
- Concurrency bottlenecks
- Failed retries blocking queue
- Memory leaks
- Long-running browser sessions
- Missing timeout handling

### Best Practice
Always implement:
- Crawl checkpointing
- Retry queues
- Timeout protection
- Crawl resumability
- Queue observability
- Failure dashboards

---

## Admin Interfaces Matter
Instead of managing systems through:
- GitHub
- Railway
- CLI

Create:
- Internal admin dashboards
- Monitoring panels
- Crawl controls
- Queue inspection tools

Benefits:
- Lower operational overhead
- Faster debugging
- Reduced context switching

---

# Reusable Prompt Wrapper

```xml
<prompt_for_claude>

<role>
</role>

<context>
</context>

<task>
</task>

<constraints>
</constraints>

<technical_requirements>
</technical_requirements>

<reasoning_requirements>
</reasoning_requirements>

<output_format>
</output_format>

</prompt_for_claude>
```

---

# Future Entries

## Date:
## Project:
## Problem:
## Solution:
## Lessons Learned:
## Token Optimization Notes:
## Reusable Prompt Pattern:
## Architectural Improvements:

---

# Notes

This document should evolve continuously as:
- New prompting patterns emerge
- Claude behavior changes
- Token optimization improves
- Architectures become more advanced
- Failures reveal new best practices

