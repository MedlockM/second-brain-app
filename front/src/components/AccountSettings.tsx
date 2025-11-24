import { useState } from "react";
import { ArrowLeft, Mail, Loader2, CheckCircle, Music } from "lucide-react";
import { SettingsService } from "../services/settingsService";
import { SpotifyService } from "../services/spotifyService";

interface AccountSettingsProps {
    token: string;
    userEmail: string;
    userId: string;
    onBack: () => void;
}

export default function AccountSettings({
    token,
    userEmail,
    userId,
    onBack,
}: AccountSettingsProps) {
    const [newEmail, setNewEmail] = useState(userEmail);
    const [isUpdatingEmail, setIsUpdatingEmail] = useState(false);
    const [emailSuccess, setEmailSuccess] = useState(false);
    const [emailError, setEmailError] = useState<string | null>(null);

    const [spotifyLinked, setSpotifyLinked] = useState(false);
    const [spotifyUserId, setSpotifyUserId] = useState<string | null>(null);
    const [isCheckingSpotify, setIsCheckingSpotify] = useState(true);
    const [isUnlinkingSpotify, setIsUnlinkingSpotify] = useState(false);
    const [spotifyError, setSpotifyError] = useState<string | null>(null);

    // Check Spotify status on mount
    useState(() => {
        const checkSpotify = async () => {
            try {
                const status = await SpotifyService.checkStatus(token);
                setSpotifyLinked(status.linked);
                setSpotifyUserId(status.spotify_user_id || null);
            } catch (error) {
                console.error("Failed to check Spotify status:", error);
            } finally {
                setIsCheckingSpotify(false);
            }
        };
        checkSpotify();
    });

    const handleUpdateEmail = async (e: React.FormEvent) => {
        e.preventDefault();
        if (newEmail === userEmail) return;

        setIsUpdatingEmail(true);
        setEmailError(null);
        setEmailSuccess(false);

        try {
            await SettingsService.updateEmail(userId, newEmail, token);
            setEmailSuccess(true);
            setTimeout(() => setEmailSuccess(false), 3000);
        } catch (error) {
            setEmailError(
                error instanceof Error ? error.message : "Failed to update email",
            );
        } finally {
            setIsUpdatingEmail(false);
        }
    };

    const handleUnlinkSpotify = async () => {
        setIsUnlinkingSpotify(true);
        setSpotifyError(null);

        try {
            await SettingsService.unlinkSpotify(token);
            setSpotifyLinked(false);
            setSpotifyUserId(null);
        } catch (error) {
            setSpotifyError(
                error instanceof Error ? error.message : "Failed to unlink Spotify",
            );
        } finally {
            setIsUnlinkingSpotify(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-950 dark:to-black">
            {/* Header */}
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <button
                    onClick={onBack}
                    className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white mb-6 transition-colors"
                >
                    <ArrowLeft className="h-5 w-5" />
                    <span>Back to Dashboard</span>
                </button>

                <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
                    Account Settings
                </h1>
                <p className="text-gray-600 dark:text-gray-400">
                    Manage your account preferences and linked services
                </p>
            </div>

            {/* Content */}
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
                <div className="space-y-6">
                    {/* Email Settings */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                        <div className="flex items-center space-x-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 flex items-center justify-center">
                                <Mail className="h-5 w-5 text-white" />
                            </div>
                            <div>
                                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                                    Email Address
                                </h2>
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    Update the email where you receive quizzes and summaries
                                </p>
                            </div>
                        </div>

                        <form onSubmit={handleUpdateEmail} className="space-y-4">
                            <div>
                                <label
                                    htmlFor="email"
                                    className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
                                >
                                    Email
                                </label>
                                <input
                                    type="email"
                                    id="email"
                                    value={newEmail}
                                    onChange={(e) => setNewEmail(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    required
                                />
                            </div>

                            {emailError && (
                                <div className="text-sm text-red-600 dark:text-red-400">
                                    {emailError}
                                </div>
                            )}

                            {emailSuccess && (
                                <div className="flex items-center space-x-2 text-sm text-green-600 dark:text-green-400">
                                    <CheckCircle className="h-4 w-4" />
                                    <span>Email updated successfully!</span>
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={isUpdatingEmail || newEmail === userEmail}
                                className="px-6 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-lg shadow-sm hover:shadow-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                            >
                                {isUpdatingEmail && <Loader2 className="h-4 w-4 animate-spin" />}
                                <span>{isUpdatingEmail ? "Updating..." : "Update Email"}</span>
                            </button>
                        </form>
                    </div>

                    {/* Spotify Settings */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                        <div className="flex items-center space-x-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-green-600 flex items-center justify-center">
                                <Music className="h-5 w-5 text-white" />
                            </div>
                            <div>
                                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                                    Spotify Account
                                </h2>
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    Manage your linked Spotify account
                                </p>
                            </div>
                        </div>

                        {isCheckingSpotify ? (
                            <div className="flex items-center space-x-2 text-gray-600">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span className="text-sm">Checking Spotify status...</span>
                            </div>
                        ) : spotifyLinked ? (
                            <div className="space-y-4">
                                <div className="flex items-center justify-between p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                                    <div>
                                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                                            Connected
                                        </p>
                                        {spotifyUserId && (
                                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                                User ID: {spotifyUserId}
                                            </p>
                                        )}
                                    </div>
                                    <CheckCircle className="h-5 w-5 text-green-600" />
                                </div>

                                {spotifyError && (
                                    <div className="text-sm text-red-600 dark:text-red-400">
                                        {spotifyError}
                                    </div>
                                )}

                                <button
                                    onClick={handleUnlinkSpotify}
                                    disabled={isUnlinkingSpotify}
                                    className="px-6 py-2 bg-red-600 text-white font-semibold rounded-lg shadow-sm hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                                >
                                    {isUnlinkingSpotify && (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    )}
                                    <span>
                                        {isUnlinkingSpotify ? "Unlinking..." : "Unlink Account"}
                                    </span>
                                </button>
                            </div>
                        ) : (
                            <div className="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700">
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                    No Spotify account linked. Link your account from the dashboard
                                    to sync your podcast playlists.
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
