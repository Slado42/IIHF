import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { getMe, login as apiLogin, signup as apiSignup } from "../api/client";
import type { User } from "../types";

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  signup: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem("token"));
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (token) {
      getMe()
        .then((res) => setUser(res.data))
        .catch(() => {
          localStorage.removeItem("token");
          setToken(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [token]);

  const login = async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    const newToken = res.data.access_token;
    localStorage.setItem("token", newToken);
    setToken(newToken);
    const me = await getMe();
    setUser(me.data);
  };

  const signup = async (username: string, email: string, password: string) => {
    const res = await apiSignup(username, email, password);
    const newToken = res.data.access_token;
    localStorage.setItem("token", newToken);
    setToken(newToken);
    const me = await getMe();
    setUser(me.data);
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
