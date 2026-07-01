# Nereus Classifier — Model Card (Phase 2 evaluation)

The fact-vs-opinion classifier, **measured** on Nereus's own input distribution. This is
the project's differentiator: not "I used an LLM," but "I evaluated it, here's the F1, and
here's where it breaks."

## Setup

- **Task:** binary, article-level — classify each item `factual` vs `opinion`.
- **Classifier:** LLM prompt (zero-shot) returning `{stance, confidence, rationale}`,
  batched ~10 items/call. Behind the swappable `LLMClient` interface.
- **Model evaluated:** `llama-3.3-70b-versatile` via Groq.
  *(Gemini 2.5 selected as primary, but its free daily quota was exhausted during
  development; Groq is the brief's planned fallback. A Gemini run is pending for a
  cross-provider comparison.)*
- **Test set:** **195 items hand-labelled by me**, drawn from Nereus's own live pipeline
  (NewsData.io), not a borrowed benchmark — so the numbers reflect the real input the app
  sees. 137 factual / 58 opinion. 5 genuinely-ambiguous items excluded.

## Headline results

| Metric | factual | opinion |
|---|---|---|
| Precision | 0.932 | 0.641 |
| Recall | 0.796 | 0.862 |
| F1 | 0.858 | 0.735 |

**Accuracy 0.815 · macro-F1 0.797 · coverage 100% (0 unclassified).**

Confusion matrix (rows = predicted, cols = gold):

|              | factual | opinion |
|--------------|:-------:|:-------:|
| **factual**  |   109   |    8    |
| **opinion**  |   28    |   50    |

## Where it breaks

The dominant error is **over-calling "opinion"**: 28 factual items were labelled opinion,
vs only 8 the other way. The classifier catches opinions well (recall 0.86) but is
trigger-happy (opinion precision 0.64). Three recurring causes:

1. **Reported speech read as opinion.** A neutral news report *of* someone's opinion gets
   flagged opinion. E.g. *"AWS CEO says replacing young employees with AI is 'dumbest
   idea'"* → model: "quotes a CEO's opinion"; *"Haroon terms SMEs 'driving force'"* →
   "promotes a particular perspective." The article reports that a statement was made — that's
   factual reporting — but the model latches onto the opinionated *content* of the quote.
2. **Sensational/colourful headlines.** Straight reporting with a punchy headline trips it:
   *"Even Apple couldn't escape the 'RAM-ageddon' crisis"* → "sensationalized headline";
   *"NBA trade speculation gone horribly wrong…"* → "subjective language like 'brutal jab'."
3. **Trend/analysis framing.** *"Why China's young urbanites are romanticising countryside
   living"* → flagged opinion for "subjective interpretation," though it reports a trend.

The reverse error (opinion → factual, 8 cases) is the mirror image: opinion that is
**neutrally framed or data-rich** slips through — e.g. *"Utah ranked second-best
road-tripping state"* (a ranking reported plainly), *"4 Takeaways from Croatia's Win"*
(analysis in an objective register).

**The unifying finding:** the fact/opinion boundary is fuzziest around **reported speech and
analysis** — and these were precisely the hardest items for me to hand-label too. The model
and the human disagree exactly where the task is genuinely ambiguous, not at random.

## Operating point

Confidence-threshold sweep (abstain below threshold):

| threshold | coverage | accuracy on covered |
|:---:|:---:|:---:|
| 0.0 | 1.000 | 0.815 |
| 0.7 | 0.959 | 0.850 |
| 0.8 | 0.805 | 0.892 |
| 0.9 | 0.513 | 0.940 |

**Chosen default: 0.7** — keeps 96% of items labelled at 85% accuracy. Below it, the UI can
show the item as "uncertain" rather than a confident wrong label. For a precision-sensitive
view, 0.8 trades ~20% coverage for ~89% accuracy.

## Honest caveats

- v1 has only the **news** source, which skews factual (137/58). The opinion class — and the
  reported-speech edge cases — will get richer once Reddit lands in Phase 3; re-run then.
- Single human labeller (me): no inter-annotator agreement measured. The ~36 disagreements
  with the model overlap heavily with the items I found hardest to call.
- Zero-shot prompt. A few-shot prompt seeded with reported-speech examples is the obvious
  next lever to lift opinion precision.

## Reproduce

```bash
cd backend && source .venv/bin/activate
python eval/evaluate.py            # reads eval/data/labelling_pool.csv
```
Outputs metrics + `eval/data/predictions.csv` and `eval/data/disagreements.csv`.
