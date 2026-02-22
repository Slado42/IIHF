import { useEffect, useState } from "react";
import { getMyScores } from "../api/client";
import type { UserDayScore } from "../types";

export default function History() {
  const [scores, setScores] = useState<UserDayScore[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  useEffect(() => {
    getMyScores()
      .then((res) => setScores(res.data))
      .finally(() => setLoading(false));
  }, []);

  const toggle = (day: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(day) ? next.delete(day) : next.add(day);
      return next;
    });
  };

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">My History</h1>
      {loading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-12 bg-navy-800 rounded animate-pulse" />
          ))}
        </div>
      ) : scores.length === 0 ? (
        <p className="text-gray-400 text-sm">No scores yet. Play your first lineup!</p>
      ) : (
        <div className="space-y-2">
          {scores.map((ds) => (
            <div key={ds.day} className="bg-navy-800 rounded-xl overflow-hidden">
              <button
                onClick={() => toggle(ds.day)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-navy-700 transition-colors"
              >
                <span className="font-medium">Day {ds.day}</span>
                <div className="flex items-center gap-3">
                  <span className="text-gold font-bold">{ds.total_points.toFixed(1)} pts</span>
                  <span className="text-gray-400 text-sm">{expanded.has(ds.day) ? "▲" : "▼"}</span>
                </div>
              </button>

              {expanded.has(ds.day) && (
                <div className="border-t border-navy-700 px-4 py-3 space-y-1">
                  {ds.players.map((p) => (
                    <div key={p.player_id} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400 font-mono w-8">{p.team_abbr}</span>
                        <span>{p.name}</span>
                        {p.is_captain && <span className="text-gold text-xs">★ CAP</span>}
                        <span className="text-xs text-gray-500">{p.position}</span>
                      </div>
                      <span className="text-gold font-semibold">{p.fantasy_points.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
