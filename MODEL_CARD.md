# Nereus Classifier — Model Card (Phase 2 evaluation)

The fact-vs-opinion classifier, **measured** on Nereus's own input distribution. This is
the project's differentiator: not "I used an LLM," but "I evaluated it, here's the F1, and
here's where it breaks."

## Setup

- **Task:** binary, article-level — classify each item `factual` vs `opinion`.
- **Classifier:** LLM prompt (zero-shot) returning `{stance, confidence, rationale}`,
  batched ~10 items/call. Behind the swappable `LLMClient` interface.
- **Model evaluated:** `llama-3.1-8b-instant` via Groq (operational model).
- **Test set:** **195 items hand-labelled by me**, drawn from Nereus's own live pipeline
  (NewsData.io), not a borrowed benchmark — so the numbers reflect the real input the app
  sees. 137 factual / 58 opinion. 5 genuinely-ambiguous items excluded.

## Model selection (70b → 8b)

The classifier was first evaluated on `llama-3.3-70b-versatile`, but its Groq free-tier
budget of **100k tokens/day** is the binding constraint of the whole app — enough for only
~7 fresh searches/day. `llama-3.1-8b-instant` has a **500k tokens/day** budget (5×) and is
faster. Rather than assume the smaller model was good enough, I re-ran the *same* eval
harness on the *same* 195 labels. The result: **statistically on par.**

| Metric | 70b | 8b (operational) |
|---|:---:|:---:|
| Accuracy | 0.815 | **0.821** |
| Macro-F1 | 0.797 | **0.792** |
| Factual F1 | 0.858 | **0.869** |
| Opinion F1 | 0.735 | **0.715** |

A 0.005 macro-F1 change for 5× the daily headroom — so 8b is the operational model. This is
the point of having an eval harness: a model swap is a measured decision, not a guess.

## Headline results (8b)

| Metric | factual | opinion |
|---|---|---|
| Precision | 0.892 | 0.677 |
| Recall | 0.847 | 0.759 |
| F1 | 0.869 | 0.715 |

**Accuracy 0.821 · macro-F1 0.792 · coverage 100% (0 unclassified).**

Confusion matrix (rows = predicted, cols = gold):

|              | factual | opinion |
|--------------|:-------:|:-------:|
| **factual**  |   116   |   14    |
| **opinion**  |   21    |   44    |

## Where it breaks

The dominant error is **over-calling "opinion"**: 21 factual items were labelled opinion,
vs 14 the other way. The classifier catches opinions reasonably (recall 0.76) but is
trigger-happy on factual reporting (opinion precision 0.68). Three recurring causes:

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

The reverse error (opinion → factual, 14 cases) is the mirror image: opinion that is
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
| 0.0 | 1.000 | 0.821 |
| 0.7 | 0.938 | 0.842 |
| 0.8 | 0.810 | 0.861 |
| 0.9 | 0.528 | 0.893 |

**Chosen default: 0.7** — keeps 94% of items labelled at 84% accuracy. Below it, the UI can
show the item as "uncertain" rather than a confident wrong label. For a precision-sensitive
view, 0.8 trades ~13% coverage for ~86% accuracy.

## Honest caveats

- The eval set is **news-derived** (labelled before Reddit/YouTube landed in Phase 3), so it
  skews factual (137/58). The app now pulls all three sources; re-labelling a mixed-source
  pool — especially Reddit's opinion-heavy posts — is the next step to measure the opinion
  class on the fuller distribution.
- Single human labeller (me): no inter-annotator agreement measured. The 35 disagreements
  with the model overlap heavily with the items I found hardest to call.
- Zero-shot prompt. A few-shot prompt seeded with reported-speech examples is the obvious
  next lever to lift opinion precision.

## Reproduce

```bash
cd backend && source .venv/bin/activate
python eval/evaluate.py            # reads eval/data/labelling_pool.csv
```
Outputs metrics + `eval/data/predictions.csv` and `eval/data/disagreements.csv`.
