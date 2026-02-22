import type { Player } from "../types";

interface Props {
  player: Player;
  isCaptain?: boolean;
  isLocked?: boolean;
  onRemove?: () => void;
  onToggleCaptain?: () => void;
}

export default function PlayerCard({ player, isCaptain, isLocked, onRemove, onToggleCaptain }: Props) {
  return (
    <div className={`flex items-center justify-between rounded-lg px-3 py-2 ${isCaptain ? "bg-gold/20 border border-gold" : "bg-navy-700"}`}>
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-xs font-mono bg-navy-900 text-gray-300 px-1.5 py-0.5 rounded">
          {player.team_abbr}
        </span>
        <span className="text-sm text-white truncate">{player.name}</span>
        {isLocked && <span className="text-xs text-gray-400">🔒</span>}
      </div>
      <div className="flex items-center gap-1 ml-2 shrink-0">
        <button
          onClick={onToggleCaptain}
          disabled={isLocked}
          title={isCaptain ? "Remove captain" : "Set as captain (2×)"}
          className={`text-sm px-1.5 rounded ${isCaptain ? "text-gold" : "text-gray-500 hover:text-gold"} disabled:opacity-40`}
        >
          ★
        </button>
        {onRemove && (
          <button
            onClick={onRemove}
            disabled={isLocked}
            className="text-gray-500 hover:text-red-400 text-sm px-1 disabled:opacity-40"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
