# GraphGuard verification rule

For this project, a suspected problem is only a candidate issue until it has
been independently checked by three agents.

- Do not modify paper text, code, figures, tables, results, or reproducibility
  documentation in response to a candidate issue before all three agents have
  reviewed the relevant raw data/artifacts, implementation, and paper context.
- Ask the three agents to verify independently, in parallel, and without
  editing files.
- If all three confirm the same issue, report their evidence and the proposed
  minimal change to the user before or alongside making an authorized change.
- If any agent disagrees, do not modify the affected content. Report the
  disagreement and evidence to the user for a decision.
- Preserve pre-change hashes and keep changes narrowly scoped. Re-run
  independent checks after any modification.
- Never present a suspicion, stylistic preference, or incomplete reading as a
  confirmed factual error.
