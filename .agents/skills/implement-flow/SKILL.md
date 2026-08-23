---
name: implement-flow
description: Run implementation under the exact Pstack playbook, with Pocock implementation and review nested at the playbook's implementation step.
---

# Implement flow

Use this router only when the user explicitly invokes `$implement-flow`.

1. Invoke `$poteto-mode`. Read `../../../vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/SKILL.md` completely and let Poteto Mode choose the implementation playbook.
2. Read the selected file under `../../../vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/pstack/skills/poteto-mode/playbooks/` completely. The Pstack playbook owns the outer sequence, proof method, and completion boundary.
3. Keep `$unlazy` and `$clean-code-for-agents` active as standing laws. They do not replace a playbook step or a testing method.
4. At the playbook's implementation step, invoke `$implement` for the agreed spec or ticket. That wrapper preserves exact Pocock Implement, `$pocock-tdd` at pre-agreed seams, and `$code-review` at its review step.
5. An unqualified Pstack `tdd` call remains `$tdd`. The Pocock name mapping applies only inside the Pocock method.

Do not merge, summarize, or reorder the Pstack and Pocock methods.
