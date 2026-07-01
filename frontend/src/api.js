// The ONLY place the frontend talks to the backend. Keeping all fetches here is
// what keeps the UI a thin rendering layer (and makes a future mobile client a drop-in).
// Dev: calls go to /api and Vite proxies to the backend. Prod: set VITE_API_BASE.

const BASE = import.meta.env.VITE_API_BASE ?? "/api";
const TIMEOUT_MS = 30000; // never let the UI hang on a slow/stuck backend

async function get(path, params) {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (Array.isArray(v)) v.forEach((x) => url.searchParams.append(k, x));
    else if (v != null) url.searchParams.set(k, v);
  });

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError")
      throw new Error(`Request timed out after ${TIMEOUT_MS / 1000}s`);
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const search = (q, sources) => get("/search", { q, sources });
export const feed = () => get("/feed");
export const health = () => get("/health");

// Defense in depth: only ever put http(s) URLs into an href/src. A hostile source could
// otherwise sneak a `javascript:` URL through and turn a click into script execution.
export function safeUrl(url) {
  if (typeof url !== "string") return null;
  try {
    const u = new URL(url, window.location.origin);
    return u.protocol === "http:" || u.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}
