---
name: plan-flow
description: Run the Pstack-owned planning route with exact Pocock planning methods nested at their named branches. Stops before implementation.
---

# Plan flow

Use this router only when the user explicitly invokes `$plan-flow`.

1. Invoke `$poteto-mode`. Read `../../../vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/SKILL.md` completely, including its Principles index.
2. Read `../../../vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md` and `../../../vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/references/plan.md` completely. Those Pstack files own the outer planning sequence and its deliverable.
3. Run exact Pocock skills only where the Pstack plan needs them. Use `$grilling` with `$domain-modeling` for unresolved decisions, `$research` for facts from primary sources, and `$wayfinder` only when the route is too foggy for one session. Once decisions are settled, use `$to-spec`, then `$to-tickets` when the approved work needs tickets.
4. Follow every selected skill in full. Return its result to the Pstack planning sequence without combining or rewriting either method.
5. Deliver the plan and stop. Leave implementation for a later explicit request.
