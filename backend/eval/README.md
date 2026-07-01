# Phase 2 — Evaluating the Nereus classifier

This is the differentiator: not "I used an LLM" but "I built a classifier, **measured**
it, and know where it fails." The whole workflow is two scripts.

## Workflow

From the `backend/` directory, with the venv active and `.env` filled in:

```bash
# 1. Export ~200 real items from the live pipeline into a CSV
python eval/export_labelling_pool.py
#    -> eval/data/labelling_pool.csv  (with an empty human_label column)

# 2. Hand-label: open the CSV, put `factual` or `opinion` in human_label for each row.
#    - Read title + body, not just the headline.
#    - Be honest about genuinely ambiguous ones (analysis pieces, news-framed opinion).
#      Those are the interesting cases — leave blank to exclude, or pick the dominant register.

# 3. Score it
python eval/evaluate.py
#    -> prints accuracy, per-class precision/recall/F1, a confusion matrix,
#       and a confidence-threshold sweep
#    -> writes eval/data/predictions.csv and eval/data/disagreements.csv
```

Only `GEMINI_API_KEY` is needed for step 3 — items come from the CSV, so no news-API
quota is spent re-running the evaluation.

## What to produce from it (the resume artifact)

After scoring, write a short **results note** (drop it in the top-level README or a
`MODEL_CARD.md`):

1. The headline numbers: macro-F1, per-class P/R/F1, accuracy, coverage.
2. 3–5 concrete failure examples from `disagreements.csv` and *why* each fails
   (e.g. "misreads analysis pieces with factual framing as factual").
3. The operating point you chose from the threshold sweep and why.

## Honest caveats to note

- v1 has only the **news** source, which skews factual. The opinion class gets richer
  once Reddit lands in Phase 3 — re-run this then for a stronger, more balanced eval.
- This measures the classifier on Nereus's *real* input distribution, which is the
  point: it's defensible precisely because it's not a borrowed benchmark.

## Files

`eval/data/` (gitignored by default) holds generated CSVs. If you want the labelled
test set in the repo as a defensible artifact, force-add it:
`git add -f eval/data/labelling_pool.csv`.
