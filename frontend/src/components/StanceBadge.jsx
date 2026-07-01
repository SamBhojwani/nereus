// The AI output, surfaced on every card. Hover shows the model's rationale — the "why"
// that the evaluated classifier produces (see MODEL_CARD.md).

const LABELS = { factual: "Factual", opinion: "Opinion", unclassified: "Unrated" };

export default function StanceBadge({ classification }) {
  const c = classification || {};
  const stance = c.stance || "unclassified";
  const pct = c.confidence != null ? Math.round(c.confidence * 100) : null;
  const label = LABELS[stance] ?? LABELS.unclassified;

  // A full spoken phrase for screen readers (the visual badge is terse + color-coded).
  const aria =
    stance === "unclassified"
      ? "Not yet classified as fact or opinion"
      : `Classified as ${label.toLowerCase()}${pct != null ? `, ${pct}% confidence` : ""}`;

  // Rationale on hover for sighted users; the empty-string fallback avoids a stray tooltip.
  const tip = c.rationale || (stance === "unclassified" ? "Classifier hasn’t rated this item" : "");

  return (
    <span className={`badge badge-${stance}`} title={tip} aria-label={aria}>
      <span className="dot" aria-hidden="true" />
      <span aria-hidden="true">{label}</span>
      {pct != null && stance !== "unclassified" && <em aria-hidden="true">{pct}%</em>}
    </span>
  );
}
