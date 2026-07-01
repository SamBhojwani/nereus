import { useEffect, useRef, useState } from "react";

// Reveal-on-scroll: returns [ref, inView]. Sets inView true once the element enters
// the viewport, then stops observing. Falls back to visible if IntersectionObserver
// is missing or the user prefers reduced motion — content must never stay hidden.
export function useInView() {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!el || reduce || typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          obs.disconnect();
        }
      },
      { threshold: 0.06, rootMargin: "0px 0px -40px 0px" }
    );
    obs.observe(el);
    // Fail-safe: never let a card stay hidden if the observer doesn't fire
    // (odd viewports, backgrounded tabs). Reveal after a short beat regardless.
    const fallback = setTimeout(() => setInView(true), 1200);
    return () => { obs.disconnect(); clearTimeout(fallback); };
  }, []);

  return [ref, inView];
}
