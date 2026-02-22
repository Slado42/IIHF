/**
 * Tests for the Dashboard page.
 *
 * Dashboard calls getTodaysMatches and getMyLineup on mount.
 * We mock ../api/client so those calls are controlled.
 *
 * Assertions:
 *   1. Six lineup slots are rendered (3F + 2D + 1G) via pick buttons
 *   2. Clicking a "Pick Forward" slot opens the PlayerPickerModal
 *      (identified by the "Search by name" input that only appears in the modal)
 *   3. Save button is disabled when no players are selected
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/client", () => ({
  login: vi.fn(),
  signup: vi.fn(),
  getMe: vi.fn(),
  getPlayers: vi.fn(),
  getTodaysMatches: vi.fn(),
  getMatches: vi.fn(),
  getMyLineup: vi.fn(),
  saveLineup: vi.fn(),
  getStandings: vi.fn(),
  getMyScores: vi.fn(),
}));

import * as apiClient from "../api/client";
import Dashboard from "../pages/Dashboard";

function Wrapper({ children }: { children: React.ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(apiClient.getTodaysMatches).mockResolvedValue({ data: [] } as any);
    vi.mocked(apiClient.getMyLineup).mockResolvedValue({
      data: { day: 1, lineup: [] },
    } as any);
    // Modal calls getPlayers when opened
    vi.mocked(apiClient.getPlayers).mockResolvedValue({ data: [] } as any);
  });

  it("renders 6 lineup slots (3F, 2D, 1G)", async () => {
    render(
      <Wrapper>
        <Dashboard />
      </Wrapper>
    );

    await waitFor(() => {
      const forwardButtons = screen.getAllByTestId("pick-Forward");
      expect(forwardButtons).toHaveLength(3);

      const defenderButtons = screen.getAllByTestId("pick-Defender");
      expect(defenderButtons).toHaveLength(2);

      const gkButtons = screen.getAllByTestId("pick-Goalkeeper");
      expect(gkButtons).toHaveLength(1);
    });
  });

  it("clicking a Pick Forward slot opens the PlayerPickerModal", async () => {
    const user = userEvent.setup();

    render(
      <Wrapper>
        <Dashboard />
      </Wrapper>
    );

    // Confirm no modal is open initially (search input is unique to the modal)
    expect(screen.queryByPlaceholderText(/search by name/i)).not.toBeInTheDocument();

    // Wait for the empty slots to appear
    await waitFor(() => {
      expect(screen.getAllByTestId("pick-Forward")).toHaveLength(3);
    });

    const forwardPicks = screen.getAllByTestId("pick-Forward");
    await user.click(forwardPicks[0]);

    // PlayerPickerModal renders a search input – this appears only when the modal is open
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search by name/i)).toBeInTheDocument();
    });
  });

  it("Save Lineup button is disabled when no players are selected", async () => {
    render(
      <Wrapper>
        <Dashboard />
      </Wrapper>
    );

    await waitFor(() => {
      const saveBtn = screen.getByTestId("save-lineup");
      expect(saveBtn).toBeDisabled();
    });
  });
});
