import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Calendar,
  CheckCircle2,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { Episode } from "../services/episodesService";

interface EpisodeCardProps {
  episode: Episode;
  status?: "processing" | "completed" | "failed";
  progress?: number;
}

export default function EpisodeCard({
  episode,
  status = "completed",
}: EpisodeCardProps) {
  const [showQuiz, setShowQuiz] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  const isProcessing = status === "processing";
  const isFailed = status === "failed";

  const formatDate = (timestamp: number) => {
    if (!timestamp) return "";
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  const renderConclusion = (conclusion: string | string[]) => {
    if (Array.isArray(conclusion)) {
      return conclusion.join(" ");
    }
    return conclusion;
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow relative">
      {/* Processing Overlay */}
      {isProcessing && (
        <div className="absolute inset-0 z-20 bg-gradient-to-b from-blue-500/10 via-transparent to-blue-500/5 pointer-events-none flex items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <div className="bg-white/80 backdrop-blur-sm px-4 py-3 rounded-lg shadow-sm border border-blue-200/30">
              <Loader2 className="h-5 w-5 text-blue-600 animate-spin mx-auto" />
            </div>
            <p className="text-xs font-medium text-blue-700/70 whitespace-nowrap">
              Processing
            </p>
          </div>
        </div>
      )}

      <div className="flex flex-col md:flex-row">
        {/* Episode Image */}
        <div className="md:w-48 md:h-48 flex-shrink-0">
          {episode.episode_image ? (
            <img
              src={episode.episode_image}
              alt={episode.episode_title}
              className="w-full h-48 md:h-full object-cover"
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.src =
                  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='%23e5e7eb'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='16' fill='%239ca3af'%3ENo Image%3C/text%3E%3C/svg%3E";
              }}
            />
          ) : (
            <div className="w-full h-48 md:h-full bg-gray-200 flex items-center justify-center">
              <span className="text-gray-400 text-sm">No Image</span>
            </div>
          )}
        </div>

        {/* Episode Metadata */}
        <div className="flex-1 p-6">
          <div className="mb-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-xl font-bold text-gray-900 mb-1">
                  {episode.episode_title}
                </h3>
                <p className="text-sm text-gray-600 mb-2">
                  {episode.podcast_title}
                </p>
                {episode.episode_date_published > 0 && (
                  <div className="flex items-center text-xs text-gray-500">
                    <Calendar className="h-3 w-3 mr-1" />
                    <span>
                      Published: {formatDate(episode.episode_date_published)}
                    </span>
                  </div>
                )}
              </div>

              {/* Status badge - only display on failure since 'En cours' is already in overlay */}
              {isFailed && (
                <div className="inline-flex items-center px-2 py-1 rounded-full border text-xs font-medium whitespace-nowrap bg-red-50 text-red-700 border-red-200">
                  <AlertCircle className="h-3.5 w-3.5 mr-1" />
                  Processing failed
                </div>
              )}
            </div>
          </div>

          {/* Accordions - only render when not processing */}
          {!isProcessing && (
            <>
              {/* Quiz Accordion */}
              <div className="mb-3">
                <button
                  onClick={() => setShowQuiz(!showQuiz)}
                  className={`flex items-center justify-between w-full px-4 py-2 text-sm font-semibold text-left rounded-lg transition-colors bg-gradient-to-r from-blue-50 to-purple-50 hover:from-blue-100 hover:to-purple-100`}
                >
                  <span>{`Reveal quiz (${episode.quiz?.questions?.length || 0} questions)`}</span>
                  {showQuiz ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </button>
                {showQuiz && episode.quiz && (
                  <div className="mt-2 p-4 bg-gray-50 rounded-lg space-y-4">
                    {episode.quiz.questions.map((question, qIndex) => (
                      <div
                        key={question.id || qIndex}
                        className="border-b border-gray-200 pb-4 last:border-0"
                      >
                        <p className="font-medium text-gray-900 mb-2">
                          {qIndex + 1}. {question.prompt}
                        </p>
                        <div className="space-y-2 ml-4">
                          {question.choices.map((choice) => (
                            <div
                              key={choice.id}
                              className={`flex items-start space-x-2 text-sm ${choice.correct ? "text-green-700 font-medium" : "text-gray-700"}`}
                            >
                              {choice.correct && (
                                <CheckCircle2 className="h-4 w-4 flex-shrink-0 mt-0.5" />
                              )}
                              <span className={choice.correct ? "" : "ml-6"}>
                                {choice.id.toUpperCase()}. {choice.text}
                              </span>
                            </div>
                          ))}
                        </div>
                        {question.explanation && (
                          <p className="mt-2 ml-4 text-xs text-gray-600 italic">
                            {question.explanation}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Summary Accordion */}
              <div>
                <button
                  onClick={() => setShowSummary(!showSummary)}
                  className={`flex items-center justify-between w-full px-4 py-2 text-sm font-semibold text-left rounded-lg transition-colors bg-gradient-to-r from-blue-50 to-purple-50 hover:from-blue-100 hover:to-purple-100`}
                >
                  <span>Reveal summary</span>
                  {showSummary ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </button>
                {showSummary && episode.summary && (
                  <div className="mt-2 p-4 bg-gray-50 rounded-lg space-y-4">
                    {/* Main Topics */}
                    {episode.summary.main_topics &&
                      episode.summary.main_topics.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold text-gray-700 mb-2">
                            Main topics:
                          </h4>
                          <div className="flex flex-wrap gap-2">
                            {episode.summary.main_topics.map((topic, index) => (
                              <span
                                key={index}
                                className="px-3 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded-full"
                              >
                                {topic}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                    {/* Key Points */}
                    {episode.summary.key_points &&
                      episode.summary.key_points.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold text-gray-700 mb-2">
                            Key points:
                          </h4>
                          <ul className="list-disc list-inside space-y-1">
                            {episode.summary.key_points.map((point, index) => (
                              <li key={index} className="text-sm text-gray-700">
                                {point}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                    {/* Notable Quotes */}
                    {episode.summary.notable_quotes &&
                      episode.summary.notable_quotes.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold text-gray-700 mb-2">
                            Notable quotes:
                          </h4>
                          <div className="space-y-2">
                            {episode.summary.notable_quotes.map(
                              (quote, index) => (
                                <blockquote
                                  key={index}
                                  className="border-l-4 border-gray-300 pl-3 italic text-sm text-gray-600"
                                >
                                  "{quote}"
                                </blockquote>
                              ),
                            )}
                          </div>
                        </div>
                      )}

                    {/* Conclusion */}
                    {episode.summary.conclusion && (
                      <div>
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">
                          Conclusion:
                        </h4>
                        <p className="text-sm text-gray-700">
                          {renderConclusion(episode.summary.conclusion)}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
