import { useState } from "react";
import { safeUrl } from "../api.js";

// A "facade": show the thumbnail with a play button, and only mount the real YouTube
// iframe once the user clicks. Cheaper to load (no player until wanted), and avoids the
// black-box look of an unplayed embed. Falls back to a bare iframe if there's no thumbnail.
export default function YouTubeEmbed({ embedUrl, thumbnailUrl, title }) {
  const [playing, setPlaying] = useState(false);
  const embed = safeUrl(embedUrl);
  const thumb = safeUrl(thumbnailUrl);
  if (!embed) return null;

  if (playing || !thumb) {
    const src = playing ? embed + (embed.includes("?") ? "&" : "?") + "autoplay=1" : embed;
    return (
      <div className="video">
        <iframe
          src={src}
          title={title || "YouTube video"}
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          loading="lazy"
        />
      </div>
    );
  }

  return (
    <button type="button" className="video video-facade" onClick={() => setPlaying(true)}
            aria-label={`Play video: ${title || "YouTube video"}`}>
      <img className="video-thumb" src={thumb} alt="" loading="lazy" />
      <span className="play-btn" aria-hidden="true" />
    </button>
  );
}
