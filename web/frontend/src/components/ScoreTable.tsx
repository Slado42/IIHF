import type { StandingEntry } from "../types";

interface Props {
  standings: StandingEntry[];
  currentUserId?: string;
}

export default function ScoreTable({ standings, currentUserId }: Props) {
  if (standings.length === 0) {
    return <p className="text-gray-400 text-sm">No standings yet.</p>;
  }

  // Collect all days for column headers
  const allDays = [...new Set(
    standings.flatMap((s) => Object.keys(s.scores_by_day).map(Number))
  )].sort((a, b) => a - b);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-navy-700 text-gray-400">
            <th className="text-left py-2 pr-4 w-8">#</th>
            <th className="text-left py-2 pr-6">Player</th>
            <th className="text-right py-2 pr-4 font-semibold text-white">Total</th>
            {allDays.map((d) => (
              <th key={d} className="text-right py-2 pr-3">Day {d}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {standings.map((entry) => {
            const isMe = entry.user_id === currentUserId;
            return (
              <tr
                key={entry.user_id}
                className={`border-b border-navy-700/50 ${isMe ? "bg-gold/10" : "hover:bg-navy-800"}`}
              >
                <td className="py-2 pr-4 text-gray-400">{entry.rank}</td>
                <td className="py-2 pr-6 font-medium">
                  {entry.username}
                  {isMe && <span className="ml-2 text-xs text-gold">you</span>}
                </td>
                <td className="py-2 pr-4 text-right font-bold text-gold">
                  {entry.total_points.toFixed(1)}
                </td>
                {allDays.map((d) => (
                  <td key={d} className="py-2 pr-3 text-right text-gray-300">
                    {(entry.scores_by_day[d] ?? 0).toFixed(1)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
