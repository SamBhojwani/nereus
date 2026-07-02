// Faithful cards: each source renders in a shape true to its platform, but they share
// one <article> shell so the reveal-on-scroll animation + stance footer live in one place.
import { Clock, User, ArrowBigUp, MessageSquare } from "lucide-react";
import StanceBadge from "./StanceBadge.jsx";
import YouTubeEmbed from "./YouTubeEmbed.jsx";
import CardImage from "./CardImage.jsx";
import { useInView } from "../useInView.js";
import { safeUrl } from "../api.js";

const SRC = { news: "News", reddit: "Reddit", youtube: "YouTube" };

// Relative time for the first week ("just now" / 5m / 3h / 2d), then the actual date —
// "900 days ago" is meaningless, and a real date reads cleanly for older items.
function whenLabel(iso) {
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  if (secs < 7 * 86400) return `${Math.floor(secs / 86400)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// A title link that (a) only ever points at a safe http(s) URL and (b) names its own
// destination for screen readers, since "read more"-style ambiguity is an a11y smell.
function TitleLink({ item }) {
  const href = safeUrl(item.url);
  const title = item.title || "Untitled";
  if (!href) return <>{title}</>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">{title}</a>
  );
}

function Body({ item, eager }) {
  if (item.source_type === "youtube") {
    return (
      <>
        <YouTubeEmbed embedUrl={item.embed_url} thumbnailUrl={item.thumbnail_url}
                      title={item.title} eager={eager} />
        <h3><TitleLink item={item} /></h3>
      </>
    );
  }

  if (item.source_type === "reddit")
    return (
      <>
        <h3><TitleLink item={item} /></h3>
        {item.body && <p className="excerpt">{item.body}</p>}
        {(item.likes != null || item.comments != null) && (
          <div className="reddit-meta">
            {item.likes != null && (
              <span className="rm-item"><ArrowBigUp size={15} strokeWidth={1.75} aria-hidden="true" />{item.likes} points</span>
            )}
            {item.comments != null && (
              <span className="rm-item"><MessageSquare size={14} strokeWidth={1.75} aria-hidden="true" />{item.comments} comments</span>
            )}
          </div>
        )}
      </>
    );

  // news: always show a media area (thumbnail, or a consistent placeholder if missing/broken)
  const href = safeUrl(item.url);
  const media = (
    <CardImage src={item.thumbnail_url} alt="" eager={eager}
               sourceUrl={item.url} sourceName={item.author} />
  );
  return (
    <>
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer" className="thumb-link"
           tabIndex={-1} aria-hidden="true">{media}</a>
      ) : media}
      <h3><TitleLink item={item} /></h3>
      {item.body && <p className="excerpt">{item.body}</p>}
    </>
  );
}

export default function ContentCard({ item, index = 0 }) {
  const [ref, inView] = useInView();
  const type = item.source_type;
  const eager = index < 3; // first row is the LCP region — load its images eagerly
  return (
    <article
      ref={ref}
      className={`card card-${type} reveal${inView ? " in" : ""}`}
      style={{ transitionDelay: `${(index % 6) * 45}ms` }}
    >
      <span className={`src-tag ${type === "news" ? "" : type}`}>{SRC[type]}</span>
      <Body item={item} eager={eager} />
      <footer className="card-foot">
        <div className="meta">
          {item.author && (
            <span className="meta-item meta-author">
              <User size={12} strokeWidth={1.75} aria-hidden="true" />
              <span className="meta-name">{item.author}</span>
            </span>
          )}
          {item.published_at && (
            <span className="meta-item">
              <Clock size={12} strokeWidth={1.75} aria-hidden="true" />
              <time dateTime={item.published_at} title={new Date(item.published_at).toLocaleString()}>
                {whenLabel(item.published_at)}
              </time>
            </span>
          )}
        </div>
        <StanceBadge classification={item.classification} />
      </footer>
    </article>
  );
}
