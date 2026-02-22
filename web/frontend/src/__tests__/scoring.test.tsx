/**
 * Tests for scoring display logic using the real ScoreTable component.
 *
 * ScoreTable receives a `standings: StandingEntry[]` prop and renders a table
 * where total_points is shown via .toFixed(1).  Captains are shown in the
 * lineup via LineupSlot (which shows "CAPTAIN 2x"), but ScoreTable itself
 * does not track captain state – it only shows points.
 *
 * We test:
 *   1. Captain indicator visible in LineupSlot
 *   2. Player with 0 points shows "0.0" in ScoreTable
 *   3. ScoreTable renders the correct number of rows
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ScoreTable from "../components/ScoreTable";
import LineupSlot from "../components/LineupSlot";
import type { StandingEntry, Player } from "../types";

// ---------------------------------------------------------------------------
// ScoreTable tests
// ---------------------------------------------------------------------------

function makeStanding(
  username: string,
  total: number,
  scoresByDay: Record<number, number> = {}
): StandingEntry {
  return {
    rank: 1,
    username,
    user_id: username + "-id",
    total_points: total,
    scores_by_day: scoresByDay,
  };
}

describe("ScoreTable", () => {
  it("renders the correct number of rows (one per standing entry)", () => {
    const standings = [
      makeStanding("alice", 12),
      makeStanding("bob", 6),
      makeStanding("carol", 0),
    ];
    render(<ScoreTable standings={standings} />);

    // Each standing entry becomes a <tr> in tbody
    const rows = screen.getAllByRole("row");
    // 1 header row + 3 data rows = 4
    expect(rows).toHaveLength(4);
  });

  it("player with 0 points shows '0.0'", () => {
    const standings = [makeStanding("carol", 0, { 1: 0 })];
    render(<ScoreTable standings={standings} />);

    // total_points column uses .toFixed(1) → "0.0"
    const totalCells = screen.getAllByText("0.0");
    expect(totalCells.length).toBeGreaterThan(0);
  });

  it("shows player names in the table", () => {
    const standings = [
      makeStanding("alice", 12),
      makeStanding("bob", 6),
    ];
    render(<ScoreTable standings={standings} />);
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// LineupSlot – captain 2x indicator
// ---------------------------------------------------------------------------

const mockPlayer: Player = {
  id: 1,
  name: "Wayne Gretzky",
  position: "Forward",
  team_abbr: "CAN",
  championship_year: 2026,
};

describe("LineupSlot captain indicator", () => {
  it("shows 'CAPTAIN 2x' badge when isCaptain=true", () => {
    render(
      <LineupSlot
        position="Forward"
        label="Forward 1"
        player={mockPlayer}
        isCaptain={true}
        isLocked={false}
        onPick={() => {}}
        onRemove={() => {}}
        onToggleCaptain={() => {}}
      />
    );
    expect(screen.getByText(/CAPTAIN 2/i)).toBeInTheDocument();
  });

  it("does not show captain badge when isCaptain=false", () => {
    render(
      <LineupSlot
        position="Forward"
        label="Forward 1"
        player={mockPlayer}
        isCaptain={false}
        isLocked={false}
        onPick={() => {}}
        onRemove={() => {}}
        onToggleCaptain={() => {}}
      />
    );
    expect(screen.queryByText(/CAPTAIN 2/i)).not.toBeInTheDocument();
  });
});
