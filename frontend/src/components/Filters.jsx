// The headline filter is fact-vs-opinion; source toggles sit beside it.
// All client-side (session-local) — no accounts in v1.
import { ArrowUpDown, Info } from "lucide-react";

const SOURCE_LABELS = { news: "News", reddit: "Reddit", youtube: "YouTube" };

export default function Filters({ stance, setStance, sources, setSources, sort, setSort, allSources, counts }) {
  function toggleSource(s) {
    const next = new Set(sources);
    next.has(s) ? next.delete(s) : next.add(s);
    if (next.size === 0) return; // never let the user hide everything
    setSources(next);
  }

  return (
    <div className="filters">
      <div className="stance-area">
        <div className="stance-toggle" role="group" aria-label="Fact or opinion filter">
          <button type="button" aria-pressed={stance === "all"}
                  className={stance === "all" ? "on" : ""} onClick={() => setStance("all")}>
            All
          </button>
          <button type="button" aria-pressed={stance === "factual"}
                  className={"factual" + (stance === "factual" ? " on" : "")}
                  onClick={() => setStance("factual")}>
            <span className="dot" aria-hidden="true" />Factual <span className="count">{counts.factual}</span>
          </button>
          <button type="button" aria-pressed={stance === "opinion"}
                  className={"opinion" + (stance === "opinion" ? " on" : "")}
                  onClick={() => setStance("opinion")}>
            <span className="dot" aria-hidden="true" />Opinion <span className="count">{counts.opinion}</span>
          </button>
        </div>

        <span className="label-info">
          <button type="button" className="label-info-btn"
                  aria-label="How the fact and opinion labels work">
            <Info size={15} strokeWidth={1.75} aria-hidden="true" />
          </button>
          <span className="label-info-pop" role="tooltip">
            Each item is labelled fact or opinion by an AI classifier, evaluated at ~82%
            accuracy on a hand-labelled test set. It’s a signal, not a verdict — hover any
            label to see the model’s reasoning.
            <a href="https://github.com/SamBhojwani/nereus/blob/main/MODEL_CARD.md"
               target="_blank" rel="noopener noreferrer">How it’s measured →</a>
          </span>
        </span>
      </div>

      <div className="right-controls">
        <label className="sort">
          <ArrowUpDown size={13} strokeWidth={1.75} aria-hidden="true" />
          Sort
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort order">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="relevance">Most relevant</option>
          </select>
        </label>

        <div className="source-toggle" role="group" aria-label="Source filter">
          {allSources.map((s) => (
            <label key={s} className={sources.has(s) ? "chip on" : "chip"}>
              <input type="checkbox" checked={sources.has(s)} onChange={() => toggleSource(s)} />
              {SOURCE_LABELS[s]}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
