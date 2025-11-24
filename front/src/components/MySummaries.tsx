import { useState, useEffect } from "react";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import { SummariesService, MySummariesResponse } from "../services/summariesService";
import SummaryCard from "./SummaryCard";

interface MySummariesProps {
  token: string;
  onBack: () => void;
}

export default function MySummaries({ token, onBack }: MySummariesProps) {
  const [data, setData] = useState<MySummariesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSummaries();
  }, [token]);

  const loadSummaries = async () => {
    try {
      setLoading(true);
      setError(null);
      const summariesData = await SummariesService.getMySummaries(token);
      setData(summariesData);
    } catch (err) {
      console.error("Failed to load summaries:", err);
      setError(
        err instanceof Error ? err.message : "Failed to load summaries"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16">
            <button
              onClick={onBack}
              className="flex items-center space-x-2 px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Retour</span>
            </button>
            <h1 className="ml-4 text-xl font-bold text-gray-900">
              Mes Résumés
            </h1>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {loading && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-12 w-12 animate-spin text-blue-600 mb-4" />
            <p className="text-gray-600">Chargement de vos résumés...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-red-800 mb-1">
                Erreur de chargement
              </h3>
              <p className="text-sm text-red-700">{error}</p>
              <button
                onClick={loadSummaries}
                className="mt-3 text-sm text-red-700 underline hover:text-red-900"
              >
                Réessayer
              </button>
            </div>
          </div>
        )}

        {!loading && !error && data && (
          <>
            {data.count === 0 ? (
              <div className="text-center py-12">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
                  <svg
                    className="w-8 h-8 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Aucun résumé disponible
                </h3>
                <p className="text-gray-600 mb-6">
                  Vous n'avez pas encore de résumés d'épisodes générés.
                </p>
                <button
                  onClick={onBack}
                  className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Rechercher des podcasts
                </button>
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <p className="text-sm text-gray-600">
                    {data.count} résumé{data.count > 1 ? "s" : ""} trouvé
                    {data.count > 1 ? "s" : ""}
                  </p>
                </div>
                <div className="space-y-6">
                  {data.summaries.map((summary) => (
                    <SummaryCard key={summary.job_id} summary={summary} />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
