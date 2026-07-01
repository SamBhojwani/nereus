"""
Phase 2, step 2 — score the classifier against your hand labels.

Reads the labelled CSV, runs the SAME classifier the API uses over the SAME items, and
reports precision / recall / F1 + a confusion matrix. This is the number that makes the
project stand out (BUILD_BRIEF): "I evaluated it — here's the F1 and here's where it breaks."

It also:
  - sweeps a confidence threshold so you can pick an operating point,
  - dumps every disagreement to a CSV so you can write the "where it fails" note.

Run from backend/ (venv active), after labelling:
    python eval/evaluate.py
    python eval/evaluate.py --in eval/data/labelling_pool.csv --batch-size 10

Only GEMINI_API_KEY is needed (items come from the CSV, so no news-API quota is spent).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.classifier.llm import LLMClassifier  # noqa: E402
from app.llm.factory import make_llm  # noqa: E402
from app.models import ContentItem, SourceType, Stance  # noqa: E402

LABELS = ("factual", "opinion")


def load_labelled(path: Path):
    """Return (items, gold_labels) for rows with a valid human_label; report skips."""
    items, gold, skipped = [], [], 0
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label = (row.get("human_label") or "").strip().lower()
            if label not in LABELS:
                skipped += 1
                continue
            items.append(ContentItem(
                id=row["id"],
                source_type=SourceType(row.get("source_type") or "news"),
                title=row.get("title") or None,
                body=row.get("body") or None,
                url=row.get("url") or "https://example.invalid",
            ))
            gold.append(label)
    return items, gold, skipped


async def classify_all(items, batch_size: int, rpm: float):
    """Classify in batches, paced to stay under the free-tier requests-per-minute cap.

    The client also retries 429s, but proactively spacing calls means we rarely trip the
    limit in the first place — far faster than backing off after every burst.
    """
    clf = LLMClassifier(make_llm(), batch_size=batch_size)
    interval = 60.0 / rpm if rpm > 0 else 0.0
    done = 0
    for start in range(0, len(items), batch_size):
        t0 = time.monotonic()
        chunk = items[start : start + batch_size]
        await clf.classify_many(chunk)  # mutates items in place
        done += len(chunk)
        print(f"  classified {done}/{len(items)}")
        if start + batch_size < len(items):  # pace between calls, not after the last
            await asyncio.sleep(max(0.0, interval - (time.monotonic() - t0)))
    return items


def prf(tp: int, fp: int, fn: int):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def report(gold: list[str], items: list[ContentItem]) -> None:
    pred = [it.classification.stance.value for it in items]
    n = len(gold)
    unclassified = sum(1 for p in pred if p == Stance.UNCLASSIFIED.value)
    correct = sum(1 for g, p in zip(gold, pred) if g == p)

    print("\n" + "=" * 60)
    print(f"EVALUATION — {n} labelled items")
    print("=" * 60)
    print(f"gold distribution : factual={gold.count('factual')}  opinion={gold.count('opinion')}")
    print(f"accuracy          : {correct}/{n} = {correct / n:.3f}")
    print(f"coverage          : {(n - unclassified)}/{n} = {(n - unclassified) / n:.3f}"
          f"  ({unclassified} unclassified)")

    # 3x2 confusion matrix: predicted (rows) x gold (cols)
    pred_rows = ["factual", "opinion", Stance.UNCLASSIFIED.value]
    print("\nconfusion matrix (rows = predicted, cols = gold):")
    print(f"{'':>13} | {'factual':>8} {'opinion':>8}")
    print("-" * 35)
    for pr in pred_rows:
        fac = sum(1 for g, p in zip(gold, pred) if p == pr and g == "factual")
        opi = sum(1 for g, p in zip(gold, pred) if p == pr and g == "opinion")
        print(f"{pr:>13} | {fac:>8} {opi:>8}")

    # per-class precision / recall / F1
    print("\nper-class metrics:")
    print(f"{'class':>10} | {'prec':>6} {'recall':>6} {'f1':>6}  support")
    print("-" * 45)
    f1s = []
    for c in LABELS:
        tp = sum(1 for g, p in zip(gold, pred) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold, pred) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold, pred) if g == c and p != c)
        p, r, f1 = prf(tp, fp, fn)
        f1s.append(f1)
        print(f"{c:>10} | {p:>6.3f} {r:>6.3f} {f1:>6.3f}  {gold.count(c):>5}")
    print(f"{'macro-F1':>10} | {'':>6} {'':>6} {sum(f1s) / len(f1s):>6.3f}")

    # confidence-threshold sweep → pick an operating point
    print("\nconfidence-threshold sweep (abstain below threshold):")
    print(f"{'thresh':>7} | {'coverage':>9} {'acc@cov':>8}")
    print("-" * 30)
    for t in (0.0, 0.5, 0.6, 0.7, 0.8, 0.9):
        kept = [(g, it) for g, it in zip(gold, items)
                if it.classification.stance.value in LABELS
                and it.classification.confidence >= t]
        if not kept:
            print(f"{t:>7.1f} | {'0':>9} {'-':>8}")
            continue
        acc = sum(1 for g, it in kept if g == it.classification.stance.value) / len(kept)
        print(f"{t:>7.1f} | {len(kept) / n:>9.3f} {acc:>8.3f}")


def dump_csvs(gold, items, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    preds_path = out_dir / "predictions.csv"
    disagree_path = out_dir / "disagreements.csv"
    cols = ["id", "title", "gold", "predicted", "confidence", "correct", "rationale", "url"]

    rows = []
    for g, it in zip(gold, items):
        c = it.classification
        rows.append({
            "id": it.id, "title": it.title or "", "gold": g,
            "predicted": c.stance.value, "confidence": f"{c.confidence:.2f}",
            "correct": "yes" if g == c.stance.value else "no",
            "rationale": c.rationale or "", "url": it.url,
        })
    for path, subset in ((preds_path, rows),
                         (disagree_path, [r for r in rows if r["correct"] == "no"])):
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(subset)
    print(f"\nwrote {preds_path}  ({len(rows)} rows)")
    print(f"wrote {disagree_path}  ({sum(1 for r in rows if r['correct'] == 'no')} disagreements)")
    print("→ read disagreements.csv to write the 3–5 failure examples for your results note.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="eval/data/labelling_pool.csv")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--rpm", type=float, default=8.0,
                    help="max LLM requests/min (free tier is ~10; stay under it)")
    args = ap.parse_args()

    path = BACKEND_DIR / args.infile
    if not path.exists():
        print(f"{path} not found. Run export_labelling_pool.py and label it first.")
        sys.exit(1)

    items, gold, skipped = load_labelled(path)
    if not items:
        print(f"No labelled rows found in {path} (fill the human_label column). "
              f"{skipped} rows skipped.")
        sys.exit(1)
    print(f"Loaded {len(items)} labelled items ({skipped} unlabelled/skipped). Classifying...")

    asyncio.run(classify_all(items, args.batch_size, args.rpm))
    report(gold, items)
    dump_csvs(gold, items, path.parent)


if __name__ == "__main__":
    main()
