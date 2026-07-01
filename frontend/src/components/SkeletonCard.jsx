// Shown in place of blank space while a search fetches + classifies. Mirrors the real
// card's shape so the layout doesn't jump when results arrive. Every 3rd one shows a
// media block for variety (matches the news/YouTube mix).

export default function SkeletonCard({ index = 0 }) {
  const withMedia = index % 3 !== 1;
  return (
    <div className="card skeleton" aria-hidden="true">
      <span className="sk sk-kicker" />
      {withMedia && <span className="sk sk-media" />}
      <span className="sk sk-title" />
      <span className="sk sk-title short" />
      <span className="sk sk-line" />
      <span className="sk sk-line short" />
      <div className="sk-foot">
        <span className="sk sk-line tiny" />
        <span className="sk sk-badge" />
      </div>
    </div>
  );
}
