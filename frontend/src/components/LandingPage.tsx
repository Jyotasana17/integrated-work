"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  Shield,
  Zap,
  ArrowRight,
  Terminal,
  Layers,
  Key,
  GitBranch,
  Cpu,
  Activity,
  Lock,
  BarChart3,
  Users,
  Code2,
  BookOpen,
  Moon,
  Sun,
  Github,
  Linkedin,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface LandingPageProps {
  onLaunch: () => void;
  onLogin: () => void;
}

interface TermLine {
  key: number;
  agent: string;
  method: string;
  endpoint: string;
  status: string;
  ok: boolean;
  time: string;
}

interface Engine {
  color: string;
  bgColor: string;
  borderColor: string;
  icon: React.ReactNode;
  title: string;
  desc: string;
}

interface Review {
  name: string;
  role: string;
  text: string;
  avatar: string;
}

// ─── Data ────────────────────────────────────────────────────────────────────

const LOG_POOL: Omit<TermLine, "key" | "time">[] = [
  { agent: "RoleSwapperAgent", method: "GET",    endpoint: "/api/v1/admin/dashboard",    status: "200", ok: true  },
  { agent: "ApiCrawler",       method: "POST",   endpoint: "/api/v1/auth/login",          status: "200", ok: true  },
  { agent: "ApiCrawler",       method: "PATCH",  endpoint: "/api/v1/admin/dashboard",    status: "200", ok: true  },
  { agent: "JwtAnalyzer",      method: "GET",    endpoint: "/api/v1/admin/dashboard",    status: "200", ok: true  },
  { agent: "RoleSwapperAgent", method: "PATCH",  endpoint: "/api/v1/items/bulk",         status: "200", ok: true  },
  { agent: "MutationEngine",   method: "POST",   endpoint: "/api/v1/users",              status: "403", ok: false },
  { agent: "EndpointCrawler",  method: "DELETE", endpoint: "/api/v1/admin/purge",        status: "401", ok: false },
  { agent: "JwtAnalyzer",      method: "GET",    endpoint: "/api/v1/reports/export",     status: "200", ok: true  },
  { agent: "RoleSwapperAgent", method: "PUT",    endpoint: "/api/v1/settings/global",    status: "200", ok: true  },
  { agent: "MutationEngine",   method: "GET",    endpoint: "/api/v1/billing/invoice",    status: "200", ok: true  },
];

const ENGINES: Engine[] = [
  {
    color: "#3b82f6", bgColor: "rgba(59,130,246,0.12)", borderColor: "rgba(59,130,246,0.25)",
    icon: <Layers className="w-5 h-5" />,
    title: "ENDPOINT DISCOVERY",
    desc: "Auto-parse Swagger/OpenAPI files to identify routes, authorization metadata, and request parameters.",
  },
  {
    color: "#8b5cf6", bgColor: "rgba(139,92,246,0.12)", borderColor: "rgba(139,92,246,0.25)",
    icon: <GitBranch className="w-5 h-5" />,
    title: "API SCHEMA CRAWLER",
    desc: "Traverse endpoint dependency trees to crawl inputs and reconstruct sequence transaction flows.",
  },
  {
    color: "#f59e0b", bgColor: "rgba(245,158,11,0.12)", borderColor: "rgba(245,158,11,0.25)",
    icon: <Cpu className="w-5 h-5" />,
    title: "MUTATION ENGINE",
    desc: "Node-powered parameter fuzzing, mutating headers, query strings, and payload IDs dynamically.",
  },
  {
    color: "#ef4444", bgColor: "rgba(239,68,68,0.12)", borderColor: "rgba(239,68,68,0.25)",
    icon: <Key className="w-5 h-5" />,
    title: "JWT TOKEN ANALYSIS",
    desc: "Deep inspections on cryptographic signing algorithms, signature strength, and expiration claims.",
  },
  {
    color: "#10b981", bgColor: "rgba(16,185,129,0.12)", borderColor: "rgba(16,185,129,0.25)",
    icon: <Users className="w-5 h-5" />,
    title: "ROLE & TENANT SWAP",
    desc: "Automated horizontal privilege escalation checks by swapping admin, user, and anonymous identity tokens.",
  },
  {
    color: "#06b6d4", bgColor: "rgba(6,182,212,0.12)", borderColor: "rgba(6,182,212,0.25)",
    icon: <Activity className="w-5 h-5" />,
    title: "TRAFFIC ANOMALY",
    desc: "Real-time behavioral baseline modeling to flag unusual request patterns, timing attacks, and bot signatures.",
  },
  {
    color: "#f97316", bgColor: "rgba(249,115,22,0.12)", borderColor: "rgba(249,115,22,0.25)",
    icon: <Shield className="w-5 h-5" />,
    title: "BOLA DETECTOR",
    desc: "Object-level authorization bypass testing across all resource IDs, cross-tenant data leakage included.",
  },
];

const REVIEWS: Review[] = [
  { name: "Alex Miller",  role: "Backend Lead",          text: "Saved us from a major credential stuffing attack on day two. Literally plug and play setup.",                                        avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&h=100&fit=crop&crop=faces" },
  { name: "Devon King",   role: "Security Architect",     text: "Minimalist configuration rules that actually deliver. The telemetry monitoring overhead is practically zero.",                        avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop&crop=faces" },
  { name: "Sarah Lin",    role: "CTO @ Nexus",            text: "Finally an SDK that doesn't bloat our runtime or dependencies tree. 10/10 layer.",                                                   avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop&crop=faces" },
  { name: "Jay Ram",      role: "Fullstack Engineer",     text: "The automatic DDoS traffic throttling kicked in flawlessly during our global traffic launch window.",                                 avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop&crop=faces" },
  { name: "Priya Mehta",  role: "DevSecOps @ Razorpay",  text: "BOLA detection flagged 3 critical bypasses in our legacy endpoints that had been live for 18 months.",                              avatar: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop&crop=faces" },
  { name: "Chris Park",   role: "Platform Eng @ Stripe",  text: "JWT token analysis alone was worth the migration. Our rotation hygiene improved dramatically in week one.",                          avatar: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop&crop=faces" },
];

const CODE: Record<string, React.ReactNode> = {
  node: (
    <div className="font-mono text-sm leading-6">
      <div><span className="text-purple-400">import</span> <span className="text-slate-200">{"{ Guardian }"}</span> <span className="text-purple-400">from</span> <span className="text-green-400">&apos;@apiguardian/node&apos;</span>;</div>
      <div><span className="text-purple-400">import</span> <span className="text-slate-200">express</span> <span className="text-purple-400">from</span> <span className="text-green-400">&apos;express&apos;</span>;</div>
      <div className="mt-3"><span className="text-purple-400">const</span> <span className="text-slate-200">a</span> = <span className="text-blue-400">express</span>();</div>
      <div><span className="text-purple-400">const</span> <span className="text-slate-200">g</span> = <span className="text-purple-400">new</span> <span className="text-blue-400">Guardian</span>(<span className="text-green-400">&apos;sk_live_123&apos;</span>);</div>
      <div className="mt-3 text-slate-500">{"// One line — full protection"}</div>
      <div>a.<span className="text-blue-400">use</span>(g.<span className="text-blue-400">protect</span>());</div>
      <div>a.<span className="text-blue-400">get</span>(<span className="text-green-400">&apos;/api&apos;</span>, (q, r) =&gt; r.<span className="text-blue-400">json</span>{"({ s: 'secure' })"});</div>
    </div>
  ),
  python: (
    <div className="font-mono text-sm leading-6">
      <div><span className="text-purple-400">from</span> <span className="text-slate-200">apiguardian</span> <span className="text-purple-400">import</span> <span className="text-slate-200">Guardian</span></div>
      <div><span className="text-purple-400">from</span> <span className="text-slate-200">flask</span> <span className="text-purple-400">import</span> <span className="text-slate-200">Flask</span></div>
      <div className="mt-3"><span className="text-yellow-300">a</span> = <span className="text-slate-200">Flask(__name__)</span></div>
      <div><span className="text-yellow-300">g</span> = <span className="text-slate-200">Guardian(</span><span className="text-green-400">&apos;sk_live_123&apos;</span><span className="text-slate-200">)</span></div>
      <div className="mt-3 text-slate-500">{"# One decorator — full protection"}</div>
      <div><span className="text-yellow-300">@a.before_request</span></div>
      <div><span className="text-purple-400">def</span> <span className="text-blue-400">p</span>(): <span className="text-yellow-300">g</span>.protect()</div>
    </div>
  ),
  cpp: (
    <div className="font-mono text-sm leading-6">
      <div><span className="text-purple-400">#include</span> <span className="text-green-400">&quot;apiguardian.h&quot;</span></div>
      <div><span className="text-purple-400">#include</span> <span className="text-green-400">&quot;crow.h&quot;</span></div>
      <div className="mt-3"><span className="text-purple-400">int</span> <span className="text-blue-400">main</span>() {"{"}</div>
      <div className="pl-5"><span className="text-yellow-300">crow::SimpleApp</span> a;</div>
      <div className="pl-5"><span className="text-yellow-300">Guardian</span> g(<span className="text-green-400">&apos;sk_live_123&apos;</span>);</div>
      <div className="pl-5 mt-2 text-slate-500">{"// One call — full protection"}</div>
      <div className="pl-5">a.route_dynamic(<span className="text-green-400">&quot;/api&quot;</span>)([&amp;g]() {"{"}</div>
      <div className="pl-10">g.protect(); <span className="text-purple-400">return</span> <span className="text-green-400">&quot;{`{\\"s\\":\\"ok\\"}`}&quot;</span>;</div>
      <div className="pl-5">{"});"}</div>
      <div>{"}"}</div>
    </div>
  ),
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmt12h(): string {
  const d = new Date();
  const hh = d.getHours(), mm = String(d.getMinutes()).padStart(2, "0"), ss = String(d.getSeconds()).padStart(2, "0");
  return `${((hh % 12) || 12)}:${mm}:${ss} ${hh >= 12 ? "PM" : "AM"}`;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function LandingPage({ onLaunch, onLogin }: LandingPageProps) {
  const [darkMode, setDarkMode]       = useState(true);
  const [activeLang, setActiveLang]   = useState<"node" | "python" | "cpp">("node");
  const [termLines, setTermLines]     = useState<TermLine[]>([]);
  const termRef                        = useRef<HTMLDivElement>(null);

  // ── live terminal log ──
  useEffect(() => {
    setTermLines(
      LOG_POOL.slice(0, 5).map((l, i) => ({ ...l, key: i, time: `7:12:0${4 + i} PM` }))
    );
    let idx = 5;
    const iv = setInterval(() => {
      const entry = LOG_POOL[idx % LOG_POOL.length];
      setTermLines((prev) => [...prev.slice(-7), { ...entry, key: idx, time: fmt12h() }]);
      idx++;
    }, 1400);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
  }, [termLines]);

  // ── theme tokens ──
  const d = darkMode;
  const bg        = d ? "#0b0f19" : "#f8fafc";
  const surface   = d ? "#1e293b" : "#ffffff";
  const surface2  = d ? "#0f172a" : "#f1f5f9";
  const border    = d ? "#1e293b" : "#e2e8f0";
  const borderMid = d ? "#334155" : "#cbd5e1";
  const t1        = d ? "#ffffff" : "#0f172a";
  const t2        = d ? "#94a3b8" : "#475569";
  const t3        = d ? "#475569" : "#94a3b8";
  const accent    = "#3b82f6";

  return (
    <div style={{ background: bg, color: t1, fontFamily: "Inter, -apple-system, sans-serif", lineHeight: 1.6, overflowX: "hidden", transition: "background .3s, color .3s", minHeight: "100vh" }}>

      {/* ── Global styles ── */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700;800;900&display=swap');
        .lp-h1,.lp-h2,.lp-h3{font-family:'Plus Jakarta Sans',sans-serif!important;letter-spacing:-.03em!important}
        @keyframes lp-up{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
        @keyframes lp-float{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}
        @keyframes lp-bar{from{width:0}to{width:85%}}
        @keyframes lp-pulse{0%,100%{opacity:1}50%{opacity:.35}}
        @keyframes lp-marquee{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
        @keyframes lp-fadein{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:none}}
        .lp-au1{animation:lp-up .55s cubic-bezier(.22,.68,0,1.2) both}
        .lp-au2{animation:lp-up .55s cubic-bezier(.22,.68,0,1.2) .1s both}
        .lp-au3{animation:lp-up .55s cubic-bezier(.22,.68,0,1.2) .2s both}
        .lp-au4{animation:lp-up .55s cubic-bezier(.22,.68,0,1.2) .3s both}
        .lp-float{animation:lp-float 7s ease-in-out infinite}
        .lp-progbar{animation:lp-bar 2.2s ease forwards}
        .lp-pulse{animation:lp-pulse 1.4s ease infinite}
        .lp-termrow{animation:lp-fadein .25s ease both}
        .lp-mq-track{display:flex;gap:24px;width:max-content;animation:lp-marquee 32s linear infinite}
        .lp-mq-wrap:hover .lp-mq-track{animation-play-state:paused}
        .lp-nav-link{color:${t2};text-decoration:none;font-size:.9rem;font-weight:500;transition:color .2s}
        .lp-nav-link:hover{color:${t1}}
        .lp-card-hover:hover{transform:translateY(-4px)!important;border-color:${accent}!important;box-shadow:0 12px 32px -8px rgba(59,130,246,.22)!important}
        .lp-engine-hover:hover{transform:translateY(-3px)!important;box-shadow:0 8px 24px -6px rgba(0,0,0,.3)!important}
        .lp-btn-p:hover{background:#2563eb!important;box-shadow:0 0 20px rgba(59,130,246,.4)!important}
        .lp-btn-o:hover{border-color:${t2}!important}
        .lp-footer-a{color:${t2};text-decoration:none;font-size:.85rem;transition:color .2s}
        .lp-footer-a:hover{color:${accent}}
        .lp-doc-a{color:${accent};text-decoration:none;font-weight:600;font-size:.9rem;transition:color .2s}
        .lp-doc-a:hover{color:#2563eb}
        .lp-li::before{content:"✓";color:${accent};font-weight:700;margin-right:8px}
        .lp-popular-card{border-color:${accent}!important;transform:scale(1.04)!important;z-index:2}
      `}</style>

      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px" }}>

        {/* ════════════ NAV ════════════ */}
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", position: "sticky", top: 0, zIndex: 50, background: `${bg}ee`, backdropFilter: "blur(12px)", borderBottom: `1px solid ${border}`, margin: "0 -24px", padding: "22px 24px" }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 800, fontSize: "1.25rem" }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(59,130,246,.12)", border: "1px solid rgba(59,130,246,.25)", display: "flex", alignItems: "center", justifyContent: "center", color: accent }}>
              <Shield size={18} />
            </div>
            <span style={{ color: t1 }}>TRUST</span><span style={{ color: accent }}>LAYER</span>
            <span style={{ fontSize: ".6rem", fontWeight: 800, letterSpacing: 1, background: "rgba(59,130,246,.12)", color: accent, border: "1px solid rgba(59,130,246,.2)", borderRadius: 8, padding: "2px 8px", marginLeft: 4 }}>SECURITY</span>
          </div>

          {/* Nav links */}
          <nav style={{ display: "flex", gap: 28 }}>
            {[["#lp-features","Features"],["#lp-engines","Engines"],["#lp-docs","Docs"],["#lp-pricing","Pricing"]].map(([href, label]) => (
              <a key={href} href={href} className="lp-nav-link">{label}</a>
            ))}
          </nav>

          {/* Actions */}
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <button
              onClick={() => setDarkMode(m => !m)}
              style={{ width: 38, height: 38, borderRadius: "50%", border: `1px solid ${borderMid}`, background: "transparent", color: t2, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", transition: "all .2s" }}
            >
              {darkMode ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button onClick={onLogin} style={{ padding: "8px 18px", borderRadius: 9, border: `1px solid ${borderMid}`, background: "transparent", color: t1, fontWeight: 600, fontSize: ".88rem", cursor: "pointer", transition: "all .2s" }} className="lp-btn-o">
              Sign In
            </button>
            <button onClick={onLaunch} className="lp-btn-p" style={{ padding: "8px 18px", borderRadius: 9, background: accent, color: "#fff", fontWeight: 700, fontSize: ".88rem", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, transition: "all .2s" }}>
              Launch Console <ArrowRight size={14} />
            </button>
          </div>
        </header>

        {/* ════════════ HERO ════════════ */}
        <main style={{ display: "flex", alignItems: "center", gap: 56, minHeight: "calc(100vh - 80px)", padding: "60px 0 56px" }}>

          {/* Left copy */}
          <div style={{ flex: 1, maxWidth: 580 }}>
            <div className="lp-au1" style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "6px 14px", background: "rgba(59,130,246,.1)", border: "1px solid rgba(59,130,246,.2)", borderRadius: 20, fontSize: ".78rem", fontWeight: 700, color: accent, marginBottom: 24, letterSpacing: .6, textTransform: "uppercase" }}>
              <Zap size={13} style={{ fill: accent }} />
              AI-Powered API Security Intelligence Platform
            </div>

            <h1 className="lp-h1 lp-au2" style={{ fontSize: "3.6rem", lineHeight: 1.08, fontWeight: 900, marginBottom: 20 }}>
              <span style={{ backgroundImage: d ? "linear-gradient(135deg,#fff 40%,#93c5fd)" : "linear-gradient(135deg,#0f172a 40%,#3b82f6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                Automated API{"\n"}
              </span>
              <span style={{ backgroundImage: "linear-gradient(90deg,#3b82f6,#8b5cf6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                Authorization Testing
              </span>
              <span style={{ backgroundImage: d ? "linear-gradient(135deg,#fff 40%,#93c5fd)" : "linear-gradient(135deg,#0f172a 40%,#3b82f6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text" }}>
                {"\n"}for Enterprise DevSecOps.
              </span>
            </h1>

            <p className="lp-au3" style={{ fontSize: "1.05rem", color: t2, marginBottom: 36, lineHeight: 1.75, maxWidth: 520 }}>
              Discover endpoints, crawl schemas, decode tokens, mutate parameter payloads, and swap roles autonomously in real time. Seal BOLA and privilege leaks before deployment.
            </p>

            <div className="lp-au4" style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              <button onClick={onLaunch} className="lp-btn-p" style={{ padding: "13px 26px", borderRadius: 11, background: accent, color: "#fff", fontWeight: 700, fontSize: "1rem", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 8, transition: "all .25s", boxShadow: "0 4px 24px -4px rgba(59,130,246,.4)" }}>
                Start Security Scan <ArrowRight size={16} />
              </button>
              <button onClick={onLogin} className="lp-btn-o" style={{ padding: "13px 26px", borderRadius: 11, border: `1px solid ${borderMid}`, background: "transparent", color: t1, fontWeight: 700, fontSize: "1rem", cursor: "pointer", transition: "all .25s" }}>
                Request API Key
              </button>
            </div>

            {/* Stats bar */}
            <div className="lp-au4" style={{ display: "flex", gap: 40, marginTop: 44, paddingTop: 32, borderTop: `1px solid ${border}` }}>
              {[
                { val: "100%",   label: "AUTONOMOUS DISCOVERY" },
                { val: "< 15ms", label: "TOKEN PARSING LATENCY" },
                { val: "P1–P4",  label: "DISTRIBUTED QUEUES" },
              ].map(s => (
                <div key={s.label}>
                  <div style={{ fontSize: "1.9rem", fontWeight: 900, color: t1, lineHeight: 1, fontVariantNumeric: "tabular-nums", letterSpacing: "-.04em" }}>{s.val}</div>
                  <div style={{ fontSize: ".65rem", fontWeight: 700, color: t2, letterSpacing: 1.2, textTransform: "uppercase", marginTop: 6 }}>{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: live security engine card */}
          <div style={{ flex: 1, maxWidth: 440, position: "relative" }}>
            <div style={{ position: "absolute", width: 280, height: 280, background: "#3b82f6", filter: "blur(130px)", borderRadius: "50%", opacity: .08, top: "50%", left: "50%", transform: "translate(-50%,-50%)", zIndex: 0, pointerEvents: "none" }} />

            <div className="lp-float" style={{ position: "relative", zIndex: 1, background: d ? "#0f172a" : "#ffffff", border: `1px solid ${border}`, borderRadius: 20, overflow: "hidden", boxShadow: "0 32px 72px -16px rgba(0,0,0,.55)" }}>

              {/* Window titlebar */}
              <div style={{ background: d ? "#1e293b" : "#f8fafc", padding: "12px 18px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: `1px solid ${border}` }}>
                <div style={{ display: "flex", gap: 7 }}>
                  {["#ef4444", "#f59e0b", "#10b981"].map(c => <div key={c} style={{ width: 11, height: 11, borderRadius: "50%", background: c }} />)}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: ".65rem", fontWeight: 800, color: t3, letterSpacing: .8, textTransform: "uppercase", fontFamily: "monospace" }}>
                  <Terminal size={11} />
                  SECURITY ENGINES
                </div>
              </div>

              <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 10 }}>

                {/* Engine row 1: ENDPOINT DISCOVERY */}
                <div style={{ background: d ? "#1e293b" : "#f8fafc", border: `1px solid ${border}`, borderRadius: 13, padding: "13px 15px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 32, height: 32, borderRadius: 9, background: "rgba(59,130,246,.12)", color: "#3b82f6", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(59,130,246,.2)" }}>
                        <Layers size={14} />
                      </div>
                      <span style={{ fontSize: ".7rem", fontWeight: 800, color: d ? "#e2e8f0" : "#0f172a", letterSpacing: .6, fontFamily: "monospace" }}>ENDPOINT DISCOVERY</span>
                    </div>
                    <span style={{ fontSize: ".62rem", fontWeight: 800, padding: "3px 10px", borderRadius: 20, background: "rgba(16,185,129,.12)", color: "#10b981", border: "1px solid rgba(16,185,129,.2)", letterSpacing: .4 }}>ACTIVE</span>
                  </div>
                  <div style={{ height: 3, background: d ? "#334155" : "#e2e8f0", borderRadius: 99, overflow: "hidden" }}>
                    <div className="lp-progbar" style={{ height: 3, background: "linear-gradient(90deg,#3b82f6,#8b5cf6)", borderRadius: 99 }} />
                  </div>
                </div>

                {/* Engine row 2: JWT */}
                <div style={{ background: d ? "#1e293b" : "#f8fafc", border: `1px solid ${border}`, borderRadius: 13, padding: "13px 15px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 32, height: 32, borderRadius: 9, background: "rgba(139,92,246,.12)", color: "#8b5cf6", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(139,92,246,.2)" }}>
                        <Key size={14} />
                      </div>
                      <span style={{ fontSize: ".7rem", fontWeight: 800, color: d ? "#e2e8f0" : "#0f172a", letterSpacing: .6, fontFamily: "monospace" }}>JWT DECODER & ANALYSIS</span>
                    </div>
                    <span style={{ fontSize: ".62rem", fontWeight: 800, padding: "3px 10px", borderRadius: 20, background: "rgba(245,158,11,.12)", color: "#f59e0b", border: "1px solid rgba(245,158,11,.2)", letterSpacing: .4 }}>ANALYZING</span>
                  </div>
                  <div style={{ fontFamily: "monospace", fontSize: ".6rem", color: t3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", background: d ? "#0f172a" : "#f1f5f9", padding: "6px 10px", borderRadius: 8, border: `1px solid ${border}` }}>
                    eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMiIsInJvbGUi…
                  </div>
                </div>

                {/* Engine row 3: ROLE SWAP */}
                <div style={{ background: d ? "#1e293b" : "#f8fafc", border: `1px solid ${border}`, borderRadius: 13, padding: "13px 15px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 32, height: 32, borderRadius: 9, background: "rgba(239,68,68,.12)", color: "#ef4444", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid rgba(239,68,68,.2)" }}>
                        <GitBranch size={14} />
                      </div>
                      <span style={{ fontSize: ".7rem", fontWeight: 800, color: d ? "#e2e8f0" : "#0f172a", letterSpacing: .6, fontFamily: "monospace" }}>ROLE & TENANT SWAPPING</span>
                    </div>
                    <span style={{ fontSize: ".62rem", fontWeight: 800, padding: "3px 10px", borderRadius: 20, background: "rgba(239,68,68,.12)", color: "#ef4444", border: "1px solid rgba(239,68,68,.2)", letterSpacing: .4 }}>9 CRITICAL CHECKS</span>
                  </div>
                  <div style={{ fontSize: ".7rem", color: t3, fontFamily: "monospace" }}>
                    Testing swap: <span style={{ color: "#f59e0b", fontWeight: 700 }}>admin</span>
                    <span style={{ margin: "0 7px", color: t3 }}>⇄</span>
                    <span style={{ color: t2, fontWeight: 600 }}>anonymous</span>
                  </div>
                </div>

                {/* Live terminal */}
                <div style={{ background: "#060d1a", border: "1px solid #1e293b", borderRadius: 13, overflow: "hidden" }}>
                  <div style={{ padding: "8px 14px", background: "#0a1628", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #1e293b" }}>
                    <span style={{ fontSize: ".58rem", fontWeight: 700, color: "#475569", letterSpacing: 1, textTransform: "uppercase", fontFamily: "monospace" }}>SIMULATED SCAN TRAFFIC LOG</span>
                    <div className="lp-pulse" style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981" }} />
                  </div>
                  <div ref={termRef} style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: ".6rem", height: 128, overflowY: "auto", scrollbarWidth: "none" }}>
                    {termLines.map((l, i) => (
                      <div key={l.key} className="lp-termrow" style={{ display: "flex", gap: 7, marginBottom: 4, alignItems: "flex-start", animationDelay: `${i * 0.04}s` }}>
                        <span style={{ color: "#475569", flexShrink: 0 }}>[{l.time}]</span>
                        <span style={{ color: "#3b82f6", flexShrink: 0 }}>{l.agent}</span>
                        <span style={{ color: "#94a3b8", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>-&gt; {l.method} {l.endpoint}</span>
                        <span style={{ fontWeight: 700, flexShrink: 0, color: l.ok ? "#10b981" : "#ef4444" }}>{l.status} {l.ok ? "✓" : "✗"}</span>
                      </div>
                    ))}
                    <div style={{ display: "flex", gap: 4, marginTop: 2 }}>
                      <span style={{ color: "#10b981" }}>▸</span>
                      <span className="lp-pulse" style={{ color: "#3b82f6" }}>_</span>
                    </div>
                  </div>
                </div>

              </div>
            </div>
          </div>
        </main>

        {/* ════════════ TRUSTED BY ════════════ */}
        <div style={{ textAlign: "center", padding: "36px 0", borderTop: `1px solid ${border}`, borderBottom: `1px solid ${border}` }}>
          <p style={{ color: t3, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: 1.4, marginBottom: 22, fontWeight: 700 }}>Securing endpoints for innovative teams worldwide</p>
          <div style={{ display: "flex", justifyContent: "center", gap: 48, flexWrap: "wrap", opacity: .35, filter: "grayscale(100%)" }}>
            {(["a","b","c","d","e"] as const).map((k) => (
              <svg key={k} viewBox="0 0 100 30" style={{ height: 24, fill: t1 }}>
                <rect width="100" height="20" rx="8" />
              </svg>
            ))}
          </div>
        </div>

        {/* ════════════ FEATURES ════════════ */}
        <section id="lp-features" style={{ padding: "80px 0" }}>
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <p style={{ color: accent, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: 1.6, fontWeight: 700, marginBottom: 10 }}>What We Do</p>
            <h2 className="lp-h2" style={{ fontSize: "2.4rem", fontWeight: 800, marginBottom: 14, color: t1 }}>Banish vulnerabilities instantly</h2>
            <p style={{ color: t2, fontSize: "1rem", maxWidth: 500, margin: "0 auto" }}>Everything you need to secure your backend, packed into one intuitive platform.</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 24 }}>
            {[
              { icon: <Shield size={22} />, title: "Real-Time Threat Shield", desc: "Automatically block DDoS attempts, SQL injections, and malicious bot traffic before they hit your database." },
              { icon: <BarChart3 size={22} />, title: "Deep Usage Analytics", desc: "Track request volumes, latency drops, and error rates across all your endpoints with our beautiful dashboard." },
              { icon: <Zap size={22} />, title: "5-Minute Integration", desc: "No complex configurations. Drop in our SDK, grab your API key, and your infrastructure is secured instantly." },
              { icon: <Users size={22} />, title: "Instant Team Alerts", desc: "Coordinate security squads during active breaches. Set role-based access limits and escalate threats via cross-team rooms." },
            ].map((f, i) => (
              <div key={i} className="lp-card-hover" style={{ background: surface, border: `1px solid ${border}`, borderRadius: 20, padding: "32px 28px", display: "flex", flexDirection: "column", gap: 16, transition: "all .25s", cursor: "default" }}>
                <div style={{ width: 46, height: 46, borderRadius: 12, background: "rgba(59,130,246,.1)", border: "1px solid rgba(59,130,246,.18)", display: "flex", alignItems: "center", justifyContent: "center", color: accent }}>
                  {f.icon}
                </div>
                <div>
                  <h3 className="lp-h3" style={{ fontSize: "1.1rem", fontWeight: 700, color: t1, marginBottom: 8 }}>{f.title}</h3>
                  <p style={{ color: t2, fontSize: ".9rem", lineHeight: 1.65 }}>{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ════════════ ENGINES ════════════ */}
        <section id="lp-engines" style={{ padding: "0 0 80px" }}>
          <div style={{ textAlign: "center", marginBottom: 52 }}>
            <p style={{ color: accent, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: 1.6, fontWeight: 700, marginBottom: 10 }}>Under the Hood</p>
            <h2 className="lp-h2" style={{ fontSize: "2.4rem", fontWeight: 800, marginBottom: 14, color: t1 }}>API Security Intelligence Engines</h2>
            <p style={{ color: t2, fontSize: "1rem", maxWidth: 560, margin: "0 auto" }}>
              Seven specialized core security engines cooperating asynchronously to identify authorization bypasses, token defects, and data leakage.
            </p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(230px,1fr))", gap: 18 }}>
            {ENGINES.map((e, i) => (
              <div key={i} className="lp-engine-hover" style={{ background: surface, border: `1px solid ${border}`, borderRadius: 18, padding: "26px 22px", display: "flex", flexDirection: "column", gap: 14, transition: "all .22s", cursor: "default", position: "relative", overflow: "hidden" }}>
                <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg,transparent,${e.color},transparent)` }} />
                <div style={{ width: 44, height: 44, borderRadius: 12, background: e.bgColor, color: e.color, display: "flex", alignItems: "center", justifyContent: "center", border: `1px solid ${e.borderColor}`, flexShrink: 0 }}>
                  {e.icon}
                </div>
                <div>
                  <div style={{ fontSize: ".68rem", fontWeight: 800, letterSpacing: 1, color: e.color, marginBottom: 7, fontFamily: "monospace", textTransform: "uppercase" }}>{e.title}</div>
                  <div style={{ fontSize: ".86rem", color: t2, lineHeight: 1.6 }}>{e.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ════════════ CODE SHOWCASE ════════════ */}
        <section style={{ padding: "0 0 80px" }}>
          <div style={{ background: surface, borderRadius: 24, border: `1px solid ${border}`, padding: "48px 52px", display: "flex", alignItems: "center", gap: 56, boxShadow: d ? "0 10px 40px -10px rgba(0,0,0,.4)" : "0 10px 40px -10px rgba(0,0,0,.06)" }}>
            <div style={{ flex: 1 }}>
              <p style={{ color: accent, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: 1.6, fontWeight: 700, marginBottom: 12 }}>Built for Developers</p>
              <h2 className="lp-h2" style={{ fontSize: "1.9rem", fontWeight: 800, marginBottom: 14, color: t1 }}>Wrap your API in two lines</h2>
              <p style={{ color: t2, marginBottom: 24, lineHeight: 1.75 }}>We know you hate complex setups. That&apos;s why API Guardian wraps around your existing code in literally two lines.</p>
              <button className="lp-btn-o" style={{ padding: "10px 22px", borderRadius: 10, border: `1px solid ${borderMid}`, background: "transparent", color: t1, fontWeight: 600, fontSize: ".9rem", cursor: "pointer", transition: "all .2s" }}>
                Read the Documentation
              </button>
            </div>
            <div style={{ flex: 1, background: "#0f172a", borderRadius: 14, border: "1px solid #1e293b", overflow: "hidden", boxShadow: "0 24px 48px -12px rgba(0,0,0,.5)" }}>
              <div style={{ background: "#1e293b", padding: "8px 16px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #334155" }}>
                <div style={{ display: "flex", gap: 7 }}>
                  {["#ef4444","#f59e0b","#10b981"].map((c, i) => <div key={i} style={{ width: 11, height: 11, borderRadius: "50%", background: c }} />)}
                </div>
                <div style={{ display: "flex", gap: 4 }}>
                  {(["node","python","cpp"] as const).map(l => (
                    <button key={l} onClick={() => setActiveLang(l)} style={{ background: activeLang === l ? "#0f172a" : "transparent", border: "none", color: activeLang === l ? accent : "#94a3b8", padding: "5px 12px", borderRadius: "6px 6px 0 0", fontSize: ".75rem", fontFamily: "monospace", cursor: "pointer", fontWeight: activeLang === l ? 700 : 400, transition: "all .2s" }}>
                      {l === "node" ? "Node.js" : l === "python" ? "Python" : "C++"}
                    </button>
                  ))}
                </div>
              </div>
              <div style={{ padding: 24, color: "#e2e8f0", minHeight: 200, overflowX: "auto" }}>
                {CODE[activeLang]}
              </div>
            </div>
          </div>
        </section>

        {/* ════════════ DOCS ════════════ */}
        <section id="lp-docs" style={{ padding: "0 0 80px" }}>
          <div style={{ textAlign: "center", marginBottom: 52 }}>
            <p style={{ color: accent, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: 1.6, fontWeight: 700, marginBottom: 10 }}>Learn Quickly</p>
            <h2 className="lp-h2" style={{ fontSize: "2.4rem", fontWeight: 800, marginBottom: 14, color: t1 }}>Documentation</h2>
            <p style={{ color: t2, fontSize: "1rem" }}>Everything you need to integrate and master API Guardian.</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 24 }}>
            {[
              { icon: <BookOpen size={22} />, title: "Getting Started", desc: "Learn how to integrate the API Guardian SDK into your application in under 5 minutes.", link: "Read Guide →" },
              { icon: <Code2 size={22} />, title: "API Reference", desc: "Detailed documentation of all endpoints, accepted parameters, and JSON responses.", link: "View API →" },
              { icon: <Lock size={22} />, title: "Authentication", desc: "Secure your requests properly using API keys, OAuth, and JWT tokens.", link: "Learn More →" },
            ].map((d2, i) => (
              <div key={i} className="lp-card-hover" style={{ background: surface, border: `1px solid ${border}`, borderRadius: 20, padding: "32px 28px", display: "flex", flexDirection: "column", gap: 16, transition: "all .25s" }}>
                <div style={{ width: 46, height: 46, borderRadius: 12, background: "rgba(59,130,246,.1)", border: "1px solid rgba(59,130,246,.18)", display: "flex", alignItems: "center", justifyContent: "center", color: accent }}>
                  {d2.icon}
                </div>
                <div style={{ flex: 1 }}>
                  <h3 className="lp-h3" style={{ fontSize: "1.1rem", fontWeight: 700, color: t1, marginBottom: 8 }}>{d2.title}</h3>
                  <p style={{ color: t2, fontSize: ".9rem", lineHeight: 1.65 }}>{d2.desc}</p>
                </div>
                <a href="#" className="lp-doc-a">{d2.link}</a>
              </div>
            ))}
          </div>
        </section>

        {/* ════════════ PRICING ════════════ */}
        <section id="lp-pricing" style={{ padding: "0 0 80px" }}>
          <div style={{ textAlign: "center", marginBottom: 52 }}>
            <p style={{ color: accent, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: 1.6, fontWeight: 700, marginBottom: 10 }}>Pricing</p>
            <h2 className="lp-h2" style={{ fontSize: "2.4rem", fontWeight: 800, marginBottom: 14, color: t1 }}>Simple, transparent pricing</h2>
            <p style={{ color: t2, fontSize: "1rem" }}>Scale securely without breaking the bank.</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 24, alignItems: "start" }}>
            {[
              { name: "Starter", price: "$0",     per: "/mo", desc: "For side projects and testing environments.",     features: ["100,000 API requests/mo","Basic DDoS protection","Community support","7-day log retention"],                                    cta: "Get Started",    primary: false, popular: false },
              { name: "Pro",     price: "$49",    per: "/mo", desc: "For growing startups and production APIs.",       features: ["10M API requests/mo","Advanced threat shield","Priority email support","30-day log retention","BOLA & role-swap testing"],  cta: "Start Free Trial", primary: true,  popular: true  },
              { name: "Enterprise", price: "Custom", per: "", desc: "For mission-critical infrastructure and scale.",  features: ["Unlimited API requests","Custom WAF rules","24/7 dedicated SLA","Infinite log retention","Custom engine modules"],           cta: "Contact Sales",  primary: false, popular: false },
            ].map((plan, i) => (
              <div key={i} className={plan.popular ? "lp-popular-card" : "lp-card-hover"} style={{ background: surface, border: `1px solid ${plan.popular ? accent : border}`, borderRadius: 22, padding: "36px 28px", display: "flex", flexDirection: "column", gap: 0, transition: "all .25s", position: "relative" }}>
                {plan.popular && (
                  <div style={{ position: "absolute", top: -1, left: "50%", transform: "translateX(-50%)", background: accent, color: "#fff", fontSize: ".65rem", fontWeight: 800, padding: "4px 16px", borderRadius: "0 0 10px 10px", letterSpacing: .8, textTransform: "uppercase" }}>Most Popular</div>
                )}
                <h3 className="lp-h3" style={{ fontSize: "1.15rem", fontWeight: 800, color: t1, marginBottom: 4 }}>{plan.name}</h3>
                <div style={{ fontSize: "2.8rem", fontWeight: 900, color: t1, lineHeight: 1, marginBottom: 8, fontVariantNumeric: "tabular-nums", letterSpacing: "-.04em" }}>
                  {plan.price}<span style={{ fontSize: "1rem", fontWeight: 400, color: t2 }}>{plan.per}</span>
                </div>
                <p style={{ color: t2, fontSize: ".88rem", marginBottom: 24 }}>{plan.desc}</p>
                <ul style={{ listStyle: "none", padding: 0, marginBottom: 28, flex: 1 }}>
                  {plan.features.map((f, j) => (
                    <li key={j} className="lp-li" style={{ color: t2, fontSize: ".88rem", marginBottom: 10 }}>{f}</li>
                  ))}
                </ul>
                <button onClick={plan.primary ? onLaunch : onLogin} className={plan.primary ? "lp-btn-p" : "lp-btn-o"} style={{ width: "100%", padding: "12px", borderRadius: 11, background: plan.primary ? accent : "transparent", color: plan.primary ? "#fff" : t1, border: plan.primary ? "none" : `1px solid ${borderMid}`, fontWeight: 700, fontSize: ".95rem", cursor: "pointer", transition: "all .25s" }}>
                  {plan.cta}
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* ════════════ REVIEWS MARQUEE ════════════ */}
        <section style={{ padding: "0 0 60px", overflow: "hidden" }}>
          <div style={{ textAlign: "center", marginBottom: 40 }}>
            <p style={{ color: accent, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: 1.6, fontWeight: 700, marginBottom: 8 }}>Developer Testimonials</p>
            <h2 className="lp-h2" style={{ fontSize: "2rem", fontWeight: 800, color: t1 }}>Approved by Engineers</h2>
          </div>
          <div className="lp-mq-wrap" style={{ width: "100%", overflow: "hidden", position: "relative", padding: "10px 0" }}>
            <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 80, background: `linear-gradient(to right, ${bg}, transparent)`, zIndex: 3, pointerEvents: "none" }} />
            <div style={{ position: "absolute", right: 0, top: 0, bottom: 0, width: 80, background: `linear-gradient(to left, ${bg}, transparent)`, zIndex: 3, pointerEvents: "none" }} />
            <div className="lp-mq-track">
              {[...REVIEWS, ...REVIEWS].map((r, i) => (
                <div key={i} style={{ background: surface, border: `1px solid ${border}`, borderRadius: 18, padding: "24px", width: 310, flexShrink: 0, display: "flex", flexDirection: "column", gap: 16 }}>
                  <p style={{ color: t2, fontSize: ".9rem", fontStyle: "italic", lineHeight: 1.6, margin: 0 }}>&ldquo;{r.text}&rdquo;</p>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <img src={r.avatar} alt={r.name} width={38} height={38} style={{ borderRadius: "50%", objectFit: "cover", border: `2px solid ${accent}` }} />
                    <div>
                      <div style={{ fontWeight: 700, fontSize: ".9rem", color: t1 }}>{r.name}</div>
                      <div style={{ fontSize: ".75rem", color: accent }}>{r.role}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ════════════ BOTTOM CTA ════════════ */}
        <section style={{ padding: "0 0 80px" }}>
          <div style={{ textAlign: "center", padding: "80px 32px", background: surface, borderRadius: 24, border: `1px solid ${border}`, position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: 360, height: 360, background: accent, filter: "blur(130px)", opacity: .06, borderRadius: "50%", pointerEvents: "none" }} />
            <p style={{ color: accent, fontSize: ".75rem", textTransform: "uppercase", letterSpacing: 1.6, fontWeight: 700, marginBottom: 14, position: "relative" }}>Ship with Confidence</p>
            <h2 className="lp-h2" style={{ fontSize: "2.8rem", fontWeight: 900, color: t1, marginBottom: 18, position: "relative" }}>Ready to exorcise your API demons?</h2>
            <p style={{ color: t2, fontSize: "1.05rem", maxWidth: 500, margin: "0 auto 36px", position: "relative", lineHeight: 1.7 }}>
              Join thousands of developers who sleep better at night knowing their backend is guarded by seven intelligent engines.
            </p>
            <button onClick={onLaunch} className="lp-btn-p" style={{ padding: "15px 36px", borderRadius: 12, background: accent, color: "#fff", fontWeight: 700, fontSize: "1.05rem", border: "none", cursor: "pointer", transition: "all .25s", boxShadow: "0 4px 24px -4px rgba(59,130,246,.45)", position: "relative" }}>
              Start Securing for Free
            </button>
          </div>
        </section>

      </div>

      {/* ════════════ FOOTER (full-width dark) ════════════ */}
      <footer style={{ background: "#020617", borderTop: "1px solid #1e293b", padding: "48px 24px 32px", color: "#94a3b8" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 36, marginBottom: 36 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 9, fontWeight: 800, fontSize: "1.1rem", color: "#ffffff" }}>
                <Shield size={18} color={accent} />
                TrustLayer Labs
              </div>
              <p style={{ fontSize: ".82rem", lineHeight: 1.65, color: "#64748b" }}>Real-time edge shield and telemetry monitoring built natively for development squads.</p>
            </div>
            {[
              { h: "Product",   links: ["Features","Integrations","Changelog"] },
              { h: "Resources", links: ["Documentation","API Reference","Status Page"] },
              { h: "Company",   links: ["About Us","Careers","Privacy & Policy"] },
            ].map(col => (
              <div key={col.h}>
                <h4 style={{ fontSize: ".85rem", fontWeight: 700, marginBottom: 16, color: "#ffffff" }}>{col.h}</h4>
                <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
                  {col.links.map(l => <a key={l} href="#" className="lp-footer-a">{l}</a>)}
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 20, borderTop: "1px solid #1e293b", flexWrap: "wrap", gap: 14 }}>
            <div style={{ fontSize: ".82rem" }}>© 2026 TrustLayer Labs. All rights reserved. Deployment Ready.</div>
            <div style={{ display: "flex", gap: 16 }}>
              <a href="#" className="lp-footer-a" style={{ display: "flex", alignItems: "center" }}><Github size={18} /></a>
              <a href="#" className="lp-footer-a" style={{ display: "flex", alignItems: "center" }}><Linkedin size={18} /></a>
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}
