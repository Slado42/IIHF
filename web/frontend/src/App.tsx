import { BrowserRouter, Routes, Route, Navigate, Link } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Dashboard from "./pages/Dashboard";
import Standings from "./pages/Standings";
import History from "./pages/History";
import type { ReactNode } from "react";

function Protected({ children }: { children: ReactNode }) {
  const { token, isLoading } = useAuth();
  if (isLoading) return <div className="flex items-center justify-center h-screen text-white">Loading...</div>;
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function NavBar() {
  const { user, logout } = useAuth();
  return (
    <nav className="bg-navy-800 border-b border-navy-700 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <span className="text-gold font-bold text-lg">🏒 IIHF Fantasy</span>
        <Link to="/" className="text-gray-300 hover:text-white text-sm">Dashboard</Link>
        <Link to="/standings" className="text-gray-300 hover:text-white text-sm">Standings</Link>
        <Link to="/history" className="text-gray-300 hover:text-white text-sm">My History</Link>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-gray-400 text-sm">{user?.username}</span>
        <button
          onClick={logout}
          className="bg-navy-700 hover:bg-navy-900 text-white text-sm px-3 py-1 rounded"
        >
          Logout
        </button>
      </div>
    </nav>
  );
}

function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-navy-900 text-white">
      <NavBar />
      <main className="max-w-5xl mx-auto px-4 py-8">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/"
            element={
              <Protected>
                <Layout><Dashboard /></Layout>
              </Protected>
            }
          />
          <Route
            path="/standings"
            element={
              <Protected>
                <Layout><Standings /></Layout>
              </Protected>
            }
          />
          <Route
            path="/history"
            element={
              <Protected>
                <Layout><History /></Layout>
              </Protected>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
