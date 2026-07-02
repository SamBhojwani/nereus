import { useState } from "react";
import { safeUrl } from "../api.js";

// News thumbnail with graceful states: a shimmer while the image loads; and when there's
// no thumbnail (or it fails), the outlet's own logo instead of a blank box. The box always
// reserves its height, so the grid never shifts. `eager` opts the first row out of lazy
// loading (it's the LCP region — lazy-loading above-the-fold images hurts LCP).
export default function CardImage({ src, alt = "", eager = false, sourceUrl, sourceName }) {
  const url = safeUrl(src);
  const [status, setStatus] = useState(url ? "loading" : "empty");

  return (
    <div className="thumb-box" data-status={status}>
      {url && (
        <img
          className="thumb"
          src={url}
          alt={alt}
          loading={eager ? "eager" : "lazy"}
          fetchpriority={eager ? "high" : "auto"}
          decoding="async"
          onLoad={() => setStatus("loaded")}
          onError={() => setStatus("error")}
        />
      )}
      {status !== "loaded" && (
        <span className="thumb-ph" aria-hidden="true">
          {(status === "empty" || status === "error") && (
            <SourceLogo sourceUrl={sourceUrl} sourceName={sourceName} />
          )}
        </span>
      )}
    </div>
  );
}

// The outlet's favicon (via a favicon service) when we have a domain; if that fails to
// load, a serif monogram of the outlet's name. Note: the favicon lookup makes a request
// to a third-party endpoint with the outlet's domain.
function SourceLogo({ sourceUrl, sourceName }) {
  const [failed, setFailed] = useState(false);
  let domain = null;
  try { domain = new URL(sourceUrl).hostname; } catch { /* no usable URL */ }

  if (domain && !failed) {
    return (
      <img
        className="thumb-logo"
        alt=""
        decoding="async"
        src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=128`}
        onError={() => setFailed(true)}
      />
    );
  }

  const initial = (sourceName || "").trim().charAt(0).toUpperCase() || "?";
  return <span className="thumb-mono">{initial}</span>;
}
