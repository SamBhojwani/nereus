// Faithful cards: each source renders in a shape true to its platform, but they share
// one <article> shell so the reveal-on-scroll animation + stance footer live in one place.
import StanceBadge from "./StanceBadge.jsx";
import YouTubeEmbed from "./YouTubeEmbed.jsx";
import { useInView } from "../useInView.js";
import { safeUrl } from "../api.js";

const SRC = { news: "News", reddit: "Reddit", youtube: "YouTube" };

function timeAgo(iso) {
  if (!iso) return null;
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  for (const [u, s] of [["d", 86400], ["h", 3600], ["m", 60]])
    if (secs >= s) return `${Math.floor(secs / s)}${u} ago`;
  return "just now";
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

function Body({ item }) {
  if (item.source_type === "youtube") {
    return (
      <>
        <YouTubeEmbed embedUrl={item.embed_url} thumbnailUrl={item.thumbnail_url} title={item.title} />
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
            {item.likes != null && <span>{item.likes} points</span>}
            {item.comments != null && <span>{item.comments} comments</span>}
          </div>
        )}
      </>
    );

  const href = safeUrl(item.url);
  const thumb = safeUrl(item.thumbnail_url);
  return (
    <>
      {thumb && href && (
        <a href={href} target="_blank" rel="noopener noreferrer" className="thumb-link"
           tabIndex={-1} aria-hidden="true">
          <img className="thumb" src={thumb} alt="" loading="lazy" />
        </a>
      )}
      <h3><TitleLink item={item} /></h3>
      {item.body && <p className="excerpt">{item.body}</p>}
    </>
  );
}

export default function ContentCard({ item, index = 0 }) {
  const [ref, inView] = useInView();
  const type = item.source_type;
  return (
    <article
      ref={ref}
      className={`card card-${type} reveal${inView ? " in" : ""}`}
      style={{ transitionDelay: `${(index % 6) * 45}ms` }}
    >
      <span className={`src-tag ${type === "news" ? "" : type}`}>{SRC[type]}</span>
      <Body item={item} />
      <footer className="card-foot">
        <span className="attribution">
          {item.author}
          {item.published_at && <> · {timeAgo(item.published_at)}</>}
        </span>
        <StanceBadge classification={item.classification} />
      </footer>
    </article>
  );
}
