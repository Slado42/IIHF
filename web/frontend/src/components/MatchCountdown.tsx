import { useEffect, useState } from "react";

interface Props {
  match_time: string; // ISO8601 UTC
  status: string;
}

function formatCountdown(ms: number): string {
  if (ms <= 0) return "Starting soon";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  if (h > 0) return `Locks in ${h}h ${m}m`;
  return `Locks in ${m}m`;
}

export default function MatchCountdown({ match_time, status }: Props) {
  const [display, setDisplay] = useState("");

  useEffect(() => {
    if (status === "completed") {
      setDisplay("Final");
      return;
    }
    if (status === "live") {
      setDisplay("🔴 LIVE");
      return;
    }
    const update = () => {
      const ms = new Date(match_time).getTime() - Date.now();
      setDisplay(ms <= 0 ? "🔒 Locked" : formatCountdown(ms));
    };
    update();
    const id = setInterval(update, 30_000);
    return () => clearInterval(id);
  }, [match_time, status]);

  return <span className="text-xs text-gray-400">{display}</span>;
}
