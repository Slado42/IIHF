import { useState, FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Invalid username or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-navy-900 flex items-center justify-center px-4">
      <div className="bg-navy-800 rounded-xl p-8 w-full max-w-sm shadow-xl">
        <h1 className="text-2xl font-bold text-white mb-2 text-center">🏒 IIHF Fantasy</h1>
        <p className="text-gray-400 text-sm text-center mb-6">Sign in to your account</p>

        {error && (
          <div className="bg-red-900/50 border border-red-500 text-red-200 rounded px-3 py-2 text-sm mb-4">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full bg-navy-900 border border-navy-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-gold"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-navy-900 border border-navy-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-gold"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gold text-navy-900 font-semibold py-2 rounded hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-400 mt-4">
          No account?{" "}
          <Link to="/signup" className="text-gold hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
