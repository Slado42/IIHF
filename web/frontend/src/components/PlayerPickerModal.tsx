import { useEffect, useState } from "react";
import { getPlayers } from "../api/client";
import type { Player, Position } from "../types";

interface Props {
  position: Position;
  alreadySelectedIds: Set<number>;
  onSelect: (player: Player) => void;
  onClose: () => void;
}

export default function PlayerPickerModal({ position, alreadySelectedIds, onSelect, onClose }: Props) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("");

  useEffect(() => {
    getPlayers(position).then((res) => setPlayers(res.data));
  }, [position]);

  const teams = [...new Set(players.map((p) => p.team_abbr))].sort();

  const filtered = players.filter((p) => {
    const matchesSearch = p.name.toLowerCase().includes(search.toLowerCase());
    const matchesTeam = !teamFilter || p.team_abbr === teamFilter;
    return matchesSearch && matchesTeam;
  });

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-navy-800 rounded-xl w-full max-w-lg shadow-2xl flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between px-4 py-3 border-b border-navy-700">
          <h2 className="font-semibold text-white">Pick {position}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">✕</button>
        </div>

        <div className="px-4 py-3 flex gap-2">
          <input
            type="text"
            placeholder="Search by name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 bg-navy-900 border border-navy-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-gold"
            autoFocus
          />
          <select
            value={teamFilter}
            onChange={(e) => setTeamFilter(e.target.value)}
            className="bg-navy-900 border border-navy-700 rounded px-2 py-1.5 text-white text-sm focus:outline-none"
          >
            <option value="">All teams</option>
            {teams.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        <div className="overflow-y-auto flex-1 px-4 pb-4 space-y-1">
          {filtered.length === 0 && (
            <p className="text-center text-gray-500 py-6 text-sm">No players found</p>
          )}
          {filtered.map((player) => {
            const disabled = alreadySelectedIds.has(player.id);
            return (
              <button
                key={player.id}
                disabled={disabled}
                onClick={() => { onSelect(player); onClose(); }}
                className={`w-full text-left flex items-center gap-3 px-3 py-2 rounded ${
                  disabled
                    ? "opacity-40 cursor-not-allowed bg-navy-900"
                    : "hover:bg-navy-700 bg-navy-900"
                }`}
              >
                <span className="text-xs font-mono text-gray-400 w-8">{player.team_abbr}</span>
                <span className="text-sm text-white flex-1">{player.name}</span>
                {disabled && <span className="text-xs text-gray-500">Selected</span>}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
