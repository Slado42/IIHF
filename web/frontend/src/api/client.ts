import axios from "axios";
import type {
  User, Player, Match, LineupResponse, StandingEntry, UserDayScore
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, clear token and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export const signup = (username: string, email: string, password: string) =>
  api.post<{ access_token: string }>("/auth/signup", { username, email, password });

export const login = (username: string, password: string) => {
  const form = new URLSearchParams();
  form.append("username", username);
  form.append("password", password);
  return api.post<{ access_token: string }>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
};

export const getMe = () => api.get<User>("/auth/me");

export const getPlayers = (position?: string, team?: string) =>
  api.get<Player[]>("/players", { params: { position, team } });

export const getTodaysMatches = () => api.get<Match[]>("/matches/today");

export const getMatches = (day?: number) =>
  api.get<Match[]>("/matches", { params: { day } });

export const getMyLineup = (day: number) =>
  api.get<LineupResponse>("/lineup/me", { params: { day } });

export const saveLineup = (
  day: number,
  players: { player_id: number; is_captain: boolean }[]
) => api.post<LineupResponse>("/lineup/me", { day, players });

export const getStandings = () => api.get<StandingEntry[]>("/scores/standings");

export const getMyScores = () => api.get<UserDayScore[]>("/scores/me");
