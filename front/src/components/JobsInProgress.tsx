import { useState, useEffect, useCallback } from 'react';
import { Loader2, CheckCircle, XCircle, Download, FileAudio, FileText, Clock, RefreshCw } from 'lucide-react';
import { createHttpError, parseErrorResponse } from '../lib/httpError';
import { getFriendlyErrorMessage } from '../lib/getFriendlyErrorMessage';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

interface Job {
  job_id: string;
  user_id: string;
  episode_title?: string;
  podcast_title?: string;
  status: 'pending' | 'downloading' | 'transcribing' | 'summarizing' | 'completed' | 'failed';
  created_at: string;
  updated_at?: string;
  error_message?: string;
  minutes_charged?: number;
}

interface JobsInProgressProps {
  token: string;
  onJobCompleted?: () => void;
}

const STATUS_CONFIG = {
  pending: {
    label: 'Pending',
    icon: Clock,
    color: 'text-gray-500',
    bgColor: 'bg-gray-100',
    progress: 0,
  },
  downloading: {
    label: 'Downloading Audio',
    icon: Download,
    color: 'text-blue-500',
    bgColor: 'bg-blue-100',
    progress: 25,
  },
  transcribing: {
    label: 'Transcribing',
    icon: FileAudio,
    color: 'text-purple-500',
    bgColor: 'bg-purple-100',
    progress: 50,
  },
  summarizing: {
    label: 'Generating Summary & Quiz',
    icon: FileText,
    color: 'text-indigo-500',
    bgColor: 'bg-indigo-100',
    progress: 75,
  },
  completed: {
    label: 'Completed',
    icon: CheckCircle,
    color: 'text-green-500',
    bgColor: 'bg-green-100',
    progress: 100,
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    color: 'text-red-500',
    bgColor: 'bg-red-100',
    progress: 0,
  },
};

export default function JobsInProgress({ token, onJobCompleted }: JobsInProgressProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/jobs/me`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const { message, code } = await parseErrorResponse(
          response,
          'Failed to fetch jobs',
        );
        throw createHttpError(message, response.status, code);
      }

      const data = await response.json();
      const jobsList = Array.isArray(data) ? data : data.jobs || [];

      // Check if any job just completed
      const previousPendingJobs = jobs.filter(j => j.status !== 'completed' && j.status !== 'failed');
      const newCompletedJobs = jobsList.filter(
        (j: Job) => j.status === 'completed' && previousPendingJobs.some(pj => pj.job_id === j.job_id)
      );

      if (newCompletedJobs.length > 0 && onJobCompleted) {
        onJobCompleted();
      }

      setJobs(jobsList);
      setError(null);
    } catch (err) {
      setError(getFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [token, jobs, onJobCompleted]);

  useEffect(() => {
    fetchJobs();

    // Poll every 10 seconds for active jobs
    const interval = setInterval(() => {
      fetchJobs();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  // Re-fetch when token changes
  useEffect(() => {
    fetchJobs();
  }, [token]);

  const activeJobs = jobs.filter(j => j.status !== 'completed' && j.status !== 'failed');
  const recentCompletedJobs = jobs
    .filter(j => j.status === 'completed' || j.status === 'failed')
    .slice(0, 3);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 text-center">
        <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
        <button
          onClick={fetchJobs}
          className="mt-2 text-sm text-red-600 dark:text-red-400 hover:underline flex items-center gap-1 mx-auto"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      </div>
    );
  }

  if (activeJobs.length === 0 && recentCompletedJobs.length === 0) {
    return null; // Don't show section if no jobs
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
          Processing Queue
        </h2>
        <button
          onClick={fetchJobs}
          className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Active Jobs */}
      {activeJobs.length > 0 && (
        <div className="space-y-4 mb-6">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
            In Progress ({activeJobs.length})
          </h3>
          {activeJobs.map((job) => (
            <JobCard key={job.job_id} job={job} />
          ))}
        </div>
      )}

      {/* Recent Completed Jobs */}
      {recentCompletedJobs.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
            Recently Completed
          </h3>
          {recentCompletedJobs.map((job) => (
            <JobCard key={job.job_id} job={job} compact />
          ))}
        </div>
      )}
    </div>
  );
}

interface JobCardProps {
  job: Job;
  compact?: boolean;
}

function JobCard({ job, compact = false }: JobCardProps) {
  const config = STATUS_CONFIG[job.status] || STATUS_CONFIG.pending;
  const StatusIcon = config.icon;

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className={`rounded-lg border ${job.status === 'failed' ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20' : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50'} p-4`}>
      <div className="flex items-start gap-3">
        {/* Status Icon */}
        <div className={`p-2 rounded-full ${config.bgColor} dark:bg-opacity-30`}>
          <StatusIcon className={`h-4 w-4 ${config.color}`} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-medium text-gray-900 dark:text-white text-sm truncate">
              {job.episode_title || 'Processing Episode...'}
            </h4>
            <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
              {formatTime(job.created_at)}
            </span>
          </div>

          {job.podcast_title && (
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
              {job.podcast_title}
            </p>
          )}

          {!compact && job.status !== 'completed' && job.status !== 'failed' && (
            <>
              {/* Progress Bar */}
              <div className="mt-3 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500 ease-out"
                  style={{ width: `${config.progress}%` }}
                />
              </div>

              {/* Status Label */}
              <p className={`mt-2 text-xs font-medium ${config.color}`}>
                {config.label}
                {job.status !== 'pending' && (
                  <Loader2 className="inline-block h-3 w-3 ml-1 animate-spin" />
                )}
              </p>
            </>
          )}

          {job.status === 'failed' && job.error_message && (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              {getFriendlyErrorMessage(job.error_message)}
            </p>
          )}

          {job.status === 'completed' && job.minutes_charged !== undefined && (
            <p className="mt-1 text-xs text-green-600 dark:text-green-400">
              ✓ Used {job.minutes_charged} minutes
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
