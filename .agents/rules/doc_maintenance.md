---
description: Instructs agents to maintain project documentation when making code changes.
---
# Documentation Maintenance Rules

As an AI coding agent working on this repository, you must adhere to the following rules regarding documentation:

1. **Keep Project Context Up-To-Date:** The file `.agents/rules/project_context.md` serves as the primary architectural blueprint for all coding agents. If you make any structural changes to the project (e.g., adding a new module, changing the database schema, modifying the core execution flow), you MUST update `project_context.md` to reflect these changes.
2. **Document New Dependencies:** If you introduce a new dependency, ensure it is documented in the context files.
3. **Reflect Design Decisions:** Any significant design decisions or architectural shifts approved by the user must be recorded in the `project_context.md` or a new rule file.
4. **Action Required:** Before completing your task, verify if the changes you made require documentation updates. If so, apply the updates in the same workflow.
