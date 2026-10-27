import { useState, useRef, useEffect } from "react";
import { api, setAccessToken, endSession, clearConversations } from "./api";
import { firebaseEnabled, createPasswordAccount, loginWithPassword, resetPassword, authErrorMessage, firebaseAuth } from "./firebase";
import studentProjectsExpo from "./imports/saudi-academic/ksu-media-conference-audience.jpg";
import teamDesignExpo from "./imports/saudi-academic/kfupm-team-design-expo.jpg";
import steamChallenge from "./imports/saudi-academic/kaust-steam-challenge.jpg";
import eventRegistration from "./imports/saudi-academic/kaust-event-registration.jpg";
import inclusiveWorkshop from "./imports/saudi-academic/saudi-inclusive-workshop.jpg";
import signLanguageForum from "./imports/saudi-academic/riyadh-forum-sign-language.jpg";
import academicPanel from "./imports/saudi-academic/kaust-wise-panel.jpg";
import academicNetworking from "./imports/saudi-academic/kaust-wise-networking.jpg";
import modernCampus from "./imports/saudi-academic/kaust-modern-campus.jpg";
import wheelchairCampusApproach from "./imports/saudi-academic/wheelchair-campus-approach.jpg";
import wheelchairWomanEntrance from "./imports/saudi-academic/wheelchair-woman-academic-entrance.jpg";
import AgentWorkspaceView from "./AgentWorkspace";
import EventsView from "./SavedEvents";

type View = "intro" | "auth" | "login" | "basic" | "setup" | "final" | "home" | "drop" | "events" | "agent";
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
    label: "Other",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="5" cy="12" r="1.5" fill="currentColor" />
        <circle cx="12" cy="12" r="1.5" fill="currentColor" />
        <circle cx="19" cy="12" r="1.5" fill="currentColor" />
      </svg>
    ),
  },
];

/* ── Background ── */
function FlowingBg({ zIndex = 0 }: { zIndex?: number }) {
  return (
    <div
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, overflow: "hidden", zIndex, background: "#fdf8f4" }}
    >
      {/* Top-right: pink → orange bloom */}
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

/* ── Arrow button ── */
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

/* ── Action card ── */
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
      aria-label={`${title} — ${description}`}
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

/* ── Home View ── */
function HomeView({ onNavigate, onEditAccessibility }: { onNavigate: (v: View) => void; onEditAccessibility: () => void }) {
  return (
    <div
      style={{
        minHeight: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-start",
        paddingTop: "19vh",
        paddingBottom: "19vh",
        paddingLeft: "clamp(16px, 4vw, 28px)",
        paddingRight: "clamp(16px, 4vw, 28px)",
        position: "relative",
        zIndex: 1,
        maxWidth: 640,
        margin: "0 auto",
        width: "100%",
        boxSizing: "border-box",
      }}
    >
      {/* Hero */}
      <div>
        <h1
          style={{
            fontSize: "clamp(18px, 4.2vw, 22px)",
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
            fontSize: 12,
            fontWeight: 400,
            color: "#7a6a60",
            margin: "0 0 clamp(16px, 3.5vw, 24px)",
            lineHeight: 1.55,
            maxWidth: 260,
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
            title="Previous Events"
            description="See events you've searched before."
            icon={
              <svg width="30" height="30" viewBox="0 0 36 36" fill="none" aria-hidden="true">
                <rect x="6" y="8" width="24" height="22" rx="4" stroke="#3a7abf" strokeWidth="2.3" />
                <path d="M12 6v4M24 6v4M6 16h24" stroke="#3a7abf" strokeWidth="2.2" strokeLinecap="round" />
                <path d="M12 22h12M12 26.5h7" stroke="#3a7abf" strokeWidth="2.1" strokeLinecap="round" />
              </svg>
            }
          />
        </div>

        {/* Footer */}
        <div style={{ marginTop: "clamp(20px, 5vw, 32px)", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "nowrap", gap: 12 }}>
          <button type="button" onClick={onEditAccessibility} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 0", border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="m14 5 5 5M4 20l4.5-1L20 7.5a3.2 3.2 0 0 0-4.5-4.5L4 14.5 3 21Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Edit Accessibility
          </button>
          <button type="button" onClick={() => onNavigate("intro")} style={{ padding: "4px 0", border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer", whiteSpace: "nowrap" }}>Log Out</button>
        </div>
      </div>

    </div>
  );
}

/* ── Drop Link View ── */
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
      {/* Back button — fixed to top-left of the screen */}
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
            style={{ background: "linear-gradient(135deg, #e8703a 0%, #c0392b 100%)", color: "#000000", border: "none", borderRadius: 12, padding: "12px 0", fontSize: 13, fontWeight: 700, cursor: "pointer", boxShadow: "0 10px 28px rgba(200,80,30,0.28)", letterSpacing: "0.01em", fontFamily: "inherit", transition: "opacity 0.2s, transform 0.15s" }}
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

type FlowFontSize = "small" | "default" | "large";

function AccessibilityPill({
  fontSize,
  setFontSize,
  speechText,
}: {
  fontSize: FlowFontSize;
  setFontSize: (size: FlowFontSize) => void;
  speechText?: string;
}) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    return () => {
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, []);

  function toggleSpeech() {
    if (!("speechSynthesis" in window)) return;
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    const visibleText = Array.from(
      document.querySelectorAll<HTMLElement>(
        "[data-accessibility-page] h1, [data-accessibility-page] h2, [data-accessibility-page] h3, [data-accessibility-page] p, [data-accessibility-page] label, [data-accessibility-page] button",
      ),
    )
      .filter((element) => {
        const style = window.getComputedStyle(element);
        return style.display !== "none" && style.visibility !== "hidden" && !element.closest("[aria-hidden='true']");
      })
      .map((element) => element.innerText.trim())
      .filter(Boolean)
      .join(". ");

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(speechText || visibleText);
    utterance.rate = 0.95;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }

  return (
    <div className="floating-accessibility">
      <div className={`intro-accessibility${speaking ? " accessibility-speaking" : ""}`} aria-label="Accessibility tools">
        <button
          type="button"
          aria-label="Adjust font size"
          aria-expanded={panelOpen}
          onClick={() => setPanelOpen((open) => !open)}
        >
          <span aria-hidden="true">Aa</span>
        </button>
        <span className="intro-control-divider" aria-hidden="true" />
        <button
          type="button"
          aria-label={speaking ? "Stop reading this page" : "Listen to this page"}
          aria-pressed={speaking}
          onClick={toggleSpeech}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 10v4h3l4 3V7L8 10H5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="M15 9.2a4 4 0 010 5.6M17.7 6.6a7.5 7.5 0 010 10.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      {panelOpen && (
        <div className="font-size-panel" role="group" aria-label="Choose font size">
          {([
            ["small", "A−"],
            ["default", "A"],
            ["large", "A+"],
          ] as const).map(([value, label]) => (
            <button
              type="button"
              className={fontSize === value ? "font-size-active" : ""}
              aria-pressed={fontSize === value}
              onClick={() => setFontSize(value)}
              key={value}
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function PostIntroShell({ children, speechText }: { children: React.ReactNode; speechText: string }) {
  const [fontSize, setFontSize] = useState<FlowFontSize>("default");

  return (
    <main className="setup-screen post-intro-screen" data-font-size={fontSize}>
      <FlowingBg zIndex={-1} />
      <AccessibilityPill fontSize={fontSize} setFontSize={setFontSize} speechText={speechText} />
      <div className="setup-scroll flow-scroll" data-accessibility-page>
        <div className="setup-header post-intro-header" aria-hidden="true" />
        {children}
      </div>
    </main>
  );
}

function AccessibleApplicationShell({ children }: { children: React.ReactNode }) {
  const [fontSize, setFontSize] = useState<FlowFontSize>("default");

  return (
    <div className="later-accessibility-frame" data-font-size={fontSize}>
      <AccessibilityPill fontSize={fontSize} setFontSize={setFontSize} />
      <div className="later-accessibility-content" data-accessibility-page>
        {children}
      </div>
    </div>
  );
}

function AccountProgress({ step, label }: { step: 1 | 3; label: string }) {
  return (
    <div className="setup-progress">
      <div className="setup-progress-label">
        <span>{label}</span>
        <strong>{step} of 3</strong>
      </div>
      <div
        className="setup-progress-track"
        role="progressbar"
        aria-label="Account setup progress"
        aria-valuemin={1}
        aria-valuemax={3}
        aria-valuenow={step}
      >
        <span className={`account-progress-step-${step}`} />
      </div>
    </div>
  );
}

function AuthChoiceScreen({ onLogin, onCreate }: { onLogin: () => void; onCreate: () => void }) {
  return (
    <PostIntroShell speechText="How would you like to continue? Choose an option to start discovering experiences without barriers. Log In. Create Account.">
      <section className="auth-choice" aria-labelledby="auth-title">
        <div className="auth-kicker">WELCOME</div>
        <h1 id="auth-title">How would you like to continue?</h1>
        <p>Choose an option to start discovering experiences without barriers.</p>
        <div className="auth-actions">
          <button className="flow-button flow-button-secondary" type="button" onClick={onLogin}>
            Log In
            <span aria-hidden="true">→</span>
          </button>
          <button className="flow-button flow-button-primary" type="button" onClick={onCreate}>
            Create Account
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </section>
    </PostIntroShell>
  );
}

type RegistrationDetails = { fullName: string; email: string; password: string; confirmPassword: string; accepted: boolean; termsOpen: boolean };

function BasicInformationScreen({ initialDetails, onContinue, onBack }: { initialDetails: RegistrationDetails; onContinue: (details: RegistrationDetails) => void; onBack: (details: RegistrationDetails) => void }) {
  const [fullName, setFullName] = useState(initialDetails.fullName);
  const [email, setEmail] = useState(initialDetails.email);
  const [password, setPassword] = useState(initialDetails.password);
  const [confirmPassword, setConfirmPassword] = useState(initialDetails.confirmPassword);
  const [accepted, setAccepted] = useState(initialDetails.accepted);
  const [termsOpen, setTermsOpen] = useState(initialDetails.termsOpen);
  const enabled = fullName.trim().length > 1 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && accepted && (!firebaseEnabled || (password.length >= 6 && password === confirmPassword));

  return (
    <PostIntroShell speechText="Step 1 of 3. Basic Information. Tell us about you. A few details to create your account. Full Name. Email Address. I agree to the Privacy Policy and Terms. Continue.">
      <section className="flow-panel" aria-labelledby="basic-title">
          <button type="button" onClick={() => onBack({ fullName, email, password, confirmPassword, accepted, termsOpen })} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 0", border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer" }}><span aria-hidden="true">←</span> Back</button>
          <AccountProgress step={1} label="Basic information" />
          <div className="setup-heading">
            <h1 id="basic-title">Tell us about you</h1>
            <p>A few details to create your account.</p>
          </div>
          <form
            className="flow-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (enabled) onContinue({ fullName, email, password, confirmPassword, accepted, termsOpen });
            }}
          >
            <label className="flow-field">
              <span>Full Name</span>
              <input
                type="text"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                autoComplete="name"
                placeholder="Your full name"
                required
              />
            </label>
            <label className="flow-field">
              <span>Email Address</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                placeholder="you@example.com"
                required
              />
            </label>
            {email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && <p className="flow-status" role="alert">Enter a valid email address.</p>}
            {firebaseEnabled && <>
              <label className="flow-field"><span>Password</span><input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" minLength={6} required placeholder="At least 6 characters" /></label>
              {password.length > 0 && password.length < 6 && <p className="flow-status" role="alert">Password must contain at least 6 characters.</p>}
              <label className="flow-field"><span>Confirm Password</span><input type="password" value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={6} required placeholder="Re-enter your password" /></label>
              {confirmPassword && password !== confirmPassword && <p className="flow-status" role="alert">Passwords do not match.</p>}
            </>}
            <label className="flow-checkbox">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              <span className="flow-checkbox-mark" aria-hidden="true">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2.5 6.2 4.8 8.5 9.5 3.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <span>I agree to the Privacy Policy and Terms.</span>
            </label>
            <div className={`terms-accordion${termsOpen ? " terms-accordion-open" : ""}`}>
              <button
                className="terms-accordion-trigger"
                type="button"
                aria-expanded={termsOpen}
                aria-controls="account-terms-content"
                onClick={() => setTermsOpen((open) => !open)}
              >
                <span>Terms &amp; Conditions</span>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <path d="m4 5.5 3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <div className="terms-accordion-content" id="account-terms-content">
                <div>
                  <div className="terms-accordion-inner">
                    <p>ACCESSLY PRIVACY POLICY</p>
                    <p>Version: 1.0</p>
                    <p>Last Updated: 26 October 2026</p>
                    <p>1 Introduction</p>
                    <p>Accessly is an AI-powered accessibility assistant that helps users identify accessibility information for events and communicate accommodation requests to event organizers.</p>
                    <p>This Privacy Policy explains how Accessly collects, uses, stores, and protects personal data. Accessly is designed to handle personal data in accordance with the Saudi Personal Data Protection Law (PDPL) and its applicable Implementing Regulations.</p>
                    <p>By creating an account or using Accessly, you acknowledge the practices described in this Privacy Policy.</p>
                    <p>2 Personal Data We Collect</p>
                    <p>Depending on how you use Accessly, we may collect the following information:</p>
                    <p>Account Information:</p>
                    <p>• User ID</p>
                    <p>• Name</p>
                    <p>• Email address</p>
                    <p>• Preferred language</p>
                    <p>Accessibility Information:</p>
                    <p>• Accessibility needs and preferences selected by you</p>
                    <p>• Custom accessibility needs or additional information voluntarily provided by you</p>
                    <p>Accessibility information may include information related to health or disability and may therefore be treated as Sensitive Data where applicable under Saudi law.</p>
                    <p>Event Information:</p>
                    <p>• Event URL</p>
                    <p>• Event name</p>
                    <p>• Event date</p>
                    <p>• Event location</p>
                    <p>• Organizer name</p>
                    <p>• Organizer contact information, when available</p>
                    <p>• Saved event information and accessibility analysis results</p>
                    <p>Accessibility Request Information:</p>
                    <p>• Request ID</p>
                    <p>• Accessibility requirements included in a request</p>
                    <p>• Request status</p>
                    <p>• Date a request was created or sent</p>
                    <p>• Status of individual accessibility needs</p>
                    <p>• Relevant organizer responses</p>
                    <p>Authentication and Consent Information:</p>
                    <p>• Authentication identifiers generated through the login process</p>
                    <p>• Login and session information</p>
                    <p>• Privacy Policy and Terms acceptance status</p>
                    <p>• Consent date and related records</p>
                    <p>Technical and Service Information:</p>
                    <p>• Session identifiers</p>
                    <p>• Processing or job identifiers</p>
                    <p>• Basic usage information</p>
                    <p>• Technical information necessary to operate, secure, troubleshoot, and maintain the service</p>
                    <p>Accessly aims to collect only the personal data reasonably necessary for the purposes described in this Policy.</p>
                    <p>3 How We Collect Your Data</p>
                    <p>We collect personal data directly from you when you:</p>
                    <p>• Create an Accessly account</p>
                    <p>• Enter or update your accessibility needs and preferences</p>
                    <p>• Submit an event URL for accessibility analysis</p>
                    <p>• Save an analyzed event</p>
                    <p>• Create or manage an accessibility request</p>
                    <p>• Use Accessly’s login and authentication features</p>
                    <p>• Use other features of the service</p>
                    <p>Accessly may also obtain publicly available information from event webpages or information provided by event organizers when necessary to analyze event accessibility or process an accessibility request.</p>
                    <p>4 How We Use Your Data</p>
                    <p>Accessly may process personal data to:</p>
                    <p>• Create and manage your account</p>
                    <p>• Authenticate users and maintain secure sessions</p>
                    <p>• Save and retrieve your accessibility preferences</p>
                    <p>• Analyze accessibility information relating to events • Personalize event accessibility analysis based on your saved preferences</p>
                    <p>• Save events and previous accessibility analyses to your account</p>
                    <p>• Identify accessibility requirements relevant to an event</p>
                    <p>• Prepare accommodation requests for your review</p>
                    <p>• Send approved accommodation requests to event organizers</p>
                    <p>• Track accessibility requests and their statuses</p>
                    <p>• Process relevant responses from event organizers</p>
                    <p>• Provide and maintain Accessly’s AI-assisted features</p>
                    <p>• Protect the security and integrity of the service</p>
                    <p>• Troubleshoot technical issues</p>
                    <p>• Improve the reliability and functionality of Accessly</p>
                    <p>Accessly will not intentionally process personal data for purposes incompatible with those for which it was collected unless permitted under applicable law.</p>
                    <p>5 Legal Basis and Sensitive Data</p>
                    <p>Accessly processes personal data based on applicable legal bases under the PDPL, including consent where required.</p>
                    <p>Because accessibility information may reveal health-related information, some accessibility information may constitute Sensitive Data under applicable law.</p>
                    <p>Where Sensitive Data is processed, Accessly will apply the additional safeguards and requirements required by applicable law, including obtaining explicit consent where required.</p>
                    <p>You may update your accessibility preferences through your account.</p>
                    <p>6 Data Sharing and Service Providers</p>
                    <p>Accessly may use third-party service providers that are necessary to operate the service, including providers supporting:</p>
                    <p>• Cloud hosting and databases</p>
                    <p>• User authentication</p>
                    <p>• Artificial intelligence processing</p>
                    <p>• Event information retrieval</p>
                    <p>• Email delivery</p>
                    <p>• Technical infrastructure and security</p>
                    <p>These providers may process personal data only as necessary to provide their relevant services and subject to applicable legal and contractual requirements.</p>
                    <p>Accessly does not sell users’ personal data.</p>
                    <p>Where personal data is transferred or processed outside the Kingdom of Saudi Arabia, Accessly will handle such transfers in accordance with the applicable requirements of the PDPL and its Implementing Regulations.</p>
                    <p>7 Data Storage, Security, and Retention</p>
                    <p>Accessly uses technical and organizational measures intended to protect personal data from unauthorized access, misuse, alteration, loss, or disclosure.</p>
                    <p>User account information, accessibility preferences, saved events, and related service information may be stored in cloud-based systems used to operate Accessly.</p>
                    <p>Accessly retains personal data only for as long as reasonably necessary to provide the service, fulfill the purposes described in this Policy, resolve applicable requests, or comply with legal obligations.</p>
                    <p>When personal data is no longer required, it will be deleted, destroyed, or anonymized where appropriate and in accordance with applicable requirements.</p>
                    <p>8 Your Privacy Rights</p>
                    <p>Subject to applicable law and any relevant conditions or exceptions, you may have the right to:</p>
                    <p>• Be informed about how your personal data is processed</p>
                    <p>• Access your personal data</p>
                    <p>• Request a copy of your personal data</p>
                    <p>• Request correction, completion, or updating of inaccurate personal data</p>
                    <p>• Request destruction of personal data where permitted by law</p>
                    <p>• Withdraw consent where processing is based on consent</p>
                    <p>Withdrawing consent does not affect processing that was lawfully carried out before the withdrawal.</p>
                    <p>9 How to Exercise Your Rights</p>
                    <p>To ask a privacy question or exercise an applicable privacy right, contact Accessly at:</p>
                    <p>Email: accesslyai@gmail.com</p>
                    <p>We may request information reasonably necessary to verify your identity before fulfilling a request involving personal data.</p>
                    <p>10 Changes to This Privacy Policy</p>
                    <p>Accessly may update this Privacy Policy from time to time to reflect changes to the service, technology, or applicable requirements.</p>
                    <p>Material updates will be reflected by changing the Last Updated date displayed at the beginning of this Policy.</p>
                    <p>ACCESSLY TERMS &amp; CONDITIONS</p>
                    <p>Version: 1.0</p>
                    <p>Last Updated: 26 October 2026</p>
                    <p>1 Using Accessly. Accessly is an AI-powered accessibility assistant designed to help users understand accessibility information relating to events and communicate accommodation requests to event organizers.</p>
                    <p>By creating an account or using Accessly, you agree to these Terms &amp; Conditions.</p>
                    <p>You must use Accessly only for lawful and legitimate purposes.</p>
                    <p>2 Account and User Responsibilities</p>
                    <p>You are responsible for:</p>
                    <p>• Providing accurate information when using Accessly</p>
                    <p>• Keeping your email account and access to your account secure</p>
                    <p>• Reviewing your accessibility preferences and keeping them up to date</p>
                    <p>• Reviewing accommodation requests before approving them for submission</p>
                    <p>• Using Accessly only for legitimate accessibility-related purposes</p>
                    <p>• Not attempting to misuse, disrupt, reverse engineer, damage, or gain unauthorized access to Accessly or another user’s information</p>
                    <p>You are responsible for activity performed through your account.</p>
                    <p>3 AI-Generated and Event Information</p>
                    <p>Accessly uses artificial intelligence and information obtained from event pages and other relevant sources to assist with accessibility analysis.</p>
                    <p>AI-generated analysis may occasionally be incomplete, outdated, or inaccurate.</p>
                    <p>Accessly does not guarantee that every accessibility feature identified by the service is currently available at an event.</p>
                    <p>Users should review important information and, where appropriate, confirm accessibility arrangements directly with the relevant event organizer before relying on them.</p>
                    <p>4 Accessibility and Accommodation Requests</p>
                    <p>Accessly may assist users in preparing and communicating accommodation requests to event organizers.</p>
                    <p>Before a request is sent, the user must review and approve the request where the service provides an approval step.</p>
                    <p>Accessly does not control event organizers and cannot guarantee that:</p>
                    <p>• An organizer will respond to a request</p>
                    <p>• A requested accommodation will be available</p>
                    <p>• An organizer will approve or provide a requested accommodation</p>
                    <p>• Event information will remain unchanged</p>
                    <p>The final decision regarding accommodations remains with the relevant event organizer.</p>
                    <p>5 Saved Events and Previous Analyses</p>
                    <p>Accessly may allow users to save analyzed events and view previous event analyses through their account.</p>
                    <p>Saved analyses represent the information available at the time the analysis was performed. Event details or accessibility arrangements may change after an event has been analyzed.</p>
                    <p>Accessly may therefore require or recommend a new analysis when updated information is needed.</p>
                    <p>6 Third-Party Services and Websites</p>
                    <p>Accessly may interact with or rely on third-party websites, platforms, cloud services, and other technology providers.</p>
                    <p>Accessly does not control third-party services and is not responsible for their independent availability, content, privacy practices, security practices, or actions.</p>
                    <p>Links or references to third-party services do not constitute an endorsement of those services.</p>
                    <p>7 Service Availability and Changes</p>
                    <p>Accessly may periodically update, modify, maintain, suspend, or discontinue features when reasonably necessary for maintenance, security, technical development, legal compliance, or service improvement.</p>
                    <p>Accessly does not guarantee that the service will always be uninterrupted or error-free.</p>
                    <p>8 Privacy</p>
                    <p>Your use of Accessly is also subject to the Accessly Privacy Policy, which explains how personal data is collected, used, stored, and protected.</p>
                    <p>By creating an account, you should review and acknowledge both the Privacy Policy and these Terms &amp; Conditions.</p>
                    <p>9 Changes to These Terms</p>
                    <p>Accessly may update these Terms &amp; Conditions from time to time.</p>
                    <p>Changes will be reflected by updating the Last Updated date displayed at the beginning of these Terms.</p>
                    <p>Continued use of Accessly following an applicable update may be subject to the updated Terms.</p>
                    <p>10 Contact Us</p>
                    <p>For questions about these Terms &amp; Conditions or Accessly:</p>
                    <p>Email: accesslyai@gmail.com</p>
                  </div>
                </div>
              </div>
            </div>
            <button className="setup-continue flow-submit" type="submit" disabled={!enabled}>
              Continue
              <span aria-hidden="true">→</span>
            </button>
          </form>
      </section>
    </PostIntroShell>
  );
}

type LoginProps = { onBack: () => void; initialEmail?: string; initialCodeSent?: boolean; onAuthenticated: (email: string) => Promise<void>; initialError?: string };
function LoginScreen(props: LoginProps) {
  return firebaseEnabled ? <PasswordLoginScreen {...props}/> : <LegacyLoginScreen {...props}/>;
}
function PasswordLoginScreen({ onBack, initialEmail = "", onAuthenticated, initialError = "" }: LoginProps) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError);
  const [notice, setNotice] = useState("");
  const inFlight = useRef(false);
  const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  async function submit(forgot = false) {
    if (inFlight.current) return;
    setError(""); setNotice("");
    if (!validEmail) { setError("Enter a valid email address."); return; }
    if (!forgot && !password) { setError("Enter your password."); return; }
    inFlight.current = true; setBusy(true);
    try {
      if (forgot) {
        await resetPassword(email);
        setNotice("If this email has an account, Firebase will send password reset instructions. Existing accounts without a password can use this to set one.");
      } else {
        await loginWithPassword(email, password);
        clearConversations(); setPassword("");
        await onAuthenticated(email);
      }
    } catch (failure) { setError(authErrorMessage(failure)); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <PostIntroShell speechText="Welcome back. Log in with your email address and password. Forgot password?">
    <section className="flow-panel flow-panel-compact" aria-labelledby="login-title">
      <button type="button" onClick={onBack} disabled={busy} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 0", border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer" }}><span aria-hidden="true">←</span> Back</button>
      <div className="auth-kicker">WELCOME BACK</div>
      <div className="setup-heading"><h1 id="login-title">Log in</h1><p>Enter your email and password to continue.</p></div>
      <form className="flow-form" onSubmit={event => { event.preventDefault(); void submit(); }}>
        <label className="flow-field"><span>Email Address</span><input type="email" value={email} onChange={event => { setEmail(event.target.value); setError(""); setNotice(""); }} autoComplete="email" placeholder="you@example.com" required disabled={busy}/></label>
        {email && !validEmail && <p className="flow-status" role="alert">Enter a valid email address.</p>}
        <label className="flow-field"><span>Password</span><input type="password" value={password} onChange={event => { setPassword(event.target.value); setError(""); }} autoComplete="current-password" placeholder="Your password" required disabled={busy}/></label>
        <button className="setup-continue flow-submit" type="submit" disabled={busy}>{busy ? "Please wait…" : "Login"}<span aria-hidden="true">→</span></button>
        <button type="button" onClick={() => void submit(true)} disabled={busy} style={{ padding: "4px 0", border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer", alignSelf: "flex-start" }}>Forgot password?</button>
        {error && <p className="flow-status" role="alert">{error}</p>}
        {notice && <p className="flow-status" role="status">{notice}</p>}
      </form>
    </section>
  </PostIntroShell>;
}

function LegacyLoginScreen({ onBack, initialEmail = "", initialCodeSent = false, onAuthenticated, initialError = "" }: { onBack: () => void; initialEmail?: string; initialCodeSent?: boolean; onAuthenticated: (email: string) => Promise<void>; initialError?: string }) {
  const [email, setEmail] = useState(initialEmail);
  const [codeSent, setCodeSent] = useState(initialCodeSent);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError);
  const [verified, setVerified] = useState(false);
  const inFlight = useRef(false);

  async function submit() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setError("");
    try {
      if (!codeSent) {
        await api("/auth/send-otp", "POST", { email });
        setCodeSent(true);
      } else {
        if (!verified) {
          const result = await api<{ access_token: string }>("/auth/verify-otp", "POST", { email, code });
          setAccessToken(result.access_token);
          setVerified(true);
        }
        await onAuthenticated(email);
      }
    } catch (failure) { setError((failure as Error).message); }
    finally { inFlight.current = false; setBusy(false); }
  }
  const enabled = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  return (
    <PostIntroShell speechText={`Welcome back. Log in. We’ll email you a secure code to continue. Email Address. Send Login Code.${codeSent ? " Check your email." : ""}`}>
      <section className="flow-panel flow-panel-compact" aria-labelledby="login-title">
        <button type="button" onClick={onBack} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 0", border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer" }}><span aria-hidden="true">←</span> Back</button>
        <div className="auth-kicker">WELCOME BACK</div>
        <div className="setup-heading">
          <h1 id="login-title">Log in</h1>
          <p>We’ll email you a secure code to continue.</p>
        </div>
          <form
            className="flow-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (enabled) void submit();
            }}
          >
            <label className="flow-field">
              <span>Email Address</span>
              <input
                type="email"
                disabled={busy || verified}
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setCodeSent(false); setCode(""); setVerified(false); setError("");
                }}
                autoComplete="email"
                placeholder="you@example.com"
                required
              />
            </label>
            {codeSent && !verified && <label className="flow-field">
              <span>Login code</span>
              <input type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} disabled={busy} onChange={(event) => setCode(event.target.value.replace(/[^0-9]/g, ""))} placeholder="6-digit code" />
            </label>}
            <button className="setup-continue flow-submit" type="submit" disabled={busy || !enabled || (codeSent && !verified && !/^[0-9]{6}$/.test(code))}>
              {busy ? "Please wait…" : verified ? "Continue" : codeSent ? "Verify Login Code" : "Send Login Code"}
              <span aria-hidden="true">→</span>
            </button>
            {codeSent && (
              <p className="flow-status" role="status">
                If this email is registered, a code was sent.
              </p>
            )}
            {codeSent && !verified && <button className="flow-button flow-button-secondary" type="button" disabled={busy} onClick={() => { setCodeSent(false); setCode(""); setError(""); }}>Request another code</button>}
            {error && <p className="flow-status" role="alert">{error}</p>}
          </form>
      </section>
    </PostIntroShell>
  );
}

function FinalSetupScreen({ needs, onCreate, onBack, initialReuse, busy, error }: { needs: string[]; onCreate: () => void; onBack: (reuse: boolean) => void; initialReuse: boolean; busy: boolean; error: string }) {
  const [reusePreferences, setReusePreferences] = useState(initialReuse);
  return (
    <PostIntroShell speechText={`Step 3 of 3. Final Setup. You’re almost there. Review your preferences before creating your account. Accessibility needs: ${needs.join(", ")}. Use my accessibility preferences for future event checks. Create Account.`}>
      <section className="flow-panel" aria-labelledby="final-title">
          <button type="button" onClick={() => onBack(reusePreferences)} disabled={busy} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 0", border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer" }}><span aria-hidden="true">←</span> Back</button>
          <AccountProgress step={3} label="Final setup" />
          <div className="setup-heading">
            <h1 id="final-title">You’re almost there</h1>
            <p>Review your preferences before creating your account.</p>
          </div>
          <div className="final-summary">
            <div className="final-summary-title">
              <span>Accessibility needs</span>
              <strong>{needs.length} selected</strong>
            </div>
            <ul>
              {needs.map((need) => (
                <li key={need}>
                  <span aria-hidden="true">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2.5 6.2 4.8 8.5 9.5 3.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                  {need}
                </li>
              ))}
            </ul>
          </div>
          <label className="flow-checkbox final-preference">
            <input
              type="checkbox"
              checked={reusePreferences}
              onChange={(event) => setReusePreferences(event.target.checked)}
            />
            <span className="flow-checkbox-mark" aria-hidden="true">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2.5 6.2 4.8 8.5 9.5 3.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span>Use my accessibility preferences for future event checks</span>
          </label>
          <button className="setup-continue flow-submit" type="button" onClick={onCreate} disabled={busy} aria-busy={busy}>
            {busy ? "Creating account…" : "Create Account"}
            <span aria-hidden="true">→</span>
          </button>
          {error && <p className="flow-status" role="alert">{error}</p>}
      </section>
    </PostIntroShell>
  );
}

/* ── Shared chip button for accessibility options ── */
function ChipBtn({ opt, on, onToggle }: { opt: typeof A11Y_OPTIONS[0]; on: boolean; onToggle: (id: string) => void }) {
  return (
    <button
      type="button"
      className={`setup-option${on ? " setup-option-selected" : ""}`}
      onClick={() => onToggle(opt.id)}
      aria-pressed={on}
    >
      <span className="setup-option-icon" aria-hidden="true">
        {opt.icon}
      </span>
      <span className="setup-option-label">{opt.label}</span>
      <span className="setup-option-check" aria-hidden="true">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 6.2 4.8 8.5 9.5 3.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </button>
  );
}

/* ── Accessibility Setup Screen ── */
function AccessibilitySetupScreen({ onContinue, initialNeeds = [], onCancel, onBack, busy = false, error = "" }: { onContinue: (needs: string[]) => void; initialNeeds?: string[]; onCancel?: () => void; onBack?: (needs: string[]) => void; busy?: boolean; error?: string }) {
  const [selected, setSelected] = useState<Set<string>>(() => new Set(initialNeeds.map((need) => A11Y_OPTIONS.find((option) => option.id !== "other" && option.label === need)?.id ?? "other")));
  const [otherText, setOtherText] = useState(() => initialNeeds.filter((need) => !A11Y_OPTIONS.some((option) => option.id !== "other" && option.label === need)).map((need) => need === "Other" ? "" : need.startsWith("Other: ") ? need.slice(7) : need).join("; "));
  const [ctaPressed, setCtaPressed] = useState(false);
  function toggle(id: string) {
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

  const otherOnly = selected.size === 1 && selected.has("other");
  const enabled = selected.size > 0 && !(otherOnly && !otherText.trim());

  return (
    <PostIntroShell
      speechText={`${onCancel ? "Edit accessibility." : "Step 2 of 3."} Accessibility needs. What do you need? Select all that apply. ${A11Y_OPTIONS.map((option) => option.label).join(". ")}. ${selected.has("other") ? "Tell us what you need. " : ""}Continue.`}
    >
      <section className="setup-content" aria-labelledby="setup-title">
          {onBack && <button type="button" onClick={() => onBack(Array.from(selected).map((id) => {
            const label = A11Y_OPTIONS.find((option) => option.id === id)?.label ?? id;
            return id === "other" ? `${label}: ${otherText}` : label;
          }))} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 0", border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer" }}><span aria-hidden="true">←</span> Back</button>}
          {!onCancel && <div className="setup-progress">
            <div className="setup-progress-label">
              <span>Accessibility needs</span>
              <strong>2 of 3</strong>
            </div>
            <div
              className="setup-progress-track"
              role="progressbar"
              aria-label="Account setup progress"
              aria-valuemin={1}
              aria-valuemax={3}
              aria-valuenow={2}
            >
              <span />
            </div>
          </div>}

          <div className="setup-heading">
            <h1 id="setup-title">What do you need?</h1>
            <p>Select all that apply.</p>
          </div>

          <div className="setup-grid" role="group" aria-label="Accessibility preferences">
            {[0, 2, 4, 6, 1, 3, 5, 7, 8, 9, 10].map((i) => {
              const opt = A11Y_OPTIONS[i];
              return <ChipBtn key={opt.id} opt={opt} on={selected.has(opt.id)} onToggle={toggle} />;
            })}
          </div>

          {selected.has("other") && (
            <div className="setup-other">
              <label htmlFor="other-accessibility-need">Tell us what you need</label>
              <input
                id="other-accessibility-need"
                type="text"
                autoFocus
                value={otherText}
                onChange={(e) => setOtherText(e.target.value)}
                placeholder="Tell us what you need"
                maxLength={120}
              />
            </div>
          )}

          <button
            className="setup-continue"
            type="button"
            onClick={() => {
              const needs = Array.from(selected).map((id) => {
                const label = A11Y_OPTIONS.find((option) => option.id === id)?.label ?? id;
                return id === "other" && otherText.trim() ? `${label}: ${otherText.trim()}` : label;
              });
              onContinue(needs);
            }}
            onMouseDown={() => { if (enabled) setCtaPressed(true); }}
            onMouseUp={() => setCtaPressed(false)}
            onMouseLeave={() => setCtaPressed(false)}
            onTouchStart={() => { if (enabled) setCtaPressed(true); }}
            onTouchEnd={() => setCtaPressed(false)}
            disabled={!enabled || busy}
            aria-label="Continue to the next step"
            style={{ transform: ctaPressed && enabled ? "scale(0.985)" : "scale(1)" }}
          >
            Continue
            <span aria-hidden="true">→</span>
          </button>
          {error && <p className="flow-status" role="alert">{error}</p>}
          {onCancel && <button type="button" onClick={onCancel} disabled={busy} style={{ display: "block", margin: "8px auto 0", padding: 8, border: "none", background: "transparent", color: "#292421", fontSize: 12, fontFamily: "inherit", cursor: "pointer" }}>Cancel</button>}
      </section>
    </PostIntroShell>
  );
}

const INTRO_PHOTO_COLUMNS = [
  [
    {
      src: studentProjectsExpo,
      alt: "King Saud University academic conference audience",
      height: 310,
    },
    {
      src: teamDesignExpo,
      alt: "KFUPM student design exhibition",
      height: 220,
    },
    {
      src: eventRegistration,
      alt: "Attendees registering for the KAUST STEAM Innovation Challenge",
      height: 270,
    },
  ],
  [
    {
      src: academicPanel,
      alt: "Attendees at the KAUST Women in Science and Engineering panel discussion",
      height: 230,
    },
    {
      src: steamChallenge,
      alt: "Students collaborating at the KAUST STEAM Innovation Challenge",
      height: 300,
    },
    {
      src: wheelchairCampusApproach,
      alt: "Wheelchair user seen from behind approaching an academic building along an outdoor campus path",
      height: 250,
    },
  ],
  [
    {
      src: modernCampus,
      alt: "Modern KAUST academic buildings and landscaped campus spaces",
      height: 255,
    },
    {
      src: teamDesignExpo,
      alt: "KFUPM student design exhibition",
      height: 310,
    },
    {
      src: wheelchairWomanEntrance,
      alt: "Saudi woman in a black abaya and hijab seen from behind using a wheelchair toward an academic event entrance",
      height: 225,
    },
  ],
  [
    {
      src: academicNetworking,
      alt: "Researchers networking between sessions at the KAUST WISE workshop",
      height: 245,
    },
    {
      src: inclusiveWorkshop,
      alt: "Saudi workshop participants using wheelchairs seated together at conference tables",
      height: 300,
    },
    {
      src: signLanguageForum,
      alt: "Live sign-language interpretation supporting attendees at a Riyadh cultural forum",
      height: 240,
    },
  ],
];

/* ── Intro Screen ── */
function IntroScreen({ onEnter }: { onEnter: () => void }) {
  const [pressed, setPressed] = useState(false);

  return (
    <main className="intro-hero">
      <div className="intro-photo-wall" aria-hidden="true">
        {INTRO_PHOTO_COLUMNS.map((photos, columnIndex) => (
          <div
            className={`intro-photo-column ${columnIndex % 2 === 0 ? "intro-photo-column-up" : "intro-photo-column-down"}`}
            style={{ animationDuration: `${38 + columnIndex * 6}s` }}
            key={columnIndex}
          >
            {[0, 1].map((setIndex) => (
              <div className="intro-photo-set" key={setIndex}>
                {photos.map((photo) => (
                  <img
                    src={photo.src}
                    alt=""
                    loading="eager"
                    draggable={false}
                    style={{ height: photo.height }}
                    key={photo.src}
                  />
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="intro-shade" aria-hidden="true" />

      <header className="intro-header">
        <div className="intro-wordmark" aria-label="Accessly">
          Accessly
        </div>
      </header>

      <section className="intro-content" aria-labelledby="intro-title">
        <p className="intro-eyebrow">EVENT ACCESSIBILITY CHECKER</p>
        <h1 id="intro-title">Paste an event link and check its <span>accessibility</span>.</h1>
        <button
          className="intro-cta"
          type="button"
          onClick={onEnter}
          onMouseDown={() => setPressed(true)}
          onMouseUp={() => setPressed(false)}
          onMouseLeave={() => setPressed(false)}
          onTouchStart={() => setPressed(true)}
          onTouchEnd={() => setPressed(false)}
          style={{ transform: pressed ? "scale(0.98)" : "scale(1)" }}
        >
          Start Checking
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <path d="M3.75 9h10.5M10.25 5l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </section>

      <p className="intro-footer-note">Events • Venues • Dining • Arts • Culture</p>
    </main>
  );
}

/* ── Root ── */
export default function App() {
  const [view, setView] = useState<View>("intro");
  const [agentUrl, setAgentUrl] = useState("");
  const [accessibilityNeeds, setAccessibilityNeeds] = useState<string[]>([]);
  const [editingAccessibility, setEditingAccessibility] = useState(false);
  const [registrationDetails, setRegistrationDetails] = useState<RegistrationDetails>({ fullName: "", email: "", password: "", confirmPassword: "", accepted: false, termsOpen: false });
  const [registrationNeeds, setRegistrationNeeds] = useState<string[] | null>(null);
  const [registrationReuse, setRegistrationReuse] = useState(true);

  const [authEmail, setAuthEmail] = useState("");
  const [loginRevision, setLoginRevision] = useState(0);
  const [codeRequested, setCodeRequested] = useState(false);
  const [recoveringProfile, setRecoveringProfile] = useState(false);
  const [pendingRegistration, setPendingRegistration] = useState(false);
  const [accountCreated, setAccountCreated] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const registrationCredential = useRef<{ email: string; uid: string } | null>(null);
  const accountInFlight = useRef(false);
  const profileInFlight = useRef(false);

  useEffect(() => {
    const requireLogin = () => {
      registrationCredential.current = null;
      endSession();
      setAgentUrl(""); setAccessibilityNeeds([]); setRegistrationNeeds(null);
      setEditingAccessibility(false); setPendingRegistration(false);
      setCodeRequested(false); setAuthEmail("");
      setLoginRevision((value) => value + 1);
      setAuthError("Your session expired. Log in to continue.");
      setView("login");
    };
    window.addEventListener("accessly:auth-required", requireLogin);
    return () => window.removeEventListener("accessly:auth-required", requireLogin);
  }, []);

  function navigate(next: View) {
    if (next === "intro") {
      endSession();
      setAgentUrl(""); setAccessibilityNeeds([]); setRegistrationNeeds(null);
      setRegistrationDetails({ fullName: "", email: "", password: "", confirmPassword: "", accepted: false, termsOpen: false });
      registrationCredential.current = null;
      setAccountCreated(false); setPendingRegistration(false); setCodeRequested(false);
      setAuthEmail(""); setAuthError(""); setEditingAccessibility(false); setRecoveringProfile(false);
    }
    setView(next);
  }

  async function createAccount() {
    if (accountInFlight.current) return;
    accountInFlight.current = true; setAuthBusy(true); setAuthError("");
    try {
      if (firebaseEnabled) {
        const email = registrationDetails.email.trim();
        if (!recoveringProfile && (registrationCredential.current?.email !== email || firebaseAuth().currentUser?.uid !== registrationCredential.current.uid)) {
          if (registrationDetails.password.length < 6) throw new Error("Password must contain at least 6 characters.");
          if (registrationDetails.password !== registrationDetails.confirmPassword) throw new Error("Passwords do not match.");
          const user = await createPasswordAccount(email, registrationDetails.password);
          registrationCredential.current = { email, uid: user.uid };
        }
        const needs = Array.from(new Set((registrationNeeds ?? accessibilityNeeds).map(need => need.trim()).filter(Boolean)));
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 30000);
        let profile: { name: string; needs: string[] };
        try {
          profile = await api<{ name: string; needs: string[] }>("/profile/complete", "POST", {
            name: registrationDetails.fullName.trim(), preferred_language: "en", consent: registrationDetails.accepted, needs,
          }, { signal: controller.signal, keepSession: true });
          if (!profile || !Array.isArray(profile.needs)) throw new Error("The profile save returned an invalid response.");
          // Finish a prior partial registration without creating another Auth user.
          if (profile.needs.length !== needs.length || needs.some(need => !profile.needs.includes(need))) {
            profile = await api<{ name: string; needs: string[] }>("/profile", "POST", { needs }, { signal: controller.signal, keepSession: true });
          }
          if (!profile?.needs?.length) throw new Error("Accessibility preferences were not saved.");
        } catch (failure) {
          throw new Error(controller.signal.aborted
            ? "Saving your profile timed out. Your account is still signed in. Press Create Account to retry saving."
            : `Your account is signed in, but registration could not finish. ${authErrorMessage(failure)} Press Create Account to retry.`);
        } finally { clearTimeout(timeout); }
        // Use the confirmed save response; no second profile read can block entry.
        try { clearConversations(); } catch { /* Optional browser storage must not block registration. */ }
        setAccessibilityNeeds(profile.needs); setRegistrationNeeds(profile.needs);
        setPendingRegistration(false); setAccountCreated(false); setRecoveringProfile(false);
        setEditingAccessibility(false); setAuthError("");
        setRegistrationDetails(details => ({ ...details, password: "", confirmPassword: "" }));
        setView("home");
        registrationCredential.current = null;
        return;
      }
      // PostgreSQL fallback retains its existing OTP flow.
      if (!accountCreated) {
        await api("/auth/register", "POST", { name: registrationDetails.fullName.trim(), email: registrationDetails.email.trim(), preferred_language: "en", consent: registrationDetails.accepted });
        setAccountCreated(true);
      }
      await api("/auth/send-otp", "POST", { email: registrationDetails.email.trim() });
      setAuthEmail(registrationDetails.email.trim()); setCodeRequested(true);
      setPendingRegistration(true); setView("login");
    } catch (failure) { setAuthError(authErrorMessage(failure)); }
    finally { accountInFlight.current = false; setAuthBusy(false); }
  }

  async function finishLogin(email: string) {
    if ((pendingRegistration || accountCreated) && email.trim().toLowerCase() === registrationDetails.email.trim().toLowerCase()) await api("/profile", "POST", { needs: registrationNeeds ?? accessibilityNeeds });
    let profile: { name: string; needs: string[] };
    try { profile = await api<{ name: string; needs: string[] }>("/profile"); }
    catch (failure) {
      if (firebaseEnabled && failure instanceof Error && failure.message === "User not found.") {
        setRecoveringProfile(true);
        setRegistrationDetails({ fullName: "", email, password: "", confirmPassword: "", accepted: false, termsOpen: false });
        setAccessibilityNeeds([]); setRegistrationNeeds(null); setView("basic"); return;
      }
      throw failure;
    }
    setAccessibilityNeeds(profile.needs); setRegistrationNeeds(profile.needs);
    setPendingRegistration(false); setAccountCreated(false); setAuthError("");
    // A previous partial signup can log in and complete preference setup.
    setEditingAccessibility(profile.needs.length === 0);
    setView(profile.needs.length ? "home" : "setup");
  }

  async function continuePreferences(needs: string[]) {
    if (!editingAccessibility) {
      setAccessibilityNeeds(needs); setRegistrationNeeds(needs); setView("final");
      return;
    }
    if (profileInFlight.current) return;
    profileInFlight.current = true; setProfileBusy(true); setProfileError("");
    try {
      await api("/profile", "POST", { needs });
      setAccessibilityNeeds(needs); setRegistrationNeeds(needs);
      setEditingAccessibility(false); setView("home");
    } catch (failure) { setProfileError((failure as Error).message); }
    finally { profileInFlight.current = false; setProfileBusy(false); }
  }

  if (view === "intro") return <IntroScreen onEnter={() => setView("auth")} />;
  if (view === "auth") return <AuthChoiceScreen onLogin={() => { setAuthError(""); setAuthEmail(""); setCodeRequested(false); setPendingRegistration(false); setView("login"); }} onCreate={() => { if (firebaseEnabled) endSession(); setRecoveringProfile(false); setView("basic"); }} />;
  if (view === "login") return <LoginScreen key={`${authEmail}:${loginRevision}`} initialEmail={authEmail} initialCodeSent={codeRequested} initialError={authError} onAuthenticated={finishLogin} onBack={() => setView("auth")} />;
  if (view === "basic") return <BasicInformationScreen initialDetails={registrationDetails} onBack={(details) => { setRegistrationDetails(details); setView("auth"); }} onContinue={(details) => { if (details.email !== registrationDetails.email) setAccountCreated(false); setRegistrationDetails(details); setView("setup"); }} />;
  if (view === "setup") {
    return (
      <AccessibilitySetupScreen
        initialNeeds={editingAccessibility ? accessibilityNeeds : registrationNeeds ?? accessibilityNeeds}
        onBack={editingAccessibility ? undefined : (needs) => { setRegistrationNeeds(needs); setView("basic"); }}
        onCancel={editingAccessibility ? () => { setEditingAccessibility(false); setView("home"); } : undefined}
        busy={profileBusy}
        error={profileError}
        onContinue={(needs) => void continuePreferences(needs)}
      />
    );
  }
  if (view === "final") return <FinalSetupScreen busy={authBusy} error={authError} needs={accessibilityNeeds} initialReuse={registrationReuse} onBack={(reuse) => { setRegistrationReuse(reuse); setView("setup"); }} onCreate={() => void createAccount()} />;

  return (
    <AccessibleApplicationShell>
      <div style={{ minHeight: "100%", position: "relative" }}>
        <FlowingBg />
        <div role="main" style={{ minHeight: "100%" }}>
          {view === "home" && <HomeView onNavigate={navigate} onEditAccessibility={() => { setProfileError(""); setEditingAccessibility(true); setView("setup"); }} />}
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
    </AccessibleApplicationShell>
  );
}