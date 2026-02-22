import type { Player, Position } from "../types";
import PlayerCard from "./PlayerCard";

interface Props {
  position: Position;
  label: string;
  player: Player | null;
  isCaptain: boolean;
  isLocked: boolean;
  onPick: () => void;
  onRemove: () => void;
  onToggleCaptain: () => void;
}

export default function LineupSlot({ position, label, player, isCaptain, isLocked, onPick, onRemove, onToggleCaptain }: Props) {
  const posColor: Record<Position, string> = {
    Forward: "text-blue-400",
    Defender: "text-green-400",
    Goalkeeper: "text-yellow-400",
  };

  return (
    <div className="bg-navy-800 rounded-lg p-3 border border-navy-700">
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs font-semibold uppercase tracking-wide ${posColor[position]}`}>
          {label}
        </span>
        {isCaptain && <span className="text-xs text-gold font-bold">CAPTAIN 2×</span>}
      </div>

      {player ? (
        <PlayerCard
          player={player}
          isCaptain={isCaptain}
          isLocked={isLocked}
          onRemove={isLocked ? undefined : onRemove}
          onToggleCaptain={onToggleCaptain}
        />
      ) : (
        <button
          onClick={onPick}
          data-testid={`pick-${position}`}
          className="w-full border-2 border-dashed border-navy-700 rounded-lg py-3 text-gray-500 hover:border-gold hover:text-gold text-sm transition-colors"
        >
          + Pick {position}
        </button>
      )}
    </div>
  );
}
