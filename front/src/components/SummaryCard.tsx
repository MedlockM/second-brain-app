import { SummaryItem } from "../services/summariesService";

interface SummaryCardProps {
  summary: SummaryItem;
}

export default function SummaryCard({ summary }: SummaryCardProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const renderConclusion = (conclusion: string | string[]) => {
    if (Array.isArray(conclusion)) {
      return conclusion.join(" ");
    }
    return conclusion;
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow">
      <div className="flex flex-col md:flex-row">
        {/* Episode Image */}
        <div className="md:w-48 md:h-48 flex-shrink-0">
          {summary.episode_image ? (
            <img
              src={summary.episode_image}
              alt={summary.episode_title}
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

        {/* Summary Content */}
        <div className="flex-1 p-6">
          {/* Header */}
          <div className="mb-4">
            <h3 className="text-xl font-bold text-gray-900 mb-1">
              {summary.episode_title}
            </h3>
            <p className="text-sm text-gray-600 mb-2">
              {summary.podcast_title}
            </p>
            <p className="text-xs text-gray-500">
              {summary.completed_at
                ? formatDate(summary.completed_at)
                : formatDate(summary.created_at)}
            </p>
          </div>

          {/* Main Topics */}
          {Array.isArray(summary.summary.main_topics) &&
            summary.summary.main_topics.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">
                  Main Topics:
                </h4>
                <div className="flex flex-wrap gap-2">
                  {summary.summary.main_topics.map((topic, index) => (
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
          {Array.isArray(summary.summary.key_points) &&
            summary.summary.key_points.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">
                  Key Points:
                </h4>
                <ul className="list-disc list-inside space-y-1">
                  {summary.summary.key_points.map((point, index) => (
                    <li key={index} className="text-sm text-gray-700">
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
            )}

          {/* Notable Quotes */}
          {Array.isArray(summary.summary.notable_quotes) &&
            summary.summary.notable_quotes.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">
                  Notable Quotes:
                </h4>
                <div className="space-y-2">
                  {summary.summary.notable_quotes.map((quote, index) => (
                    <blockquote
                      key={index}
                      className="border-l-4 border-gray-300 pl-3 italic text-sm text-gray-600"
                    >
                      "{quote}"
                    </blockquote>
                  ))}
                </div>
              </div>
            )}

          {/* Conclusion */}
          {summary.summary.conclusion && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">
                Conclusion:
              </h4>
              <p className="text-sm text-gray-700">
                {renderConclusion(summary.summary.conclusion)}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
