// The AI output, surfaced on every card. Hovering (or focusing) the badge reveals a small
// panel with the classifier's reasoning for THIS item — the "why" behind the label.
// See MODEL_CARD.md for how the classifier is evaluated.
import { BadgeCheck, Quote, CircleHelp } from "lucide-react";

const LABELS = { factual: "Factual", opinion: "Opinion", unclassified: "Unrated" };
const ICONS = { factual: BadgeCheck, opinion: Quote, unclassified: CircleHelp };

function confidenceWord(conf) {
  if (conf == null) return null;
  if (conf >= 0.8) return "High";
  if (conf >= 0.6) return "Moderate";
  return "Low";
}

export default function StanceBadge({ classification }) {
  const c = classification || {};
  const stance = c.stance || "unclassified";
  const label = LABELS[stance] ?? LABELS.unclassified;
  const Icon = ICONS[stance] ?? CircleHelp;
  const rationale = (c.rationale || "").trim();
  const conf = confidenceWord(c.confidence);

  const isRated = stance === "factual" || stance === "opinion";

  // Screen readers get the whole story from the label (no hover needed).
  const aria = isRated
    ? `AI-labelled ${label.toLowerCase()}${rationale ? `. Reason: ${rationale}` : ""}` +
      `${conf ? `. ${conf} confidence` : ""}`
    : "Not yet classified as fact or opinion";

  return (
    <span className={`badge badge-${stance}`} tabIndex={0} aria-label={aria}>
      <Icon size={13} strokeWidth={2} aria-hidden="true" />
      <span aria-hidden="true">{label}</span>

      <span className="badge-pop" role="tooltip" aria-hidden="true">
        {isRated ? (
          <>
            <span className="badge-pop-kicker"><span className="kdot" />Why {label.toLowerCase()}</span>
            {rationale && <span className="badge-pop-reason">{rationale}</span>}
            {conf && <span className="badge-pop-meta">{conf} confidence</span>}
          </>
        ) : (
          <>
            <span className="badge-pop-kicker"><span className="kdot" />Unrated</span>
            <span className="badge-pop-reason">Not yet labelled by the classifier.</span>
          </>
        )}
      </span>
    </span>
  );
}
