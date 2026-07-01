import { useEffect, useState } from "react";
import { search as apiSearch, feed as apiFeed } from "./api.js";
import SearchBar from "./components/SearchBar.jsx";
import Filters from "./components/Filters.jsx";
import ContentCard from "./components/ContentCard.jsx";
import SkeletonCard from "./components/SkeletonCard.jsx";

const ALL_SOURCES = ["news", "reddit", "youtube"];
const EXAMPLE_TOPICS = ["Climate change", "Elections", "Artificial intelligence", "Interest rates", "Premier League"];

export default function App() {
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [stance, setStance] = useState("all"); // all | factual | opinion
  const [sources, setSources] = useState(new Set(ALL_SOURCES));
  const [sort, setSort] = useState("newest"); // newest | oldest | relevance

  function loadFeed() {
    setQuery("");
    setStatus("loading");
    apiFeed()
      .then((data) => { setItems(data); setStatus("done"); })
      .catch(() => setStatus("error"));
  }

  // default feed on first load
  useEffect(() => { loadFeed(); }, []);

  async function runSearch(q) {
    if (!q.trim()) return;
    setQuery(q);
    setStatus("loading");
    try {
      setItems(await apiSearch(q));
      setStatus("done");
    } catch {
      setStatus("error");
    }
  }

  // Re-run whatever the user was last looking at (a search, or the default feed).
  const retry = () => (query ? runSearch(query) : loadFeed());

  // Filtering + sorting are client-side only (v1 has no accounts) — a thin, session-local view.
  const filtered = items.filter(
    (it) =>
      sources.has(it.source_type) &&
      (stance === "all" || it.classification?.stance === stance)
  );

  const ts = (it) => (it.published_at ? new Date(it.published_at).getTime() : null);
  const visible = [...filtered].sort((a, b) => {
    if (sort === "relevance") return 0; // keep the backend's returned order (stable sort)
    const ta = ts(a), tb = ts(b);
    if (ta === null && tb === null) return 0;
    if (ta === null) return 1; // undated items sink to the bottom
    if (tb === null) return -1;
    return sort === "newest" ? tb - ta : ta - tb;
  });

  const counts = {
    factual: items.filter((i) => i.classification?.stance === "factual").length,
    opinion: items.filter((i) => i.classification?.stance === "opinion").length,
  };

  // Announced to screen readers via an aria-live region so state changes aren't silent.
  const statusMessage =
    status === "loading" ? "Loading results…"
    : status === "error" ? "Couldn’t load results."
    : status === "done" && visible.length === 0 ? "No results found."
    : status === "done" ? `Showing ${visible.length} result${visible.length === 1 ? "" : "s"}.`
    : "";

  return (
    <div className="app">
      <header className="masthead">
        <h1>Nereus</h1>
        <div className="rule">Fact &amp; Opinion, Separated</div>
        <p className="tagline">Live news, Reddit &amp; YouTube — what’s reported, and what’s argued.</p>
      </header>

      <SearchBar onSearch={runSearch} />

      <div className="examples">
        <span className="examples-label">Try</span>
        {EXAMPLE_TOPICS.map((t) => (
          <button key={t} type="button" className="example-chip"
                  onClick={() => runSearch(t)}>{t}</button>
        ))}
      </div>

      <Filters
        stance={stance} setStance={setStance}
        sources={sources} setSources={setSources}
        sort={sort} setSort={setSort}
        allSources={ALL_SOURCES}
        counts={counts}
      />

      <main aria-busy={status === "loading"}>
        <h2 className="visually-hidden">Results</h2>
        <p className="visually-hidden" role="status" aria-live="polite">{statusMessage}</p>

        {status === "error" && (
          <div className="note error">
            <p>We couldn’t load results just now.</p>
            <button type="button" className="retry" onClick={retry}>Try again</button>
          </div>
        )}

        {status === "loading" && (
          <div className="grid" aria-hidden="true">
            {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} index={i} />)}
          </div>
        )}

        {status === "done" && visible.length === 0 && (
          <p className="note">No items match these filters{query && ` for “${query}”`}.</p>
        )}

        {status === "done" && visible.length > 0 && (
          <div className="grid">
            {visible.map((it, i) => <ContentCard key={it.id} item={it} index={i} />)}
          </div>
        )}
      </main>
    </div>
  );
}
