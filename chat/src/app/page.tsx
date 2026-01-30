"use client";

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown, { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// =============================================================================
// Design Tokens — Light & Dark (per Ask AI Design System)
// =============================================================================

interface ColorTokens {
  bg: string;
  bgElevated: string;
  bgSubtle: string;
  border: string;
  text: string;
  textSecondary: string;
  textTertiary: string;
  accent: string;
  accentHover: string;
  link: string;
  codeBg: string;
  codeInlineBg: string;
  tableBorder: string;
  thColor: string;
  tdColor: string;
  inputBg: string;
  pillHoverBg: string;
  error: string;
  errorBg: string;
  chipSuccess: string;
  chipSuccessText: string;
}

const lightColors: ColorTokens = {
  bg: "#faf9f7",
  bgElevated: "#ffffff",
  bgSubtle: "#f0eeeb",
  border: "#e8e6e3",
  text: "#1a1a1a",
  textSecondary: "#6b6b6b",
  textTertiary: "#999999",
  accent: "#2a2a2a",
  accentHover: "#3a3a3a",
  link: "#0066ff",
  codeBg: "#f5f5f5",
  codeInlineBg: "#e8e8e8",
  tableBorder: "#e0e0e0",
  thColor: "#1a1a1a",
  tdColor: "#4a4a4a",
  inputBg: "rgba(0,0,0,0.05)",
  pillHoverBg: "#fff",
  error: "#ef4444",
  errorBg: "rgba(239,68,68,0.08)",
  chipSuccess: "#dcfce7",
  chipSuccessText: "#16a34a",
};

const darkColors: ColorTokens = {
  bg: "#0f0f0f",
  bgElevated: "#1a1a1a",
  bgSubtle: "#262626",
  border: "#2a2a2a",
  text: "#e5e5e5",
  textSecondary: "#888888",
  textTertiary: "#555555",
  accent: "#3a3a3a",
  accentHover: "#4a4a4a",
  link: "#6b9fff",
  codeBg: "#1a1a1a",
  codeInlineBg: "#2a2a2a",
  tableBorder: "#2a2a2a",
  thColor: "#e5e5e5",
  tdColor: "#b0b0b0",
  inputBg: "rgba(255,255,255,0.05)",
  pillHoverBg: "#1f1f1f",
  error: "#ef4444",
  errorBg: "rgba(239,68,68,0.08)",
  chipSuccess: "#0f2e1f",
  chipSuccessText: "#4ade80",
};

function getColors(dark: boolean): ColorTokens {
  return dark ? darkColors : lightColors;
}

// =============================================================================
// Theme Hook
// =============================================================================

function useTheme() {
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined") return true;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const toggle = useCallback(() => setDark((d) => !d), []);

  return { dark, toggle };
}

// =============================================================================
// Types
// =============================================================================

interface ActionTaken {
  tool: string;
  success: boolean;
  error: string | null;
}

interface Metrics {
  latency_ms: number;
  tokens_used: number;
}

interface DebugData {
  trajectory?: unknown[];
  metrics?: unknown;
  [key: string]: unknown;
}

interface AttachedFile {
  name: string;
  mime: string;
  base64: string;
  type: string;
}

interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  actions?: ActionTaken[];
  metrics?: Metrics;
  debugData?: DebugData;
  file?: { name: string; mime: string };
}

// =============================================================================
// Icons (inline SVG per spec)
// =============================================================================

function SparkleIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z" />
      <path d="M19 15l.5 1.5 1.5.5-1.5.5-.5 1.5-.5-1.5-1.5-.5 1.5-.5.5-1.5z" opacity={0.6} />
    </svg>
  );
}

function PaperclipIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

function SendIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  );
}

function TrashIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14z" />
    </svg>
  );
}

function LogoutIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}

function SunIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function MoonIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  );
}

function InfoIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  );
}

function ChevronIcon({ size = 12, open }: { size?: number; open: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        transition: "transform 0.2s",
        transform: open ? "rotate(90deg)" : "rotate(0deg)",
      }}
    >
      <path d="M9 18l6-6-6-6" />
    </svg>
  );
}

function CloseIcon({ size = 10 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}

function ImageIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <path d="M21 15l-5-5L5 21" />
    </svg>
  );
}

function FileIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
    </svg>
  );
}

// =============================================================================
// Helpers
// =============================================================================

function uuid(): string {
  return crypto.randomUUID();
}

function formatLatency(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

const IMAGE_EXTS = new Set(["jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico"]);
function isImageFile(name: string): boolean {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  return IMAGE_EXTS.has(ext);
}

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

// =============================================================================
// Markdown Components (dynamic per theme)
// =============================================================================

function useMdComponents(c: ColorTokens): Components {
  return useMemo<Components>(() => ({
    p: ({ children }) => (
      <p style={{ margin: "0 0 8px 0" }}>{children}</p>
    ),
    pre: ({ children }) => (
      <pre style={{
        background: c.codeBg,
        padding: 12,
        borderRadius: 8,
        overflow: "auto",
        margin: "8px 0",
        fontSize: 13,
      }}>{children}</pre>
    ),
    code: ({ children, className }) => {
      const isBlock = className?.includes("language-");
      if (isBlock) return <code style={{ fontSize: 13 }}>{children}</code>;
      return (
        <code style={{
          background: c.codeInlineBg,
          padding: "2px 6px",
          borderRadius: 4,
          fontSize: 13,
        }}>{children}</code>
      );
    },
    ul: ({ children }) => (
      <ul style={{ margin: "8px 0", paddingLeft: 20 }}>{children}</ul>
    ),
    ol: ({ children }) => (
      <ol style={{ margin: "8px 0", paddingLeft: 20 }}>{children}</ol>
    ),
    li: ({ children }) => (
      <li style={{ margin: "4px 0" }}>{children}</li>
    ),
    strong: ({ children }) => (
      <strong style={{ fontWeight: 600 }}>{children}</strong>
    ),
    a: ({ children, href }) => (
      <a href={href} target="_blank" rel="noopener noreferrer" style={{
        color: c.link,
        textDecoration: "underline",
      }}>{children}</a>
    ),
    table: ({ children }) => (
      <div style={{ overflowX: "auto", margin: "12px 0" }}>
        <table style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 13,
          border: `1px solid ${c.tableBorder}`,
          borderRadius: 6,
        }}>{children}</table>
      </div>
    ),
    thead: ({ children }) => (
      <thead style={{ background: c.codeBg }}>{children}</thead>
    ),
    tr: ({ children }) => (
      <tr style={{ borderBottom: `1px solid ${c.tableBorder}` }}>{children}</tr>
    ),
    th: ({ children }) => (
      <th style={{
        padding: "10px 12px",
        textAlign: "left" as const,
        fontWeight: 600,
        color: c.thColor,
        borderRight: `1px solid ${c.tableBorder}`,
      }}>{children}</th>
    ),
    td: ({ children }) => (
      <td style={{
        padding: "10px 12px",
        color: c.tdColor,
        borderRight: `1px solid ${c.tableBorder}`,
      }}>{children}</td>
    ),
  }), [c]);
}

// =============================================================================
// Loading Shimmer
// =============================================================================

const loadingMessages = [
  "Seu agente está pensando",
  "Analisando sua solicitação",
  "Preparando resposta",
  "Processando sua pergunta",
];

function LoadingShimmer({ c }: { c: ColorTokens }) {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    const t = setInterval(() => {
      setMsgIndex((i) => (i + 1) % loadingMessages.length);
    }, 2000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{
      display: "flex",
      justifyContent: "flex-start",
      marginBottom: 16,
      padding: "12px 16px",
    }}>
      <span style={{
        fontSize: 14,
        fontStyle: "italic",
        background: `linear-gradient(90deg, ${c.textTertiary}, ${c.textSecondary}, ${c.textTertiary})`,
        backgroundSize: "200% 100%",
        WebkitBackgroundClip: "text",
        WebkitTextFillColor: "transparent",
        backgroundClip: "text",
        animation: "shimmer 2s ease-in-out infinite",
      }}>
        {loadingMessages[msgIndex]}…
      </span>
    </div>
  );
}

// =============================================================================
// Suggestion Pills
// =============================================================================

const suggestions = [
  "Olá!",
  "O que você pode fazer?",
  "Me ajude com algo",
];

function SuggestionPills({ c, onSelect }: { c: ColorTokens; onSelect: (text: string) => void }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  return (
    <div style={{
      display: "flex",
      flexWrap: "wrap",
      gap: 8,
      justifyContent: "center",
      maxWidth: 320,
    }}>
      {suggestions.map((text, i) => (
        <button
          key={i}
          onClick={() => onSelect(text)}
          onMouseEnter={() => setHoveredIndex(i)}
          onMouseLeave={() => setHoveredIndex(null)}
          style={{
            padding: "10px 16px",
            fontSize: 13,
            color: c.text,
            background: hoveredIndex === i ? c.pillHoverBg : c.bgElevated,
            border: `1px solid ${hoveredIndex === i ? c.accent : c.border}`,
            borderRadius: 20,
            cursor: "pointer",
            transition: "all 0.15s",
            fontFamily: "inherit",
          }}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

// =============================================================================
// Debug Panel
// =============================================================================

function DebugField({ label, c, children, mono }: { label: string; c: ColorTokens; children: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: c.textTertiary, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 2 }}>
        {label}
      </div>
      <div style={{
        fontSize: 12,
        color: c.text,
        lineHeight: 1.5,
        ...(mono ? { fontFamily: "monospace", fontSize: 11, whiteSpace: "pre-wrap" as const, wordBreak: "break-all" as const } : {}),
      }}>
        {children}
      </div>
    </div>
  );
}

function StageLLMInfo({ llmCalls, c }: { llmCalls: Record<string, unknown>[]; c: ColorTokens }) {
  if (!llmCalls.length) return null;
  const call = llmCalls[0];
  return (
    <>
      {call.model && <DebugField label="Modelo" c={c}>{String(call.model)}</DebugField>}
      <DebugField label="Tokens" c={c}>
        {Number(call.input_tokens ?? 0)} input / {Number(call.output_tokens ?? 0)} output
      </DebugField>
    </>
  );
}

function StageDetail({ s, c }: { s: Record<string, unknown>; c: ColorTokens }) {
  const stageId = s.stage_id as string;
  const promptDebug = s.prompt_debug as Record<string, unknown> | undefined;
  const llmCalls = Array.isArray(s.llm_calls) ? s.llm_calls as Record<string, unknown>[] : [];
  const output = s.output as Record<string, unknown> | undefined;
  const errors = Array.isArray(s.errors) ? s.errors as string[] : [];
  const [showPrompt, setShowPrompt] = useState(false);

  const sectionStyle: React.CSSProperties = {
    padding: 12,
    borderRadius: 8,
    background: c.codeBg,
    marginTop: 8,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  };

  const divider: React.CSSProperties = {
    height: 1,
    background: c.border,
    margin: "2px 0",
  };

  const prompt = typeof promptDebug?.final_system_prompt_used === "string"
    ? promptDebug.final_system_prompt_used : null;

  if (stageId === "intent") {
    const stageVal = output?.stage as string | undefined;
    const toolCalls = Array.isArray(output?.tool_calls) ? output.tool_calls as string[] : [];
    const reasoning = output?.reasoning as string | undefined;

    return (
      <div style={sectionStyle}>
        <StageLLMInfo llmCalls={llmCalls} c={c} />
        <div style={divider} />
        <DebugField label="Output" c={c}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 2 }}>
            {stageVal && (
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 11, color: c.textTertiary, minWidth: 40 }}>stage:</span>
                <span style={{ padding: "1px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600, background: c.bgSubtle, color: c.text }}>{stageVal}</span>
              </div>
            )}
            <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
              <span style={{ fontSize: 11, color: c.textTertiary, minWidth: 40, paddingTop: 2 }}>tools:</span>
              {toolCalls.length > 0 ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {toolCalls.map((t, i) => (
                    <span key={i} style={{ padding: "2px 6px", borderRadius: 4, fontSize: 11, background: c.bgSubtle, color: c.textSecondary }}>{String(t)}</span>
                  ))}
                </div>
              ) : (
                <span style={{ fontSize: 11, color: c.textTertiary }}>nenhuma</span>
              )}
            </div>
            {reasoning && (
              <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
                <span style={{ fontSize: 11, color: c.textTertiary, minWidth: 40, paddingTop: 1 }}>razao:</span>
                <span style={{ fontSize: 11, color: c.text }}>{reasoning}</span>
              </div>
            )}
          </div>
        </DebugField>
        {prompt && (
          <>
            <div style={divider} />
            <button onClick={() => setShowPrompt(!showPrompt)} style={{
              background: "none", border: "none", cursor: "pointer", fontFamily: "inherit",
              fontSize: 11, color: c.textTertiary, textAlign: "left", padding: 0,
              display: "flex", alignItems: "center", gap: 4,
            }}>
              <ChevronIcon size={9} open={showPrompt} />
              System prompt
            </button>
            {showPrompt && (
              <pre style={{ fontSize: 10, lineHeight: 1.4, color: c.textSecondary, whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 200, overflow: "auto", margin: 0, padding: 8, borderRadius: 6, background: c.bgSubtle }}>
                {prompt}
              </pre>
            )}
          </>
        )}
      </div>
    );
  }

  if (stageId === "executor") {
    const toolsExecuted = Array.isArray(output?.tools_executed) ? output.tools_executed as Record<string, unknown>[] : [];
    const stateUpdated = output?.state_updated as boolean | undefined;

    return (
      <div style={sectionStyle}>
        <DebugField label="LLM calls" c={c}>0 (execucao deterministica)</DebugField>
        <div style={divider} />
        <DebugField label="Output" c={c}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 2 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
              <span style={{ fontSize: 11, color: c.textTertiary, minWidth: 80, paddingTop: 2 }}>tools exec:</span>
              {toolsExecuted.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  {toolsExecuted.map((t, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{
                        padding: "2px 6px", borderRadius: 4, fontSize: 11, fontWeight: 500,
                        background: t.success ? c.chipSuccess : c.errorBg,
                        color: t.success ? c.chipSuccessText : c.error,
                      }}>
                        {t.success ? "✓" : "✗"} {String(t.tool)}
                      </span>
                      {typeof t.error === "string" && t.error && (
                        <span style={{ fontSize: 11, color: c.error }}>{t.error}</span>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <span style={{ fontSize: 11, color: c.textTertiary }}>nenhuma</span>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 11, color: c.textTertiary, minWidth: 80 }}>state updated:</span>
              <span style={{ fontSize: 11, color: c.text }}>{stateUpdated ? "sim" : "nao"}</span>
            </div>
          </div>
        </DebugField>
      </div>
    );
  }

  if (stageId === "writer") {
    const msg = output?.message as string | undefined;
    const stageVal = typeof promptDebug?.state_value === "string" ? promptDebug.state_value : null;

    return (
      <div style={sectionStyle}>
        <StageLLMInfo llmCalls={llmCalls} c={c} />
        {stageVal && (
          <DebugField label="Stage do prompt" c={c}>
            <span style={{ padding: "1px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600, background: c.bgSubtle, color: c.text }}>{stageVal}</span>
          </DebugField>
        )}
        <div style={divider} />
        <DebugField label="Output" c={c}>
          {msg ? (
            <div style={{ fontSize: 12, color: c.text, lineHeight: 1.5, maxHeight: 120, overflow: "auto" }}>{msg}</div>
          ) : (
            <span style={{ fontSize: 11, color: c.textTertiary }}>(vazio)</span>
          )}
        </DebugField>
        {prompt && (
          <>
            <div style={divider} />
            <button onClick={() => setShowPrompt(!showPrompt)} style={{
              background: "none", border: "none", cursor: "pointer", fontFamily: "inherit",
              fontSize: 11, color: c.textTertiary, textAlign: "left", padding: 0,
              display: "flex", alignItems: "center", gap: 4,
            }}>
              <ChevronIcon size={9} open={showPrompt} />
              System prompt completo
            </button>
            {showPrompt && (
              <pre style={{ fontSize: 10, lineHeight: 1.4, color: c.textSecondary, whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 250, overflow: "auto", margin: 0, padding: 8, borderRadius: 6, background: c.bgSubtle }}>
                {prompt}
              </pre>
            )}
          </>
        )}
      </div>
    );
  }

  // Fallback for unknown stages
  return (
    <div style={sectionStyle}>
      {llmCalls.length > 0 && llmCalls.map((call, i) => (
        <DebugField key={i} label={`LLM Call ${i + 1}`} c={c}>
          {String(call.model)} — {Number(call.input_tokens ?? 0)} in / {Number(call.output_tokens ?? 0)} out
        </DebugField>
      ))}
      {output != null && <DebugField label="Output" c={c} mono>{JSON.stringify(output, null, 2)}</DebugField>}
      {prompt && <DebugField label="System prompt" c={c} mono>{prompt}</DebugField>}
      {errors.length > 0 && <DebugField label="Erros" c={c}>{errors.join(", ")}</DebugField>}
    </div>
  );
}

function DebugModal({ data, c, onClose }: { data: DebugData; c: ColorTokens; onClose: () => void }) {
  const [expandedStages, setExpandedStages] = useState<Set<number>>(new Set());
  const [viewMode, setViewMode] = useState<"structured" | "json">("structured");

  const toggleStage = (idx: number) => {
    setExpandedStages((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const trajectory = Array.isArray(data.trajectory) ? data.trajectory : [];
  const metrics = data.metrics as Record<string, unknown> | undefined;

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const tabStyle = (active: boolean): React.CSSProperties => ({
    padding: "4px 10px",
    fontSize: 11,
    fontWeight: 500,
    fontFamily: "inherit",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    color: active ? c.text : c.textTertiary,
    background: active ? c.bgSubtle : "transparent",
    transition: "all 0.15s",
  });

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 9999,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        animation: "fade-in 0.15s ease-out both",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 600,
          maxHeight: "85vh",
          borderRadius: 14,
          background: c.bgElevated,
          border: `1px solid ${c.border}`,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          animation: "modal-in 0.2s cubic-bezier(0.16,1,0.3,1) both",
          boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
        }}
      >
        {/* Header */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 18px",
          borderBottom: `1px solid ${c.border}`,
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: c.text }}>Run Debug</span>
            <div style={{ display: "flex", alignItems: "center", gap: 2, padding: 2, borderRadius: 8, background: c.codeBg }}>
              <button onClick={() => setViewMode("structured")} style={tabStyle(viewMode === "structured")}>
                Estruturado
              </button>
              <button onClick={() => setViewMode("json")} style={tabStyle(viewMode === "json")}>
                JSON
              </button>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              border: "none",
              background: "transparent",
              color: c.textSecondary,
              cursor: "pointer",
              fontSize: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "inherit",
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ overflow: "auto", padding: 18, fontSize: 12, lineHeight: 1.5, color: c.textSecondary }}>
          {viewMode === "json" ? (
            <pre style={{
              margin: 0,
              overflow: "auto",
              fontSize: 11,
              lineHeight: 1.4,
              color: c.textSecondary,
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              fontFamily: "monospace",
              padding: 12,
              borderRadius: 8,
              background: c.codeBg,
            }}>
              {JSON.stringify(data, null, 2)}
            </pre>
          ) : (
            <>
              {/* Metrics summary */}
              {metrics && (
                <div style={{
                  marginBottom: trajectory.length ? 16 : 0,
                  padding: 12,
                  borderRadius: 8,
                  background: c.codeBg,
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 16,
                }}>
                  {typeof metrics.total_latency_ms === "number" && (
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 600, color: c.textTertiary, textTransform: "uppercase", letterSpacing: "0.05em" }}>Latencia total</div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: c.text, marginTop: 2 }}>{formatLatency(metrics.total_latency_ms as number)}</div>
                    </div>
                  )}
                  {typeof metrics.total_tokens === "object" && metrics.total_tokens !== null && (() => {
                    const t = metrics.total_tokens as Record<string, number>;
                    return (
                      <div>
                        <div style={{ fontSize: 10, fontWeight: 600, color: c.textTertiary, textTransform: "uppercase", letterSpacing: "0.05em" }}>Tokens</div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: c.text, marginTop: 2 }}>{t.input ?? 0} in / {t.output ?? 0} out</div>
                      </div>
                    );
                  })()}
                  {typeof metrics.llm_calls === "number" && (
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 600, color: c.textTertiary, textTransform: "uppercase", letterSpacing: "0.05em" }}>LLM calls</div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: c.text, marginTop: 2 }}>{metrics.llm_calls as number}</div>
                    </div>
                  )}
                </div>
              )}

              {/* Trajectory stages */}
              {trajectory.map((stage: unknown, idx: number) => {
                const s = stage as Record<string, unknown>;
                const isExpanded = expandedStages.has(idx);
                return (
                  <div key={idx} style={{ marginTop: idx === 0 ? 0 : 8 }}>
                    <button
                      onClick={() => toggleStage(idx)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        width: "100%",
                        padding: "8px 0",
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        fontFamily: "inherit",
                        fontSize: 12,
                        color: c.text,
                        textAlign: "left",
                        borderTop: idx > 0 ? `1px solid ${c.border}` : "none",
                      }}
                    >
                      <ChevronIcon size={11} open={isExpanded} />
                      <span style={{ fontSize: 11, fontWeight: 700, color: c.textSecondary, minWidth: 16 }}>{(s.sequence as number) ?? idx + 1}.</span>
                      <span style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        background: s.type === "executor" ? c.chipSuccess : c.bgSubtle,
                        color: s.type === "executor" ? c.chipSuccessText : c.textSecondary,
                      }}>
                        {(s.stage_id as string) || `Stage ${idx + 1}`}
                      </span>
                      <span style={{ color: c.textTertiary, fontSize: 11 }}>
                        {s.type as string}
                      </span>
                      {typeof s.latency_ms === "number" && (
                        <span style={{ marginLeft: "auto", color: c.textTertiary, fontSize: 11, fontVariantNumeric: "tabular-nums" }}>
                          {formatLatency(s.latency_ms as number)}
                        </span>
                      )}
                    </button>

                    {isExpanded && <StageDetail s={s} c={c} />}
                  </div>
                );
              })}

              {/* Fallback: raw JSON if no trajectory */}
              {!trajectory.length && !metrics && (
                <pre style={{
                  margin: 0,
                  overflow: "auto",
                  fontSize: 11,
                  lineHeight: 1.4,
                  color: c.textSecondary,
                  maxHeight: 400,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-all",
                }}>
                  {JSON.stringify(data, null, 2)}
                </pre>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Chat Message
// =============================================================================

function ChatMessage({ msg, c, mdComponents }: { msg: Message; c: ColorTokens; mdComponents: Components }) {
  const isUser = msg.role === "user";
  const [showDebug, setShowDebug] = useState(false);

  return (
    <div style={{ animation: "msg-in 0.28s ease-out both" }}>
      {/* Bubble */}
      <div style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: 16,
      }}>
        <div style={{
          maxWidth: isUser ? "88%" : "100%",
          width: isUser ? "auto" : "100%",
          padding: "12px 16px",
          borderRadius: isUser ? "18px 18px 4px 18px" : "8px",
          fontSize: 14,
          lineHeight: 1.6,
          background: isUser ? c.accent : "transparent",
          color: isUser ? "#ffffff" : c.text,
          wordBreak: "break-word" as const,
        }}>
          {isUser ? (
            <div>
              {msg.file && (
                <div style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  background: "rgba(255, 255, 255, 0.15)",
                  borderRadius: 8,
                  fontSize: 12,
                  marginBottom: msg.content ? 6 : 0,
                }}>
                  {isImageFile(msg.file.name) ? <ImageIcon size={14} /> : <FileIcon size={14} />}
                  {msg.file.name}
                </div>
              )}
              {msg.content && <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>}
            </div>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
              {msg.content}
            </ReactMarkdown>
          )}
        </div>
      </div>

      {/* Tool chips + debug button */}
      {!isUser && (msg.actions?.length || msg.debugData) && (
        <div style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 6,
          padding: "0 16px",
          marginTop: -8,
          marginBottom: 16,
        }}>
          {msg.actions?.map((a, i) => (
            <span key={i} style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "3px 8px",
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 500,
              background: a.success ? c.chipSuccess : c.errorBg,
              color: a.success ? c.chipSuccessText : c.error,
            }}>
              <span style={{ opacity: 0.7 }}>{a.success ? "✓" : "✗"}</span>
              {a.tool}
            </span>
          ))}
          {msg.debugData && (
            <button
              onClick={() => setShowDebug(true)}
              style={{
                marginLeft: "auto",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "3px 8px",
                borderRadius: 6,
                fontSize: 11,
                color: c.textTertiary,
                background: "transparent",
                border: `1px solid ${c.border}`,
                cursor: "pointer",
                fontFamily: "inherit",
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = c.textSecondary;
                e.currentTarget.style.borderColor = c.textTertiary;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = c.textTertiary;
                e.currentTarget.style.borderColor = c.border;
              }}
            >
              <InfoIcon size={12} />
              Debug
            </button>
          )}
        </div>
      )}

      {/* Debug modal (portal to body) */}
      {showDebug && msg.debugData && createPortal(
        <DebugModal data={msg.debugData} c={c} onClose={() => setShowDebug(false)} />,
        document.body,
      )}
    </div>
  );
}

// =============================================================================
// Login Screen
// =============================================================================

function LoginScreen({ c, dark, onToggleTheme, onLogin }: {
  c: ColorTokens;
  dark: boolean;
  onToggleTheme: () => void;
  onLogin: (token: string) => void;
}) {
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hovered, setHovered] = useState(false);
  const [themeBtnHover, setThemeBtnHover] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(
        `${API}/auth/login?username=${encodeURIComponent(user)}&password=${encodeURIComponent(pass)}`,
        { method: "POST" }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Erro ${res.status}`);
      }
      const data = await res.json();
      onLogin(data.access_token);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao conectar");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "12px 16px",
    fontSize: 14,
    color: c.text,
    background: c.inputBg,
    border: `1px solid ${c.border}`,
    borderRadius: 12,
    outline: "none",
    fontFamily: "inherit",
    transition: "border-color 0.15s",
  };

  return (
    <div style={{
      display: "flex",
      minHeight: "100dvh",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
      background: c.bg,
      transition: "background 0.3s",
    }}>
      {/* Theme toggle — top right */}
      <button
        onClick={onToggleTheme}
        onMouseEnter={() => setThemeBtnHover(true)}
        onMouseLeave={() => setThemeBtnHover(false)}
        style={{
          position: "fixed",
          top: 16,
          right: 16,
          width: 36,
          height: 36,
          borderRadius: 10,
          border: "none",
          background: themeBtnHover ? c.bgSubtle : "transparent",
          color: themeBtnHover ? c.text : c.textSecondary,
          cursor: "pointer",
          transition: "background 0.15s, color 0.15s",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        title={dark ? "Modo claro" : "Modo escuro"}
      >
        {dark ? <SunIcon size={16} /> : <MoonIcon size={16} />}
      </button>

      <form
        onSubmit={handleSubmit}
        style={{
          width: "100%",
          maxWidth: 360,
          animation: "login-in 0.5s cubic-bezier(0.16,1,0.3,1) both",
        }}
      >
        <div style={{
          padding: 32,
          borderRadius: 16,
          border: `1px solid ${c.border}`,
          background: c.bgElevated,
          transition: "background 0.3s, border-color 0.3s",
        }}>
          {/* Avatar + Brand */}
          <div style={{ textAlign: "center", marginBottom: 32 }}>
            <div style={{
              width: 40,
              height: 40,
              borderRadius: "50%",
              background: "linear-gradient(180deg, #ffffff 0%, #4a4a4a 100%)",
              margin: "0 auto 12px",
            }} />
            <h1 style={{
              fontSize: 18,
              fontWeight: 500,
              color: c.text,
              letterSpacing: "-0.02em",
            }}>
              Agent Chat
            </h1>
            <p style={{
              fontSize: 14,
              color: c.textSecondary,
              marginTop: 4,
            }}>
              Interface de teste
            </p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <input
              ref={inputRef}
              type="text"
              placeholder="Usuário"
              value={user}
              onChange={(e) => setUser(e.target.value)}
              required
              style={inputStyle}
              onFocus={(e) => e.target.style.borderColor = c.textTertiary}
              onBlur={(e) => e.target.style.borderColor = c.border}
            />
            <input
              type="password"
              placeholder="Senha"
              value={pass}
              onChange={(e) => setPass(e.target.value)}
              required
              style={inputStyle}
              onFocus={(e) => e.target.style.borderColor = c.textTertiary}
              onBlur={(e) => e.target.style.borderColor = c.border}
            />
          </div>

          {error && (
            <div style={{
              marginTop: 12,
              padding: "8px 12px",
              borderRadius: 8,
              background: c.errorBg,
              color: c.error,
              fontSize: 12,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
              marginTop: 20,
              width: "100%",
              padding: "12px 16px",
              fontSize: 14,
              fontWeight: 500,
              fontFamily: "inherit",
              color: "#ffffff",
              background: hovered ? c.accentHover : c.accent,
              border: "none",
              borderRadius: 12,
              cursor: loading ? "default" : "pointer",
              opacity: loading ? 0.5 : 1,
              transition: "all 0.15s",
            }}
          >
            {loading ? "Conectando…" : "Entrar"}
          </button>
        </div>
      </form>
    </div>
  );
}

// =============================================================================
// Chat Screen
// =============================================================================

function ChatScreen({ token, dark, c, onToggleTheme }: {
  token: string;
  dark: boolean;
  c: ColorTokens;
  onToggleTheme: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null);
  const conversationId = useRef(uuid());
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [headerHover, setHeaderHover] = useState<string | null>(null);
  const mdComponents = useMdComponents(c);

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 200);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, loading]);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_FILE_SIZE) {
      alert("Arquivo excede o limite de 5MB.");
      e.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const base64 = dataUrl.split(",")[1] || "";
      const mime = file.type || "application/octet-stream";
      let inputType = "document";
      if (mime.startsWith("image/")) inputType = "image";
      setAttachedFile({ name: file.name, mime, base64, type: inputType });
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  const sendMessage = useCallback(async (text: string) => {
    if ((!text.trim() && !attachedFile) || loading) return;

    const fileInfo = attachedFile ? { name: attachedFile.name, mime: attachedFile.mime } : undefined;
    const userMsg: Message = {
      id: uuid(),
      role: "user",
      content: text.trim(),
      file: fileInfo,
    };
    setMessages((prev) => [...prev, userMsg]);

    // Build input items
    const inputItems: { type: string; content: string; filename?: string; mime_type?: string }[] = [];
    if (attachedFile) {
      inputItems.push({
        type: attachedFile.type,
        content: attachedFile.base64,
        filename: attachedFile.name,
        mime_type: attachedFile.mime,
      });
    }
    if (text.trim()) {
      inputItems.push({ type: "text", content: text.trim() });
    }

    setInput("");
    setAttachedFile(null);
    setLoading(true);

    if (inputRef.current) {
      inputRef.current.style.height = "52px";
    }

    try {
      const res = await fetch(`${API}/run_debug`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          input: inputItems,
          conversation_id: conversationId.current,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Erro ${res.status}`);
      }

      const data = await res.json();
      const fo = data.final_output || {};

      // Extract debug data (trajectory + metrics from run_debug)
      const debugData: DebugData = {};
      if (data.trajectory) debugData.trajectory = data.trajectory;
      if (data.metrics) debugData.metrics = data.metrics;
      if (data.prompt_debug) debugData.prompt_debug = data.prompt_debug;

      setMessages((prev) => [...prev, {
        id: uuid(),
        role: "agent",
        content: fo.message || "(sem resposta)",
        actions: fo.actions_taken,
        metrics: data.metrics,
        debugData: Object.keys(debugData).length > 0 ? debugData : undefined,
      }]);
    } catch (err: unknown) {
      setMessages((prev) => [...prev, {
        id: uuid(),
        role: "agent",
        content: `**Erro:** ${err instanceof Error ? err.message : "Falha na comunicação"}`,
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [loading, token, attachedFile]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  function handleTextareaInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "52px";
    const newHeight = Math.min(Math.max(52, el.scrollHeight), 200);
    el.style.height = `${newHeight}px`;
  }

  function clearConversation() {
    setMessages([]);
    setInput("");
    conversationId.current = uuid();
  }

  const hasMessages = messages.length > 0;
  const canSend = (input.trim().length > 0 || !!attachedFile) && !loading;

  const headerBtn = (id: string): React.CSSProperties => ({
    width: 36,
    height: 36,
    borderRadius: 10,
    border: "none",
    background: headerHover === id ? c.bgSubtle : "transparent",
    color: headerHover === id ? c.text : c.textSecondary,
    cursor: "pointer",
    transition: "background 0.15s, color 0.15s",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  });

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100dvh",
      background: c.bg,
      fontFamily: "system-ui, -apple-system, sans-serif",
      transition: "background 0.3s",
    }}>
      {/* Header */}
      <div style={{
        borderBottom: `1px solid ${c.border}`,
        flexShrink: 0,
        padding: "16px 20px",
        transition: "border-color 0.3s",
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          maxWidth: 640,
          margin: "0 auto",
        }}>
          {/* Left: avatar + name */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: "linear-gradient(180deg, #ffffff 0%, #4a4a4a 100%)",
              flexShrink: 0,
            }} />
            <span style={{
              fontSize: 14,
              fontWeight: 500,
              color: c.text,
            }}>
              Agent
            </span>
          </div>

          {/* Right: buttons */}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            {hasMessages && (
              <button
                onClick={clearConversation}
                onMouseEnter={() => setHeaderHover("clear")}
                onMouseLeave={() => setHeaderHover(null)}
                style={headerBtn("clear")}
                title="Limpar conversa"
              >
                <TrashIcon size={16} />
              </button>
            )}
            <button
              onClick={onToggleTheme}
              onMouseEnter={() => setHeaderHover("theme")}
              onMouseLeave={() => setHeaderHover(null)}
              style={headerBtn("theme")}
              title={dark ? "Modo claro" : "Modo escuro"}
            >
              {dark ? <SunIcon size={16} /> : <MoonIcon size={16} />}
            </button>
          </div>
        </div>
      </div>

      {/* Messages / Empty State */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px 20px",
        }}
      >
        <div style={{ maxWidth: 640, margin: "0 auto" }}>
          {!hasMessages && !loading && (
            <div style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: "48px 24px",
              textAlign: "center",
              minHeight: "calc(100dvh - 220px)",
            }}>
              <SparkleIcon size={24} />
              <h2 style={{
                fontSize: 22,
                fontWeight: 500,
                color: c.text,
                marginTop: 16,
                marginBottom: 8,
                letterSpacing: "-0.02em",
              }}>
                Como posso ajudar?
              </h2>
              <p style={{
                fontSize: 14,
                color: c.textSecondary,
                marginBottom: 40,
                maxWidth: 260,
                lineHeight: 1.5,
              }}>
                Envie uma mensagem para começar a conversa
              </p>
              <SuggestionPills c={c} onSelect={(text) => sendMessage(text)} />
            </div>
          )}

          {messages.map((msg) => (
            <ChatMessage key={msg.id} msg={msg} c={c} mdComponents={mdComponents} />
          ))}

          {loading && <LoadingShimmer c={c} />}
        </div>
      </div>

      {/* Input Area */}
      <div style={{
        padding: "16px 20px 20px",
        borderTop: `1px solid ${c.border}`,
        background: c.bg,
        flexShrink: 0,
        transition: "background 0.3s, border-color 0.3s",
      }}>
        <div style={{ maxWidth: 640, margin: "0 auto" }}>
          {/* Attached file chip */}
          {attachedFile && (
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              marginBottom: 6,
              borderRadius: 12,
              background: dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
              border: `1px solid ${c.border}`,
              width: "fit-content",
            }}>
              {isImageFile(attachedFile.name) ? <ImageIcon size={14} /> : <FileIcon size={14} />}
              <span style={{ fontSize: 13, color: c.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 260 }}>
                {attachedFile.name}
              </span>
              <button
                onClick={() => setAttachedFile(null)}
                style={{
                  width: 18, height: 18, borderRadius: "50%", border: "none",
                  background: dark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)",
                  marginLeft: 4, cursor: "pointer",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: c.textSecondary,
                }}
              >
                <CloseIcon size={10} />
              </button>
            </div>
          )}
          <div style={{ position: "relative" }}>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,.pdf,.doc,.docx,.txt,.json,.csv"
              onChange={handleFileSelect}
              style={{ display: "none" }}
            />
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleTextareaInput}
              onKeyDown={handleKeyDown}
              placeholder="Pergunte algo..."
              disabled={loading}
              rows={1}
              style={{
                display: "block",
                width: "100%",
                margin: 0,
                padding: "16px 52px 16px 50px",
                fontSize: 14,
                lineHeight: 1.4,
                color: c.text,
                background: c.inputBg,
                border: "none",
                borderRadius: 24,
                outline: "none",
                resize: "none",
                fontFamily: "inherit",
                minHeight: 52,
                maxHeight: 200,
                boxSizing: "border-box",
                overflow: "auto",
              }}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              style={{
                position: "absolute",
                left: 10,
                bottom: 10,
                width: 32,
                height: 32,
                borderRadius: "50%",
                border: "none",
                background: attachedFile ? c.bgSubtle : "transparent",
                color: attachedFile ? c.text : c.textTertiary,
                cursor: "pointer",
                transition: "all 0.15s",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <PaperclipIcon size={16} />
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                sendMessage(input);
              }}
              disabled={!canSend}
              style={{
                position: "absolute",
                right: 10,
                bottom: 10,
                width: 32,
                height: 32,
                borderRadius: "50%",
                border: "none",
                background: c.inputBg,
                color: c.text,
                opacity: canSend ? 1 : 0.3,
                cursor: canSend ? "pointer" : "default",
                transition: "all 0.15s",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <SendIcon size={16} />
            </button>
          </div>
          <p style={{
            marginTop: 12,
            fontSize: 11,
            color: c.textTertiary,
            textAlign: "center",
            letterSpacing: "0.01em",
          }}>
            IA pode cometer erros. Verifique as respostas.
          </p>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Root
// =============================================================================

const AUTH_USER = process.env.NEXT_PUBLIC_AUTH_USER || "admin";
const AUTH_PASS = process.env.NEXT_PUBLIC_AUTH_PASS || "admin123";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const { dark, toggle } = useTheme();
  const c = getColors(dark);

  // Sync html background for scroll overscroll areas
  useEffect(() => {
    document.documentElement.style.background = c.bg;
  }, [c.bg]);

  // Auto-login on mount
  useEffect(() => {
    if (token) return;
    (async () => {
      try {
        const res = await fetch(
          `${API}/auth/login?username=${encodeURIComponent(AUTH_USER)}&password=${encodeURIComponent(AUTH_PASS)}`,
          { method: "POST" },
        );
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `Auth failed: ${res.status}`);
        }
        const data = await res.json();
        setToken(data.access_token);
      } catch (err: unknown) {
        setAuthError(err instanceof Error ? err.message : "Falha na autenticação");
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (authError) {
    return (
      <div style={{
        display: "flex",
        minHeight: "100dvh",
        alignItems: "center",
        justifyContent: "center",
        background: c.bg,
        color: c.error,
        fontSize: 14,
        padding: 24,
        textAlign: "center",
      }}>
        Erro de autenticação: {authError}
      </div>
    );
  }

  if (!token) {
    return (
      <div style={{
        display: "flex",
        minHeight: "100dvh",
        alignItems: "center",
        justifyContent: "center",
        background: c.bg,
        color: c.textSecondary,
        fontSize: 14,
      }}>
        Conectando...
      </div>
    );
  }

  return <ChatScreen token={token} dark={dark} c={c} onToggleTheme={toggle} />;
}
