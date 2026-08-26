# Two-axis review

Review the diff since a fixed point on two axes, in parallel subagents, then stop. Do not merge the reports. Do not repair during review.

- **Standards.** Does the diff follow this repo's documented coding standards, plus Akita in `.cursor/rules/akita.mdc`?
- **Spec.** Does the diff do what the ask, ticket, or spec required? Flag missing behaviour and extra behaviour.

Each subagent stays under 400 words. Paste both reports. End with a count per axis.

Then follow [one-pass.md](one-pass.md): the aggregated findings are the sweep. One repair batch next. One proof after that.

If there is no spec, the Spec agent reports "no spec available" and the Standards axis still runs.
