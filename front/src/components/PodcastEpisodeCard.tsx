import { useState } from "react";
import { PodcastEpisode } from "../types/podcast";
import {
  Calendar,
  Clock,
  Mic,
  Sparkles,
  Loader2,
  Check,
  CreditCard,
} from "lucide-react";
import { PodcastService, ServiceError } from "../services/podcastService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";

interface PodcastEpisodeCardProps {
  episode: PodcastEpisode;
  token: string;
  onClick?: (episode: PodcastEpisode) => void;
  onSubmitSuccess?: (jobId: string) => void;
  onShowPricing?: () => void;
}

export default function PodcastEpisodeCard({
  episode,
  token,
  onClick,
  onSubmitSuccess,
  onShowPricing,
}: PodcastEpisodeCardProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<
    "idle" | "success" | "error"
  >("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCreditError, setIsCreditError] = useState(false);

  const formatDate = (timestamp: number) => {
    if (!timestamp) return "";
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return null;
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}min`;
    }
    return `${minutes} min`;
  };

  const handleSubmit = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click

    if (isCreditError) {
      // Redirect to pricing/account to recharge
      if (onShowPricing) {
        onShowPricing();
      } else {
        window.location.hash = "#pricing";
      }
      return;
    }

    if (!episode.feed_id || !episode.guid) {
      setErrorMessage("Missing episode information");
      setSubmitStatus("error");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setIsCreditError(false);

    try {
      const response = await PodcastService.submitEpisode(
        episode.feed_id,
        episode.guid,
        token,
      );

      setSubmitStatus("success");

      if (onSubmitSuccess && response.job_id) {
        onSubmitSuccess(response.job_id);
      }

      // Reset success state after 3 seconds
      setTimeout(() => {
        setSubmitStatus("idle");
      }, 3000);
    } catch (error) {
      setSubmitStatus("error");
      const is402 = error instanceof ServiceError && error.status === 402;
      setIsCreditError(is402);

      setErrorMessage(
        getFriendlyErrorMessage(error, {
          fallback: "Failed to submit episode",
        }),
      );

      // Reset error state after 8 seconds if it's a credit error to give time to read/click
      setTimeout(
        () => {
          setSubmitStatus("idle");
          setErrorMessage(null);
          setIsCreditError(false);
        },
        is402 ? 30000 : 5000,
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className={`bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow flex flex-row min-h-[128px] ${onClick ? "cursor-pointer" : ""}`}
      onClick={() => onClick?.(episode)}
    >
      {/* Thumbnail - fixed width */}
      <div className="w-32 flex-shrink-0 relative bg-gray-100 dark:bg-gray-700">
        {episode.image || episode.feed_image ? (
          <img
            src={episode.image || episode.feed_image}
            alt={episode.title}
            className="w-full h-full object-cover"
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              target.src =
                "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='%23e5e7eb'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='16' fill='%239ca3af'%3ENo Image%3C/text%3E%3C/svg%3E";
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Mic className="h-10 w-10 text-gray-400 dark:text-gray-500" />
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 p-3 flex flex-col min-w-0">
        <div className="min-w-0 mb-2">
          <h3 className="font-semibold text-gray-900 dark:text-white text-sm mb-1 line-clamp-2 leading-tight">
            {episode.title}
          </h3>

          <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
            {episode.date_published > 0 && (
              <div className="flex items-center gap-1">
                <Calendar className="h-3 w-3 flex-shrink-0" />
                <span className="truncate">
                  {formatDate(episode.date_published)}
                </span>
              </div>
            )}
            {formatDuration(episode.duration) && (
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3 flex-shrink-0" />
                <span>{formatDuration(episode.duration)}</span>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-1.5 mt-auto">
          {/* Error Message (Top) - only for credit errors */}
          {isCreditError && errorMessage && (
            <p className="text-xs font-semibold leading-tight text-amber-600 dark:text-amber-400 text-center truncate">
              {errorMessage}
            </p>
          )}

          {/* Get Quiz & Summary Button */}
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || submitStatus === "success"}
            className={`w-full px-3 py-1.5 rounded-md font-medium text-xs transition-all duration-200 flex items-center justify-center gap-1.5 ${
              submitStatus === "success"
                ? "bg-green-500 text-white cursor-default"
                : submitStatus === "error"
                  ? isCreditError
                    ? "bg-amber-500 hover:bg-amber-600 text-white"
                    : "bg-red-500 hover:bg-red-600 text-white"
                  : isSubmitting
                    ? "bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-wait"
                    : "bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white shadow-sm hover:shadow-md"
            }`}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Submitting...</span>
              </>
            ) : submitStatus === "success" ? (
              <>
                <Check className="h-3.5 w-3.5" />
                <span>Submitted!</span>
              </>
            ) : isCreditError ? (
              <>
                <CreditCard className="h-3.5 w-3.5" />
                <span>Recharge</span>
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5" />
                <span>Get Quiz & Summary</span>
              </>
            )}
          </button>

          {/* Error Message (Bottom) - for other errors */}
          {!isCreditError && errorMessage && (
            <p className="text-[10px] leading-tight text-red-500 dark:text-red-400 text-center truncate">
              {errorMessage}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
