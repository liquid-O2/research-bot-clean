# Grill a decision

Use this when a genuine product or preference call has no experiment that can settle it. Facts you can observe are not the human's to answer.

Map the work as a **design tree**: every decision branches into the decisions that hang off it. The **frontier** is every question whose prerequisites are already settled.

Work in rounds:

1. Ask the whole frontier in one round. Number each question. Give your recommended answer.
2. Wait for the user's answers. Do not answer for them.
3. Recompute the frontier. Repeat until it is empty.

Finding facts is your job. Dispatch a subagent for filesystem or tool facts. Do not ask the user for anything you can look up.

The session is done when nothing is left silently assumed. Do not act on the tree until the user confirms the shared understanding, unless they already opted into full autonomy for that class of decision.
