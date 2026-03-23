import { useRef, useEffect } from "react";

interface ActionEntry {
  seat: number;
  action: string;
  amount: number;
  playerLabel: string;
  timestamp: number;
}

interface Props {
  actions: ActionEntry[];
}

const ACTION_COLORS: Record<string, string> = {
  fold: "text-red-400",
  check: "text-gray-400",
  call: "text-blue-400",
  bet: "text-gold-400",
  raise: "text-gold-400",
  all_in: "text-emerald-400",
  timeout_fold: "text-red-400",
};

function formatChips(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 10_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString();
}

function formatAction(action: string): string {
  if (action === "all_in") return "All In";
  if (action === "timeout_fold") return "Timed out";
  return action.charAt(0).toUpperCase() + action.slice(1);
}

export type { ActionEntry };

export default function ActionLog({ actions }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [actions.length]);

  if (actions.length === 0) return null;

  return (
    <div className="bg-gray-900/80 backdrop-blur-sm rounded-xl border border-white/5 overflow-hidden shadow-xl">
      <div className="px-3 py-2 border-b border-white/5">
        <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">Action Log</span>
      </div>
      <div ref={scrollRef} className="max-h-48 overflow-y-auto px-3 py-2 space-y-1 scrollbar-thin">
        {actions.map((a, i) => {
          const color = ACTION_COLORS[a.action] || "text-gray-400";
          return (
            <div key={i} className="flex items-center gap-1.5 text-xs">
              <span className="text-gray-500 shrink-0">{a.playerLabel}</span>
              <span className={`font-medium ${color}`}>
                {formatAction(a.action)}
              </span>
              {a.amount > 0 && a.action !== "fold" && a.action !== "check" && (
                <span className="text-gray-500 tabular-nums">{formatChips(a.amount)}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
