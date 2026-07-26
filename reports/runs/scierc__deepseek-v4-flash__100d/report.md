# GraphGuard experiment report

This compatibility entry points to the current generated aggregate report:
[`summary.md`](summary.md).

The SciERC run was extended after the original report was generated. Its
current lineage counts are 7,004 extraction events, 55,697 extracted edges,
and 6,336 materialized counterfactual views. Regenerate `summary.md` and
`summary.json` from the local lineage database with:

```bash
python scripts/make_report.py \
  --docred-config configs/scierc.yaml \
  --db data/processed/runs/scierc__deepseek-v4-flash__100d/scierc__deepseek-v4-flash__100d.db \
  --out reports/runs/scierc__deepseek-v4-flash__100d \
  --e0 data/processed/runs/scierc__deepseek-v4-flash__100d/reports/e0_report.json \
  --e1 data/processed/runs/scierc__deepseek-v4-flash__100d/reports/e1_report.json \
  --e2 data/processed/runs/scierc__deepseek-v4-flash__100d/reports/e2_report.json \
  --e3 data/processed/runs/scierc__deepseek-v4-flash__100d/reports/e3_report.json \
  --e4 data/processed/runs/scierc__deepseek-v4-flash__100d/reports/e4_report.json \
  --repair data/processed/runs/scierc__deepseek-v4-flash__100d/reports/repair_report.json \
  --e5-audit data/processed/runs/scierc__deepseek-v4-flash__100d/reports/e5_audit_report.json \
  --cases 8
```
