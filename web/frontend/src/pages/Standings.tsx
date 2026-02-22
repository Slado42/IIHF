import { useEffect, useState } from "react";
import { getStandings } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { StandingEntry } from "../types";
import ScoreTable from "../components/ScoreTable";

export default function Standings() {
  const { user } = useAuth();
  const [standings, setStandings] = useState<StandingEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStandings()
      .then((res) => setStandings(res.data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Standings</h1>
      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-navy-800 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="bg-navy-800 rounded-xl p-4">
          <ScoreTable standings={standings} currentUserId={user?.id} />
        </div>
      )}
    </div>
  );
}
