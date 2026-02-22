import { useEffect, useState, useCallback } from "react";
import { getTodaysMatches, getMyLineup, saveLineup } from "../api/client";
import type { Match, Player, LineupEntry, Position } from "../types";
import LineupSlot from "../components/LineupSlot";
import PlayerPickerModal from "../components/PlayerPickerModal";
import MatchCountdown from "../components/MatchCountdown";

interface SlotDef {
  key: string;
  position: Position;
  label: string;
}

const SLOTS: SlotDef[] = [
  { key: "f1", position: "Forward", label: "Forward 1" },
  { key: "f2", position: "Forward", label: "Forward 2" },
  { key: "f3", position: "Forward", label: "Forward 3" },
  { key: "d1", position: "Defender", label: "Defender 1" },
  { key: "d2", position: "Defender", label: "Defender 2" },
  { key: "gk", position: "Goalkeeper", label: "Goalkeeper" },
];

type SlotMap = Record<string, Player | null>;
type CaptainKey = string | null;

export default function Dashboard() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [day, setDay] = useState<number>(1);
  const [slots, setSlots] = useState<SlotMap>(() =>
    Object.fromEntries(SLOTS.map((s) => [s.key, null]))
  );
  const [captainKey, setCaptainKey] = useState<CaptainKey>(null);
  const [lockedIds, setLockedIds] = useState<Set<number>>(new Set());
  const [pickerSlot, setPickerSlot] = useState<SlotDef | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const loadMatches = useCallback(async () => {
    try {
      const res = await getTodaysMatches();
      setMatches(res.data);
      if (res.data.length > 0) setDay(res.data[0].day);
      const locked = new Set<number>();
      setLockedIds(locked);
    } catch {
      // no matches today or offline
    }
  }, []);

  const loadLineup = useCallback(async (d: number) => {
    try {
      const res = await getMyLineup(d);
      const newSlots: SlotMap = Object.fromEntries(SLOTS.map((s) => [s.key, null]));
      let newCaptain: CaptainKey = null;

      // Map saved entries back into slots by position order
      const byPosition: Record<Position, LineupEntry[]> = { Forward: [], Defender: [], Goalkeeper: [] };
      for (const entry of res.data.lineup) {
        byPosition[entry.player.position as Position]?.push(entry);
      }

      const posSlots: Record<Position, string[]> = {
        Forward: ["f1", "f2", "f3"],
        Defender: ["d1", "d2"],
        Goalkeeper: ["gk"],
      };

      for (const pos of ["Forward", "Defender", "Goalkeeper"] as Position[]) {
        byPosition[pos].forEach((entry, i) => {
          const key = posSlots[pos][i];
          if (key) {
            newSlots[key] = entry.player;
            if (entry.is_captain) newCaptain = key;
          }
        });
      }

      setSlots(newSlots);
      setCaptainKey(newCaptain);
    } catch {
      // no lineup yet
    }
  }, []);

  useEffect(() => {
    loadMatches();
    const interval = setInterval(loadMatches, 60_000);
    return () => clearInterval(interval);
  }, [loadMatches]);

  useEffect(() => {
    loadLineup(day);
  }, [day, loadLineup]);

  const selectedIds = new Set(
    Object.values(slots).filter(Boolean).map((p) => p!.id)
  );

  const handleRemove = (key: string) => {
    setSlots((prev) => ({ ...prev, [key]: null }));
    if (captainKey === key) setCaptainKey(null);
  };

  const handleToggleCaptain = (key: string) => {
    setCaptainKey((prev) => (prev === key ? null : key));
  };

  const handleSave = async () => {
    const players = SLOTS.flatMap((slot) => {
      const player = slots[slot.key];
      if (!player) return [];
      return [{ player_id: player.id, is_captain: captainKey === slot.key }];
    });
    if (players.length === 0) return;
    setSaving(true);
    try {
      await saveLineup(day, players);
      showToast("Lineup saved!", true);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Failed to save lineup";
      showToast(msg, false);
    } finally {
      setSaving(false);
    }
  };

  const hasAnyPlayer = Object.values(slots).some(Boolean);

  return (
    <div>
      {toast && (
        <div
          className={`fixed top-4 right-4 px-4 py-2 rounded text-sm shadow-lg ${
            toast.ok ? "bg-green-700 text-white" : "bg-red-700 text-white"
          }`}
        >
          {toast.msg}
        </div>
      )}

      <h1 className="text-xl font-bold mb-1">Day {day} Lineup</h1>
      <p className="text-gray-400 text-sm mb-4">
        Pick up to 6 players from matches that haven't started yet. One as captain (2× points).
      </p>

      {/* Today's matches */}
      {matches.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">Today's matches</h2>
          <div className="flex flex-wrap gap-2">
            {matches.map((m) => (
              <div key={m.id} className="bg-navy-800 rounded-lg px-4 py-2 text-sm flex items-center gap-3">
                <span className="font-semibold">{m.home_team}</span>
                <span className="text-gray-500 text-xs">vs</span>
                <span className="font-semibold">{m.away_team}</span>
                <MatchCountdown match_time={m.match_time} status={m.status} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lineup grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        {SLOTS.slice(0, 3).map((slot) => (
          <LineupSlot
            key={slot.key}
            position={slot.position}
            label={slot.label}
            player={slots[slot.key]}
            isCaptain={captainKey === slot.key}
            isLocked={slots[slot.key] ? lockedIds.has(slots[slot.key]!.id) : false}
            onPick={() => setPickerSlot(slot)}
            onRemove={() => handleRemove(slot.key)}
            onToggleCaptain={() => handleToggleCaptain(slot.key)}
          />
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        {SLOTS.slice(3, 5).map((slot) => (
          <LineupSlot
            key={slot.key}
            position={slot.position}
            label={slot.label}
            player={slots[slot.key]}
            isCaptain={captainKey === slot.key}
            isLocked={slots[slot.key] ? lockedIds.has(slots[slot.key]!.id) : false}
            onPick={() => setPickerSlot(slot)}
            onRemove={() => handleRemove(slot.key)}
            onToggleCaptain={() => handleToggleCaptain(slot.key)}
          />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 mb-6 max-w-xs">
        <LineupSlot
          key="gk"
          position="Goalkeeper"
          label="Goalkeeper"
          player={slots["gk"]}
          isCaptain={captainKey === "gk"}
          isLocked={slots["gk"] ? lockedIds.has(slots["gk"]!.id) : false}
          onPick={() => setPickerSlot(SLOTS[5])}
          onRemove={() => handleRemove("gk")}
          onToggleCaptain={() => handleToggleCaptain("gk")}
        />
      </div>

      <button
        onClick={handleSave}
        disabled={!hasAnyPlayer || saving}
        data-testid="save-lineup"
        className="bg-gold text-navy-900 font-semibold px-6 py-2 rounded hover:opacity-90 disabled:opacity-40"
      >
        {saving ? "Saving…" : "Save Lineup"}
      </button>

      {pickerSlot && (
        <PlayerPickerModal
          position={pickerSlot.position}
          alreadySelectedIds={selectedIds}
          onSelect={(player) => {
            setSlots((prev) => ({ ...prev, [pickerSlot.key]: player }));
          }}
          onClose={() => setPickerSlot(null)}
        />
      )}
    </div>
  );
}
