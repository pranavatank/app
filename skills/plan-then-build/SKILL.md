---
name: plan-then-build
description: Coordinate model-tiered planning, parallel implementation, and independent verification for substantial coding or artifact tasks where delegation can improve quality or speed.
---

# Plan, build, verify

Use this workflow when the user requests a high-level plan followed by implementation with a lower-tier builder and independent high-level review, or asks for parallel implementation with review. Keep the user's authorized scope and delivery goal in control throughout.

## Set up the work

1. Read applicable project instructions, inspect current changes and relevant files, and identify the authorized scope before delegating. Preserve existing staged and unrelated changes.
2. Inspect the models and collaboration tools advertised in the live environment. Do not assume a model or tool is available from memory or another host.
3. By default, use `gpt-6-astra` at high reasoning for the read-only planner and an independent final reviewer, and `gpt-6-luna` for bounded implementation tasks, when those exact choices are advertised.
4. Honor model choices the user names exactly. Never silently substitute a requested model. If a default or requested model is unavailable, choose a suitable advertised fallback only when the user's intent permits it, disclose the substitution, and use `gpt-6.1-sol` as an example fallback when it is advertised and appropriate.
5. Do not invent model IDs, change the host model, alter global configuration, or use SDK or other workarounds to obtain a model. If delegation or model overrides are unavailable, disclose the limitation. Proceed with available capabilities only when compatible with the user's model requirements; otherwise report the blocked requirement and ask before substituting, while continuing independent preparation. Do not claim the full tiered workflow.

## Plan and delegate

Ask the high-level planner for an ordered, read-only plan. It should identify acceptance criteria, dependencies, task boundaries, exclusive file ownership, and verification proportional to the change. Keep its role advisory: it does not edit files.

Split work only when tasks are meaningfully independent. Do not manufacture parallel tasks for one small change. Run ready independent builders concurrently up to the actual available collaboration slots; do not hard-code a slot count. Serialize dependent work, overlapping file ownership, shared mutable state, and GUI-heavy tests or other scarce resources.

For each builder, state the relevant context, exact task and owned files, acceptance criteria, allowed checks, and constraints such as no index changes or commits unless specifically authorized. When creating a subagent with a model override, use the collaboration tool's current schema; where it requires `fork_turns: "none"`, provide the needed context explicitly. Call collaboration tools directly, not from inside `functions.exec`. On other hosts, follow the runtime's actual tool schema.

Builders may resolve routine implementation details within their assigned scope. If they encounter ambiguity they cannot safely resolve, they may escalate to an advertised workhorse model after the higher-level plan has narrowed the task. Keep the user's authorization intact; do not widen scope. Ask the user only when a genuine blocker requires information or authorization.

## Review and finish

Collect each builder's changed files, actual commands and outcomes, unresolved issues, and deviations. The coordinator integrates the work while preserving unrelated and staged changes; do not stage or commit unless authorized.

Use a separate high-level reviewer who did not implement the changes. Have them inspect the final diff and relevant artifacts, logs, and exit codes, and run or assess useful checks when appropriate. If review finds a defect, assign the repair to the responsible builder, then have the reviewer verify the repair. Do not claim checks that were not run or results that were not observed.

Continue within the approved scope without asking for repeated confirmation. Stop only for a real blocker or when the requested result is complete. Do not expand into adjacent work. In the final report, state what changed, verification and outcomes, material limits or fallbacks, and whether any requested step remains. Commit or publish only when authorized.
