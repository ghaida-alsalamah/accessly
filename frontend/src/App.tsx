import { useState, useRef, useEffect } from "react";
import { api } from "./api";
import AgentWorkspaceView, { RequestsView as EventsView } from "./AgentWorkspace";

type View = "intro" | "setup" | "home" | "drop" | "events" | "agent";
const A11Y_OPTIONS = [
  {
    id: "wheelchair",
    label: "Wheelchair access",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="4.5" r="1.8" stroke="currentColor" strokeWidth="1.6" />
        <path d="M12 7v5.5l2.5 2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M9.5 9H7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="9" cy="19" r="2.5" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="16.5" cy="19" r="2.5" stroke="currentColor" strokeWidth="1.6" />
        <path d="M14.5 13H17l1 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "parking",
    label: "Accessible parking",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="3" y="3" width="18" height="18" rx="4" stroke="currentColor" strokeWidth="1.6" />
        <path d="M9 17V7h4a3 3 0 010 6H9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "step-free",
    label: "Step-free entrance",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M4 20h4v-4h4v-4h4v-4h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 20L20 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeDasharray="2 3" />
      </svg>
    ),
  },
  {
    id: "seating",
    label: "Accessible seating",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M6 4v8M18 4v8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M4 12h16v4H4z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M7 16v4M17 16v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "captions",
    label: "Live captions",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="2" y="5" width="20" height="14" rx="3" stroke="currentColor" strokeWidth="1.6" />
        <path d="M7 12h4M7 15h6M13 12h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "asl",
    label: "ASL interpretation",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M9 5v6M12 3v8M15 5v6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M6 11c0 3.31 2.69 6 6 6s6-2.69 6-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M10 20h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M12 17v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "listening",
    label: "Assistive listening",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 3a6 6 0 016 6c0 2.4-1.2 4.5-3 5.7V17a2 2 0 01-4 0v-2.3A6 6 0 016 9a6 6 0 016-6z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <circle cx="12" cy="20" r="1" fill="currentColor" />
        <path d="M18.5 5.5a8 8 0 010 11.3M5.5 5.5a8 8 0 000 11.3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "large-print",
    label: "Large-print materials",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M4 18L9 6l5 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M6 14h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M16 8h4M18 6v8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "screen-reader",
    label: "Screen-reader friendly",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <rect x="2" y="4" width="20" height="13" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M8 21h8M12 17v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="12" cy="10.5" r="2.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M7 10.5a5 5 0 0010 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "quiet",
    label: "Quiet / sensory-friendly",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M11 5L6 9H2v6h4l5 4V5z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M17 9l-6 6M17 15l-6-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "other",
    label: "Other accessibility need",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="5" cy="12" r="1.5" fill="currentColor" />
        <circle cx="12" cy="12" r="1.5" fill="currentColor" />
        <circle cx="19" cy="12" r="1.5" fill="currentColor" />
      </svg>
    ),
  },
];

function FlowingBg() {
  return (
    <div
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, overflow: "hidden", zIndex: 0, background: "#fdf8f4" }}
    >
      {/* Top-right: pink - orange bloom */}
      <svg viewBox="0 0 800 700" style={{ position: "absolute", top: -80, right: -100, width: 580, height: 580, opacity: 1 }} xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="bg1" cx="50%" cy="42%" r="55%">
            <stop offset="0%" stopColor="#f9c5d5" stopOpacity="1" />
            <stop offset="35%" stopColor="#f4a06a" stopOpacity="0.75" />
            <stop offset="70%" stopColor="#e8603a" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#e8603a" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="430" cy="290" rx="370" ry="310" fill="url(#bg1)" />
      </svg>

      {/* Top-left: baby blue accent */}
      <svg viewBox="0 0 500 500" style={{ position: "absolute", top: -40, left: -80, width: 380, height: 360, opacity: 0.85 }} xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="bg2" cx="55%" cy="48%" r="52%">
            <stop offset="0%" stopColor="#b8d8f8" stopOpacity="0.9" />
            <stop offset="55%" stopColor="#c8e4fc" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#c8e4fc" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="210" cy="220" rx="230" ry="210" fill="url(#bg2)" />
      </svg>

      {/* Mid-left: pink-to-peach bridge */}
      <svg viewBox="0 0 600 500" style={{ position: "absolute", top: "28%", left: -100, width: 400, height: 340, opacity: 0.65 }} xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="bg3" cx="60%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#fbc8d8" stopOpacity="0.85" />
            <stop offset="55%" stopColor="#fbbaaa" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#fbbaaa" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="230" cy="210" rx="250" ry="190" fill="url(#bg3)" />
      </svg>

      {/* Centre: subtle blue mid-screen balance */}
      <svg viewBox="0 0 500 400" style={{ position: "absolute", top: "38%", right: "8%", width: 300, height: 260, opacity: 0.55 }} xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="bg5" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#a8cef5" stopOpacity="0.75" />
            <stop offset="100%" stopColor="#a8cef5" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="180" cy="160" rx="190" ry="150" fill="url(#bg5)" />
      </svg>

      {/* Bottom-right: deep red/coral organic sweep */}
      <svg viewBox="0 0 700 600" style={{ position: "absolute", bottom: -50, right: -50, width: 540, height: 500, opacity: 1 }} xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="bg4" cx="42%" cy="55%" r="57%">
            <stop offset="0%" stopColor="#b02020" stopOpacity="0.78" />
            <stop offset="28%" stopColor="#d44a20" stopOpacity="0.58" />
            <stop offset="58%" stopColor="#f0804a" stopOpacity="0.3" />
            <stop offset="82%" stopColor="#f9c5d5" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#f9c5d5" stopOpacity="0" />
          </radialGradient>
        </defs>
        <path
          d="M580,500 C500,370 600,285 470,200 C340,115 250,225 165,310 C80,395 50,475 115,550 C175,615 500,620 580,500Z"
          fill="url(#bg4)"
        />
      </svg>

      {/* Bottom-left: deep blue anchor */}
      <svg viewBox="0 0 440 380" style={{ position: "absolute", bottom: 20, left: -60, width: 360, height: 300, opacity: 0.7 }} xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="bg6" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#90c4f0" stopOpacity="0.8" />
            <stop offset="60%" stopColor="#b8d8f8" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#b8d8f8" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="200" cy="190" rx="220" ry="170" fill="url(#bg6)" />
      </svg>
    </div>
  );
}

/* - Arrow button - */
function ArrowBtn({ color = "orange", label }: { color?: "orange" | "blue"; label: string }) {
  const bg = color === "orange" ? "linear-gradient(135deg, #e8703a, #c0392b)" : "linear-gradient(135deg, #5b9bd5, #3a7abf)";
  const shadow = color === "orange" ? "0 6px 18px rgba(200,80,30,0.36)" : "0 6px 18px rgba(58,122,191,0.3)";
  return (
    <span
      aria-hidden="true"
      style={{ width: 42, height: 42, borderRadius: "50%", background: bg, boxShadow: shadow, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}
    >
      <svg width="15" height="15" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M4 10h12M11 5l5 5-5 5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

/* - Action card - */
function ActionCard({ icon, iconBg, cardBg, cardBorder, title, description, arrowColor, onClick }: {
  icon: React.ReactNode;
  iconBg: string;
  cardBg: string;
  cardBorder: string;
  title: string;
  description: string;
  arrowColor: "orange" | "blue";
  onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-label={`${title} - ${description}`}
      style={{
        width: "100%",
        background: cardBg,
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
        border: `1px solid ${cardBorder}`,
        borderRadius: 22,
        padding: "16px",
        minHeight: 102,
        display: "flex",
        alignItems: "center",
        gap: 12,
        cursor: "pointer",
        textAlign: "left",
        boxShadow: hovered
          ? "0 16px 48px rgba(0,0,0,0.09), 0 3px 12px rgba(0,0,0,0.05)"
          : "0 6px 24px rgba(0,0,0,0.06), 0 1px 6px rgba(0,0,0,0.04)",
        transform: hovered ? "translateY(-3px) scale(1.008)" : "translateY(0) scale(1)",
        transition: "all 0.26s cubic-bezier(0.34,1.56,0.64,1)",
      }}
    >
      <div
        style={{
          width: 50,
          height: 50,
          borderRadius: 14,
          background: iconBg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          boxShadow: arrowColor === "orange" ? "0 6px 14px rgba(200,80,30,0.26)" : "0 6px 14px rgba(58,122,191,0.18)",
        }}
        aria-hidden="true"
      >
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 13, fontWeight: 700, color: "#1a1410", margin: 0, lineHeight: 1.2, letterSpacing: "-0.01em", whiteSpace: "nowrap" }}>
          {title}
        </p>
        <p style={{ fontSize: 11, fontWeight: 400, color: "#7a6a60", margin: "3px 0 0", lineHeight: 1.45 }}>
          {description}
        </p>
      </div>
      <ArrowBtn color={arrowColor} label={title} />
    </button>
  );
}

/* - Home View - */
function HomeView({ onNavigate }: { onNavigate: (v: View) => void }) {
  return (
    <div
      style={{
        minHeight: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-start",
        paddingTop: "12vh",
        paddingBottom: "10vh",
        paddingLeft: "clamp(16px, 4vw, 28px)",
        paddingRight: "clamp(16px, 4vw, 28px)",
        position: "relative",
        zIndex: 1,
        maxWidth: 800,
        margin: "0 auto",
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      {/* Hero */}
      <div>
        <h1
          style={{
            fontSize: "clamp(30px, 4.2vw, 44px)",
            fontWeight: 800,
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
            color: "#1a1410",
            margin: "0 0 8px",
          }}
        >
          Turn any event link into
          <br />
          <span
            style={{
              background: "linear-gradient(90deg, #b02020 0%, #e05a2b 50%, #f0a040 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            real action
          </span>
        </h1>
        <p
          style={{
            fontSize: 14,
            fontWeight: 400,
            color: "#7a6a60",
            margin: "0 0 clamp(16px, 3.5vw, 24px)",
            lineHeight: 1.55,
            maxWidth: 440,
          }}
        >
          Let our AI agent handle the details, so you can focus on what matters.
        </p>

        {/* Cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <ActionCard
            onClick={() => onNavigate("drop")}
            iconBg="linear-gradient(145deg, #e8703a 0%, #c0392b 100%)"
            cardBg="rgba(248,228,210,0.58)"
            cardBorder="rgba(220,130,80,0.22)"
            arrowColor="orange"
            title="Drop a Link"
            description="Submit any event link and let the agent do the work."
            icon={
              <svg width="30" height="30" viewBox="0 0 36 36" fill="none" aria-hidden="true">
                <path d="M21.5 14.5a5.5 5.5 0 010 7.78l-3.18 3.18a5.5 5.5 0 01-7.78-7.78l1.59-1.59" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M14.5 21.5a5.5 5.5 0 010-7.78l3.18-3.18a5.5 5.5 0 017.78 7.78l-1.59 1.59" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            }
          />
          <ActionCard
            onClick={() => onNavigate("events")}
            iconBg="linear-gradient(145deg, #d8eaf8 0%, #b8d4f0 100%)"
            cardBg="rgba(210,230,250,0.52)"
            cardBorder="rgba(100,170,230,0.22)"
            arrowColor="blue"
            title="My Requests"
            description="Track requests and check organizer updates."
            icon={
              <svg width="30" height="30" viewBox="0 0 36 36" fill="none" aria-hidden="true">
                <rect x="6" y="8" width="24" height="22" rx="4" stroke="#3a7abf" strokeWidth="2.3" />
                <path d="M12 6v4M24 6v4M6 16h24" stroke="#3a7abf" strokeWidth="2.2" strokeLinecap="round" />
                <path d="M12 22h12M12 26.5h7" stroke="#3a7abf" strokeWidth="2.1" strokeLinecap="round" />
              </svg>
            }
          />
        </div>

        <button className="secondary-button profile-link" onClick={() => onNavigate("setup")}>Edit profile & accessibility needs</button>
        {/* Footer */}
        <div style={{ marginTop: "clamp(20px, 5vw, 32px)", textAlign: "center" }}>
          <p style={{ fontSize: 14, fontWeight: 500, color: "#9a8a80", margin: 0, whiteSpace: "nowrap", letterSpacing: "0.01em" }}>
            Good events lead to great moments.
          </p>
        </div>
      </div>

    </div>
  );
}

/* - Drop Link View - */
function DropLinkView({ onBack, onSubmit }: { onBack: () => void; onSubmit: (url: string) => void }) {
  const [url, setUrl] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim());
  }

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 1, overflow: "auto" }}>
      {/* Back button - fixed to top-left of the screen */}
      <div style={{ position: "absolute", top: "clamp(28px, 6vw, 48px)", left: "clamp(16px, 4vw, 28px)", zIndex: 2 }}>
        <button
          onClick={onBack}
          style={{ display: "inline-flex", alignItems: "center", gap: 7, background: "rgba(255,255,255,0.72)", backdropFilter: "blur(12px)", border: "1px solid rgba(0,0,0,0.07)", borderRadius: 100, padding: "9px 18px", fontSize: 13, fontWeight: 600, color: "#3a2a20", cursor: "pointer", transition: "all 0.2s ease", fontFamily: "inherit" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.95)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.72)")}
          aria-label="Go back to home"
        >
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Back
        </button>
      </div>

      {/* Card centered in the full viewport */}
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 clamp(16px, 4vw, 28px)", boxSizing: "border-box" }}>
      <div style={{ width: "100%", maxWidth: 640, background: "rgba(255,255,255,0.82)", backdropFilter: "blur(24px)", WebkitBackdropFilter: "blur(24px)", border: "1px solid rgba(255,255,255,0.95)", borderRadius: 28, padding: "clamp(20px, 4.5vw, 32px)", boxShadow: "0 20px 64px rgba(200,80,30,0.09), 0 4px 20px rgba(0,0,0,0.05)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 18 }}>
          <div style={{ width: 42, height: 42, borderRadius: 12, background: "linear-gradient(145deg, #e8703a, #c0392b)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 6px 16px rgba(200,80,30,0.26)" }} aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 36 36" fill="none">
              <path d="M21.5 14.5a5.5 5.5 0 010 7.78l-3.18 3.18a5.5 5.5 0 01-7.78-7.78l1.59-1.59" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M14.5 21.5a5.5 5.5 0 010-7.78l3.18-3.18a5.5 5.5 0 017.78 7.78l-1.59 1.59" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <h1 style={{ fontSize: 15, fontWeight: 800, color: "#1a1410", margin: 0, letterSpacing: "-0.02em" }}>Drop a Link</h1>
            <p style={{ fontSize: 11, color: "#7a6a60", margin: "3px 0 0" }}>Paste any event URL to get started.</p>
          </div>
        </div>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 11 }}>
          <label htmlFor="event-url" style={{ fontSize: 12, fontWeight: 600, color: "#5a4a40" }}>Event URL</label>
          <input
            ref={inputRef}
            id="event-url"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://event-website.com/..."
            required
            autoFocus
            style={{ width: "100%", boxSizing: "border-box", borderRadius: 12, border: "1.5px solid rgba(200,80,30,0.2)", background: "rgba(255,255,255,0.8)", padding: "12px 14px", fontSize: 13, color: "#1a1410", outline: "none", transition: "border-color 0.2s, box-shadow 0.2s", fontFamily: "inherit" }}
            onFocus={(e) => { e.currentTarget.style.borderColor = "rgba(200,80,30,0.55)"; e.currentTarget.style.boxShadow = "0 0 0 3px rgba(200,80,30,0.07)"; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = "rgba(200,80,30,0.2)"; e.currentTarget.style.boxShadow = "none"; }}
          />
          <button
            type="submit"
            style={{ background: "linear-gradient(135deg, #e8703a 0%, #c0392b 100%)", color: "white", border: "none", borderRadius: 12, padding: "12px 0", fontSize: 13, fontWeight: 700, cursor: "pointer", boxShadow: "0 10px 28px rgba(200,80,30,0.28)", letterSpacing: "0.01em", fontFamily: "inherit", transition: "opacity 0.2s, transform 0.15s" }}
            onMouseEnter={(e) => { e.currentTarget.style.opacity = "0.9"; e.currentTarget.style.transform = "scale(1.01)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.opacity = "1"; e.currentTarget.style.transform = "scale(1)"; }}
          >
            Process Event
          </button>
        </form>
      </div>
      </div>{/* end centering flex */}
    </div>
  );
}

/* - Agent Workspace - */
function ChipBtn({ opt, on, onToggle }: { opt: typeof A11Y_OPTIONS[0]; on: boolean; onToggle: (id: string) => void }) {
  return (
    <button
      onClick={() => onToggle(opt.id)}
      aria-pressed={on}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        padding: "0 10px",
        height: 58,
        width: "100%",
        boxSizing: "border-box",
        borderRadius: 12,
        border: on ? "1.5px solid rgba(190,75,28,0.50)" : "1.5px solid rgba(255,255,255,0.52)",
        background: on ? "rgba(240,210,188,0.58)" : "rgba(255,255,255,0.28)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        boxShadow: on
          ? "0 0 0 3px rgba(190,75,28,0.10), 0 3px 14px rgba(190,75,28,0.14)"
          : "0 2px 8px rgba(0,0,0,0.06)",
        cursor: "pointer",
        textAlign: "left",
        fontFamily: "inherit",
        color: on ? "#7a1a08" : "#2e201a",
        minWidth: 0,
        overflow: "hidden",
        transition: "border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease",
      }}
    >
      {/* Fixed-width icon column */}
      <span
        aria-hidden="true"
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: on ? "rgba(200,80,30,0.16)" : "rgba(180,155,138,0.16)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
          marginRight: 9,
          color: on ? "#b83010" : "#6a5a50",
          transition: "all 0.18s ease",
        }}
      >
        {opt.icon}
      </span>
      <span style={{
        fontSize: 13,
        fontWeight: 500,
        lineHeight: "17px",
        letterSpacing: "-0.01em",
        minWidth: 0,
        flex: 1,
      }}>
        {opt.label}
      </span>
      {on && <span aria-hidden="true" style={{ marginLeft: 8, fontWeight: 800 }}>{"\u2713"}</span>}
    </button>
  );
}

/* - Accessibility Setup Screen - */
function AccessibilitySetupScreen({ onContinue }: { onContinue: () => void }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [otherText, setOtherText] = useState("");
  const [ctaPressed, setCtaPressed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const originalOther = useRef<string[]>([]);
  function loadProfile() {
    setSaveError("");
    api<{needs: string[]}>("/profile").then(profile => {
      const known = A11Y_OPTIONS.filter(o => profile.needs.includes(o.label)).map(o => o.id);
      const other = profile.needs.filter(n => !A11Y_OPTIONS.some(o => o.label === n));
      setSelected(new Set([...known, ...(other.length ? ["other"] : [])]));
      originalOther.current = other;
      setOtherText(other.join("; ")); setLoaded(true);
    }).catch(e => setSaveError(e.message));
  }
  useEffect(loadProfile, []);
  async function save() {
    if (saving) return;
    setSaving(true); setSaveError("");
    try {
      const needs = A11Y_OPTIONS.filter(o => selected.has(o.id) && o.id !== "other").map(o => o.label);
      if (selected.has("other") && otherText.trim()) {
        if (otherText === originalOther.current.join("; ")) needs.push(...originalOther.current);
        else needs.push(otherText.trim());
      }
      await api("/profile", "PUT", { needs }); onContinue();
    } catch (e) { setSaveError((e as Error).message); }
    finally { setSaving(false); }
  }


  function toggle(id: string) {
    if (!loaded || saving) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        if (id === "other") setOtherText("");
      } else {
        next.add(id);
      }
      return next;
    });
  }

  /* Same background as IntroScreen - one continuous artistic layer */
  const introBg = [
    "radial-gradient(ellipse 140% 70% at -20% 30%, rgba(80,148,210,0.55) 0%, rgba(80,148,210,0) 65%)",
    "radial-gradient(ellipse 90% 55% at -5% 0%, rgba(70,138,200,0.70) 0%, rgba(70,138,200,0) 60%)",
    "radial-gradient(ellipse 200% 30% at 30% -5%, rgba(100,170,225,0.52) 0%, rgba(100,170,225,0) 55%)",
    "radial-gradient(ellipse 90% 50% at -10% 90%, rgba(70,138,200,0.58) 0%, rgba(70,138,200,0) 60%)",
    "radial-gradient(ellipse 160% 28% at 20% 58%, rgba(80,148,210,0.42) 0%, rgba(80,148,210,0) 60%)",
    "radial-gradient(ellipse 90% 60% at 110% 0%, rgba(200,85,8,0.80) 0%, rgba(200,85,8,0) 60%)",
    "radial-gradient(ellipse 55% 40% at 105% 38%, rgba(210,100,30,0.45) 0%, rgba(210,100,30,0) 60%)",
    "radial-gradient(ellipse 80% 25% at 55% 8%, rgba(245,190,215,0.50) 0%, rgba(245,190,215,0) 70%)",
    "radial-gradient(ellipse 100% 40% at 50% 44%, rgba(240,172,200,0.38) 0%, rgba(240,172,200,0) 70%)",
    "radial-gradient(ellipse 110% 65% at 110% 105%, rgba(110,12,12,0.95) 0%, rgba(160,24,24,0.70) 35%, rgba(160,24,24,0) 65%)",
    "radial-gradient(ellipse 35% 55% at 105% 55%, rgba(140,18,18,0.45) 0%, rgba(140,18,18,0) 60%)",
    "linear-gradient(160deg, #d8eaf5 0%, #f0ddd5 35%, #f5e8e0 55%, #e8d0c8 75%, #c89090 100%)",
  ].join(", ");

  return (
    <div
      className="profile-screen"
      role="main"
      style={{
        position: "fixed",
        inset: 0,
        overflow: "hidden",
        overflowX: "hidden",
        background: introBg,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Content column - absolute inset so left/right margins are pixel-exact */}
      <div className="profile-content"
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: 20,
          right: 20,
          display: "flex",
          flexDirection: "column",
          zIndex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          paddingTop: "clamp(48px, 12vh, 80px)",
          paddingBottom: 32,
        }}
      >

        {/* Headline block */}
        <div style={{ marginBottom: 20 }}>
          <h1
            style={{
              fontSize: "clamp(22px, 5.8vw, 28px)",
              fontWeight: 800,
              color: "#120808",
              margin: "0 0 6px",
              lineHeight: 1.1,
              letterSpacing: "-0.025em",
            }}
          >
            Make every event
            <br />
            <span
              style={{
                background: "linear-gradient(90deg, #8a1a10 0%, #c84a20 55%, #e07838 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              work for you.
            </span>
          </h1>
          <p
            style={{
              fontSize: 12,
              fontWeight: 400,
              color: "#3a2a20",
              margin: 0,
              opacity: 0.72,
              lineHeight: 1.5,
            }}
          >
            Your accessibility needs
          </p>
          <p className="helper-text">
            Select what matters to you. You can update these anytime from Home.
          </p>
        </div>

        {/* Accessibility option chips - all full-width, one per row */}
        <div
          role="group"
          className="preference-grid"
          aria-label="Accessibility preferences"
          style={{ display: "flex", flexDirection: "column", gap: 9, marginBottom: 14, minWidth: 0 }}
        >
          {[0, 2, 4, 6, 1, 3, 5, 7, 8, 9, 10].map((i) => {
            const opt = A11Y_OPTIONS[i];
            return <ChipBtn key={opt.id} opt={opt} on={selected.has(opt.id)} onToggle={toggle} />;
          })}
        </div>

        {/* "Other" expandable input */}
        {selected.has("other") && (
          <div style={{ marginBottom: 16, marginTop: -4 }}>
            <input
              type="text"
              autoFocus
              value={otherText}
              onChange={(e) => setOtherText(e.target.value)}
              placeholder="Describe your accessibility need"
              maxLength={120}
              style={{
                width: "100%",
                boxSizing: "border-box",
                borderRadius: 13,
                border: "1.5px solid rgba(190,75,28,0.40)",
                background: "rgba(240,210,188,0.38)",
                backdropFilter: "blur(16px)",
                WebkitBackdropFilter: "blur(16px)",
                padding: "11px 14px",
                fontSize: 13,
                color: "#1a1008",
                outline: "none",
                fontFamily: "inherit",
                transition: "border-color 0.18s, box-shadow 0.18s",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderColor = "rgba(190,75,28,0.62)";
                e.currentTarget.style.boxShadow = "0 0 0 3px rgba(190,75,28,0.09)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "rgba(190,75,28,0.40)";
                e.currentTarget.style.boxShadow = "none";
              }}
              aria-label="Describe your accessibility need"
            />
          </div>
        )}

        {!loaded && !saveError && <p role="status">Loading saved preferences...</p>}
        {saveError && <div className="error-card" role="alert"><p>{saveError}</p>{!loaded && <button className="secondary-button" onClick={loadProfile}>Retry loading preferences</button>}</div>}
        {/* CTA */}
        {(() => {
          const otherOnly = selected.size === 1 && selected.has("other");
          const enabled = loaded && !saving && selected.size > 0 && !(selected.has("other") && !otherText.trim());
          return (
            <button
              onClick={enabled ? save : undefined}
              disabled={!enabled}
              onMouseDown={() => { if (enabled) setCtaPressed(true); }}
              onMouseUp={() => setCtaPressed(false)}
              onTouchStart={() => { if (enabled) setCtaPressed(true); }}
              onTouchEnd={() => setCtaPressed(false)}
              aria-label="Save preferences and continue"
              aria-disabled={!enabled}
              style={{
                width: "100%",
                height: 58, /* matches card height */
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 9,
                background: enabled
                  ? ctaPressed
                    ? "linear-gradient(120deg, #b84a08 0%, #8b1414 100%)"
                    : "linear-gradient(120deg, #c85a10 0%, #9a1818 100%)"
                  : "linear-gradient(120deg, #c85a10 0%, #9a1818 100%)",
                color: "#fdf5ee",
                border: "none",
                borderRadius: 12,
                fontSize: 14,
                fontWeight: 700,
                letterSpacing: "0.015em",
                cursor: enabled ? "pointer" : "default",
                fontFamily: "inherit",
                opacity: enabled ? 1 : 0.38,
                transform: ctaPressed && enabled ? "scale(0.98)" : "scale(1)",
                boxShadow: enabled
                  ? ctaPressed
                    ? "0 4px 14px rgba(140,20,20,0.26)"
                    : "0 10px 28px rgba(140,20,20,0.30), 0 2px 8px rgba(200,80,10,0.16)"
                  : "none",
                transition: "transform 0.14s ease, box-shadow 0.14s ease, opacity 0.2s ease",
              }}
            >
              {saving ? "Saving preferences..." : "Save & Continue"}
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          );
        })()}

        {/* Bottom spacer */}
        <div style={{ flex: "0.8 0 0" }} />
      </div>
    </div>
  );
}

/* - Intro Screen - */
function IntroScreen({ onEnter }: { onEnter: () => void }) {
  const [pressed, setPressed] = useState(false);

  return (
    <div
      className="intro-screen"
      role="main"
      style={{
        position: "fixed",
        inset: 0,
        overflow: "hidden",
        /* Layered gradients - every stop uses a solid colour so there
           are zero transparent gaps anywhere on the canvas.           */
        background: [
          /* 1 - blue washes entire left half + top */
          "radial-gradient(ellipse 140% 70% at -20% 30%, rgba(80,148,210,0.55) 0%, rgba(80,148,210,0) 65%)",
          /* 2 - blue anchors top-left corner firmly */
          "radial-gradient(ellipse 90% 55% at -5% 0%, rgba(70,138,200,0.70) 0%, rgba(70,138,200,0) 60%)",
          /* 3 - blue spreads across full top edge */
          "radial-gradient(ellipse 200% 30% at 30% -5%, rgba(100,170,225,0.52) 0%, rgba(100,170,225,0) 55%)",
          /* 4 - blue lower-left anchor */
          "radial-gradient(ellipse 90% 50% at -10% 90%, rgba(70,138,200,0.58) 0%, rgba(70,138,200,0) 60%)",
          /* 5 - blue horizontal mid-screen band */
          "radial-gradient(ellipse 160% 28% at 20% 58%, rgba(80,148,210,0.42) 0%, rgba(80,148,210,0) 60%)",
          /* 6 - orange claims top-right corner */
          "radial-gradient(ellipse 90% 60% at 110% 0%, rgba(200,85,8,0.80) 0%, rgba(200,85,8,0) 60%)",
          /* 7 - orange bleeds inward mid-right */
          "radial-gradient(ellipse 55% 40% at 105% 38%, rgba(210,100,30,0.45) 0%, rgba(210,100,30,0) 60%)",
          /* 8 - pink bridges top orange - blue seam */
          "radial-gradient(ellipse 80% 25% at 55% 8%, rgba(245,190,215,0.50) 0%, rgba(245,190,215,0) 70%)",
          /* 9 - pink fills centre void */
          "radial-gradient(ellipse 100% 40% at 50% 44%, rgba(240,172,200,0.38) 0%, rgba(240,172,200,0) 70%)",
          /* 10 - red dominates bottom-right */
          "radial-gradient(ellipse 110% 65% at 110% 105%, rgba(110,12,12,0.95) 0%, rgba(160,24,24,0.70) 35%, rgba(160,24,24,0) 65%)",
          /* 11 - red tension sliver mid-right */
          "radial-gradient(ellipse 35% 55% at 105% 55%, rgba(140,18,18,0.45) 0%, rgba(140,18,18,0) 60%)",
          /* 12 - warm tinted base - SOLID, no transparency */
          "linear-gradient(160deg, #d8eaf5 0%, #f0ddd5 35%, #f5e8e0 55%, #e8d0c8 75%, #c89090 100%)",
        ].join(", "),
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* - Content - full height flex column - */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          flex: 1,
          display: "flex",
          flexDirection: "column",
          padding: "0 clamp(28px, 7vw, 44px)",
        }}
      >
        {/* Top breathing room */}
        <div style={{ flex: "1 0 0" }} />

        {/* Copy block */}
        <div style={{ textAlign: "center" }}>
          <h1
            style={{
              fontSize: "clamp(32px, 9vw, 42px)",
              fontWeight: 800,
              color: "#120808",
              margin: "0 0 14px",
              lineHeight: 1.06,
              letterSpacing: "-0.03em",
            }}
          >
            Know before you{" "}
            <span
              style={{
                background: "linear-gradient(90deg, #c85a10 0%, #a31515 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              GO.
            </span>
          </h1>

          <p
            style={{
              fontSize: 13,
              fontWeight: 400,
              color: "#3a2a20",
              margin: 0,
              lineHeight: 1.6,
              opacity: 0.75,
              maxWidth: 280,
              marginLeft: "auto",
              marginRight: "auto",
            }}
          >
            Your AI agent checks if the event works for you before you go.
          </p>
        </div>

        {/* Spacer to CTA */}
        <div style={{ flex: "1 0 0" }} />

        {/* CTA */}
        <button
          onClick={onEnter}
          onMouseDown={() => setPressed(true)}
          onMouseUp={() => setPressed(false)}
          onTouchStart={() => setPressed(true)}
          onTouchEnd={() => setPressed(false)}
          aria-label="Enter the app"
          style={{
            width: "100%",
            height: 56,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            background: pressed
              ? "linear-gradient(120deg, #b84a08 0%, #8b1414 100%)"
              : "linear-gradient(120deg, #c85a10 0%, #9a1818 100%)",
            color: "#fdf5ee",
            border: "none",
            borderRadius: 20,
            fontSize: 15,
            fontWeight: 700,
            letterSpacing: "0.02em",
            cursor: "pointer",
            fontFamily: "inherit",
            transform: pressed ? "scale(0.98)" : "scale(1)",
            boxShadow: pressed
              ? "0 4px 16px rgba(140,20,20,0.28)"
              : "0 10px 32px rgba(140,20,20,0.32), 0 2px 8px rgba(200,80,10,0.18)",
            transition: "transform 0.14s ease, box-shadow 0.14s ease, background 0.14s ease",
          }}
        >
          Enter
          <svg width="17" height="17" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>

        {/* Bottom breathing room - ~10% */}
        <div style={{ flex: "0.7 0 0" }} />
      </div>
    </div>
  );
}

/* - Root - */
export default function App() {
  const [view, setView] = useState<View>("intro");
  const [agentUrl, setAgentUrl] = useState("");

  if (view === "intro") return <IntroScreen onEnter={() => setView("setup")} />;
  if (view === "setup") return <AccessibilitySetupScreen onContinue={() => setView("home")} />;

  return (
    <div style={{ minHeight: "100%", position: "relative" }}>
      <FlowingBg />
      <div role="main" style={{ minHeight: "100%" }}>
        {view === "home" && <HomeView onNavigate={setView} />}
        {view === "drop" && (
          <DropLinkView
            onBack={() => setView("home")}
            onSubmit={(url) => { setAgentUrl(url); setView("agent"); }}
          />
        )}
        {view === "agent" && (
          <AgentWorkspaceView
            key={agentUrl}
            url={agentUrl}
            onBack={() => setView("home")}
            onDone={() => setView("events")}
          />
        )}
        {view === "events" && <EventsView onBack={() => setView("home")} />}
      </div>
    </div>
  );
}
