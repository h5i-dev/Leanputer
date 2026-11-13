The optional plotting helper uses matplotlib to render standalone PDF/SVG/PNG
figures from the raw scaling JSON. It never runs a checker or changes outcomes.
Install matplotlib separately and run:

```bash
python tools/plots/evaluation.py --scaling /mnt/scratch/leanputer-runs/scaling.json \
  --output /mnt/scratch/leanputer-runs/figures/scaling
```

The workload is a replicated single identity, not a theorem-coverage corpus.
Raw repeated samples and scope differences from the baseline remain in JSON.
