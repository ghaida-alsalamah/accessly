import { useEffect, useRef, useState } from "react";

type Preferences = { size: "default" | "large" | "extra"; spacing: boolean; contrast: boolean; motion: boolean; images: boolean; rate: number };
const storageKey = "accessly.display-preferences.v1";
function defaults(): Preferences {
  return { size: "default", spacing: false, contrast: false, motion: window.matchMedia("(prefers-reduced-motion: reduce)").matches, images: true, rate: 0.95 };
}
function readPreferences(): Preferences {
  const base = defaults();
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (!saved || typeof saved !== "object") return base;
    for (const key of ["spacing", "contrast", "motion", "images"] as const) if (typeof saved[key] === "boolean") base[key] = saved[key];
    if (["default", "large", "extra"].includes(saved.size)) base.size = saved.size;
    if ([0.75, 0.95, 1.15].includes(saved.rate)) base.rate = saved.rate;
  } catch { /* Browser storage can be unavailable. Controls still work. */ }
  return base;
}

export default function AccessibilitySettings() {
  const [preferences, setPreferences] = useState(readPreferences);
  const [open, setOpen] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [speechError, setSpeechError] = useState("");
  const wrapper = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const speechSupported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  const utterance = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.readingSize = preferences.size;
    root.dataset.readingSpacing = String(preferences.spacing);
    root.dataset.readingContrast = String(preferences.contrast);
    root.dataset.readingMotion = String(preferences.motion);
    root.dataset.readingImages = String(preferences.images);
    try { localStorage.setItem(storageKey, JSON.stringify(preferences)); } catch { /* Optional persistence. */ }
  }, [preferences]);

  function close() { setOpen(false); trigger.current?.focus(); }
  useEffect(() => {
    if (!open) return;
    closeButton.current?.focus();
    const pointer = (event: PointerEvent) => { if (!wrapper.current?.contains(event.target as Node)) setOpen(false); };
    const keyboard = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); close(); } };
    document.addEventListener("pointerdown", pointer);
    document.addEventListener("keydown", keyboard);
    return () => { document.removeEventListener("pointerdown", pointer); document.removeEventListener("keydown", keyboard); };
  }, [open]);
  useEffect(() => () => { if (speechSupported) window.speechSynthesis.cancel(); }, [speechSupported]);

  function stop() {
    if (speechSupported) window.speechSynthesis.cancel();
    utterance.current = null;
    setSpeaking(false);
  }
  useEffect(() => {
    if (!speaking) return;
    const heading = document.querySelector("[data-accessibility-page] h1")?.textContent;
    const observer = new MutationObserver(() => {
      if (document.querySelector("[data-accessibility-page] h1")?.textContent !== heading) stop();
    });
    observer.observe(document.getElementById("root")!, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [speaking]);
  function readPage() {
    if (!speechSupported) return;
    if (speaking) { stop(); return; }
    setSpeechError("");
    const text = Array.from(document.querySelectorAll<HTMLElement>("[data-accessibility-page] h1, [data-accessibility-page] h2, [data-accessibility-page] h3, [data-accessibility-page] p, [data-accessibility-page] label, [data-accessibility-page] button, [data-accessibility-page] li, [data-accessibility-page] dt, [data-accessibility-page] dd"))
      .filter(element => element.getClientRects().length && getComputedStyle(element).visibility !== "hidden" && !element.closest("[aria-hidden='true'], [hidden], .terms-accordion:not(.terms-accordion-open)"))
      .map(element => element.innerText.trim()).filter(Boolean).join(". ");
    if (!text) { setSpeechError("There is no page text to read yet."); return; }
    const next = new SpeechSynthesisUtterance(text);
    next.rate = preferences.rate;
    next.lang = document.documentElement.lang || "en";
    next.onend = () => { if (utterance.current === next) { setSpeaking(false); utterance.current = null; } };
    next.onerror = event => {
      if (utterance.current !== next) return;
      setSpeaking(false); utterance.current = null;
      if (event.error !== "canceled" && event.error !== "interrupted") setSpeechError("Read aloud is unavailable right now. Please try again.");
    };
    window.speechSynthesis.cancel();
    utterance.current = next;
    window.speechSynthesis.speak(next);
    setSpeaking(true);
  }
  const toggle = (key: "spacing" | "contrast" | "motion" | "images") => setPreferences(current => ({ ...current, [key]: !current[key] }));

  return <div className="display-settings" ref={wrapper}>
    <button className="display-settings-trigger" type="button" ref={trigger} aria-haspopup="dialog" aria-expanded={open} aria-controls="display-settings-panel" onClick={() => setOpen(!open)}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="4" r="2" stroke="currentColor" strokeWidth="1.8"/><path d="M4 8l8 2 8-2M12 10v5m0 0-4 6m4-6 4 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
      Accessibility{speaking && <span className="reading-indicator" aria-label="Reading aloud" />}
    </button>
    {open && <section id="display-settings-panel" className="display-settings-panel" role="dialog" aria-modal="false" aria-labelledby="display-settings-title">
      <header><h2 id="display-settings-title">Accessibility settings</h2><button type="button" ref={closeButton} onClick={close} aria-label="Close accessibility settings">Close</button></header>
      <p className="settings-description">Make Accessly easier to read and use. These settings stay on this browser.</p>
      <fieldset><legend>Text size</legend><div className="text-size-options">{([["default", "Default"], ["large", "Large"], ["extra", "Extra large"]] as const).map(([value, label]) => <button type="button" key={value} aria-pressed={preferences.size === value} onClick={() => setPreferences(current => ({ ...current, size: value }))}>{label}</button>)}</div></fieldset>
      {([["spacing", "More reading space", "Increase line and letter spacing."], ["contrast", "Higher contrast", "Dark text and clear, solid surfaces."], ["motion", "Reduce motion", "Pause decorative movement and transitions."], ["images", "Background images", "Show decorative photos behind the content."]] as const).map(([key, label, description]) => <label className="display-setting-row" key={key}><span><strong>{label}</strong><small>{description}</small></span><input type="checkbox" checked={preferences[key]} onChange={() => toggle(key)} /></label>)}
      <fieldset><legend>Read aloud</legend><label className="reading-speed">Reading speed<select value={preferences.rate} disabled={!speechSupported} onChange={event => { stop(); setPreferences(current => ({ ...current, rate: Number(event.target.value) })); }}><option value={0.75}>Slower</option><option value={0.95}>Normal</option><option value={1.15}>Faster</option></select></label><button type="button" className="read-page-button" disabled={!speechSupported} aria-pressed={speaking} onClick={readPage}>{speaking ? "Stop reading" : "Read this page"}</button>{!speechSupported && <p>This browser does not support read aloud.</p>}{speechError && <p role="status">{speechError}</p>}</fieldset>
      <button type="button" className="reset-display-settings" onClick={() => { stop(); setSpeechError(""); setPreferences(defaults()); }}>Reset display settings</button>
      <p className="settings-footnote">Your saved event accessibility needs are unchanged.</p>
    </section>}
  </div>;
}
