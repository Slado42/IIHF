export interface User {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface Player {
  id: number;
  name: string;
  position: "Forward" | "Defender" | "Goalkeeper";
  team_abbr: string;
  championship_year: number;
}

export interface Match {
  id: number;
  day: number;
  date: string;
  match_time: string; // ISO8601 UTC
  home_team: string;
  away_team: string;
  status: "upcoming" | "live" | "completed";
}

export interface LineupEntry {
  player_id: number;
  is_captain: boolean;
  locked: boolean;
  player: Player;
}

export interface LineupResponse {
  day: number;
  lineup: LineupEntry[];
}

export interface PlayerScoreDetail {
  player_id: number;
  name: string;
  team_abbr: string;
  position: string;
  is_captain: boolean;
  fantasy_points: number;
}

export interface UserDayScore {
  day: number;
  total_points: number;
  players: PlayerScoreDetail[];
}

export interface StandingEntry {
  rank: number;
  username: string;
  user_id: string;
  total_points: number;
  scores_by_day: Record<number, number>;
}

export type Position = "Forward" | "Defender" | "Goalkeeper";

export interface LineupSlotDef {
  position: Position;
  label: string;
}
