---
name: plan-then-build
description: Coordinate concise planning, bounded implementation, and independent review for substantial work where delegation helps.
---

# Plan, build, review

Use this workflow when the user asks for planning followed by implementation and independent review, or parallel implementation with review. Preserve implicit invocation, the user's authorized scope, and existing staged or unrelated changes.

## Models and setup

1. Read applicable project instructions, inspect the current changes and relevant files, and establish the authorized scope before delegating.
2. Check the live environment's advertised models and collaboration tools. Do not infer availability from another host or memory.
3. Use `gpt-6.1-sol` at medium reasoning for one brief, read-only planning pass and one independent final review. Delegate implementation edits to `gpt-6-luna` at medium reasoning; the coordinator may inspect, integrate, test, and commit when authorized.
4. Do not use Astra, high reasoning, automatic workhorse escalation, or substitute/fallback models. Do not reinterpret these model restrictions; only an explicit user instruction can change them. If a required model or override is unavailable, state the limitation and do not claim the requested tiered workflow. Continue only work compatible with the user's requirements.
5. Never invent model IDs, claim to switch the host model, alter global configuration, or use SDK/workarounds to obtain a model. Be honest that advertised choices do not guarantee a host switch or quota/token savings. Report exact usage only when the environment exposes it.

## Plan and implement

Ask the planner for ordered acceptance criteria, dependencies, meaningful task boundaries, exclusive file ownership, and proportionate checks. Keep it advisory and read-only. Do one planning pass; resume that plan as work proceeds instead of restarting it.

Delegate only meaningfully independent tasks. For a simple task, use one Luna builder and avoid artificial fan-out. At most two Luna builders may run concurrently, and only on distinct files with independent work. Do not nest delegation. Serialize dependencies, overlapping ownership, shared state, and scarce test resources.

Keep each delegation narrow: default to `fork_turns: "none"` and provide a focused brief of about 200 words or less with relevant context, owned files, acceptance criteria, checks, and constraints. Ask for a concise reply (about 150 words or less) unless more is needed to report findings. Builders may resolve routine choices inside scope; escalate genuine blockers to the coordinator rather than changing model tier or authorization.

Use token-efficient inspection: bounded `rg` searches, diffs, and relevant excerpts; avoid rereading or reproducing whole documents. At handoffs, keep a durable checkpoint in the existing task plan or notes recording decisions, completed checks, remaining work, and the next command; resume from it without replanning. State one concise next command. Reuse checks that already passed unless code or assumptions changed. Wait 30–60 seconds between progress checks rather than rapidly polling.

## Review and finish

Integrate changes while preserving unrelated and staged work. Do not stage, commit, or publish unless authorized. Have a separate `gpt-6.1-sol` medium reviewer inspect the final diff and relevant evidence once. If review finds a defect, ask its responsible builder to repair only the changed issue, then have the reviewer check that repair; do not repeat full analysis. Do not claim checks that were not run or outcomes not observed.

Continue within scope without seeking repeated confirmation. Respect an explicit user stop instruction immediately. Stop for a genuine blocker or when the requested result is complete. Report changes, observed verification, limitations, and any remaining requested step.
