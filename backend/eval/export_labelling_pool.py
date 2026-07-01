"""
Phase 2, step 1 — export a labelling pool from Nereus's OWN pipeline.

Why from our own pipeline and not a borrowed dataset: measuring on the real input
distribution the classifier will actually see is what makes the evaluation defensible
(BUILD_BRIEF, Phase 2). This runs a spread of live queries through the same Retriever
the API uses, dedupes, and writes a CSV with an empty `human_label` column for you to
fill in by hand.

Run from the backend/ dir (venv active):
    python eval/export_labelling_pool.py            # ~200 items -> eval/data/labelling_pool.csv
    python eval/export_labelling_pool.py --target 150 --out eval/data/pool.csv

Then open the CSV and put `factual` or `opinion` in the human_label column for each row.
Leave genuinely ambiguous ones blank or mark them — they're the interesting cases.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import random
import sys
from pathlib import Path

# Make `app` importable and load the backend's .env regardless of cwd.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from app.pipeline.retrieve import Retriever  # noqa: E402
from app.sources.news import NewsDataSource  # noqa: E402

# A spread chosen to surface BOTH registers from the news source: hard-news queries
# (factual-leaning) and analysis/opinion-leaning queries (editorials, reviews, columns).
# v1 has only the news source; once Reddit lands (Phase 3) the opinion class gets richer.
QUERIES = [
    # factual-leaning
    "election results", "interest rate decision", "earthquake", "company earnings",
    "court ruling", "unemployment data", "election", "scientific study",
    "inflation report", "gdp growth", "clinical trial", "merger",
    "data breach", "supreme court", "wildfire", "flood",
    "vaccine", "space launch", "product recall", "central bank",
    # opinion / analysis-leaning
    "opinion", "editorial", "analysis", "why", "review",
    "what this means", "is overrated", "should we",
    "commentary", "column", "perspective", "debate",
    "the case for", "the case against", "ranked", "verdict",
]

FIELDS = ["id", "source_type", "title", "body", "url", "author", "published_at", "human_label"]


async def gather_pool(per_query: int) -> list:
    retriever = Retriever([NewsDataSource()])
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    pool = []
    for q in QUERIES:
        items = await retriever.retrieve(q, per_source=per_query)
        for it in items:
            title_key = (it.title or "").strip().lower()
            if it.id in seen_ids or (title_key and title_key in seen_titles):
                continue
            seen_ids.add(it.id)
            if title_key:
                seen_titles.add(title_key)
            pool.append(it)
        print(f"  '{q}': +{len(items)} fetched, pool now {len(pool)}")
    return pool


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=200, help="max items to write")
    ap.add_argument("--per-query", type=int, default=20, help="items fetched per query")
    ap.add_argument("--out", default="eval/data/labelling_pool.csv")
    ap.add_argument("--seed", type=int, default=13, help="shuffle seed (reproducible)")
    args = ap.parse_args()

    if not os.getenv("NEWSDATA_API_KEY"):
        print("NEWSDATA_API_KEY not set — fill backend/.env first. Aborting.")
        sys.exit(1)

    print("Fetching labelling pool from the live pipeline...")
    pool = asyncio.run(gather_pool(args.per_query))

    random.Random(args.seed).shuffle(pool)  # unbias labelling order
    pool = pool[: args.target]

    out_path = BACKEND_DIR / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for it in pool:
            w.writerow({
                "id": it.id,
                "source_type": it.source_type.value,
                "title": it.title or "",
                "body": it.body or "",
                "url": it.url,
                "author": it.author or "",
                "published_at": it.published_at.isoformat() if it.published_at else "",
                "human_label": "",  # <- you fill this: factual | opinion
            })

    print(f"\nWrote {len(pool)} items to {out_path}")
    print("Next: open it, fill the human_label column (factual/opinion), then run eval/evaluate.py")


if __name__ == "__main__":
    main()
