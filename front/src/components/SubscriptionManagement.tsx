import { useState, useEffect } from "react";
import { ArrowLeft, CreditCard, Loader2, AlertCircle, Calendar } from "lucide-react";
import { SettingsService, SubscriptionInfo } from "../services/settingsService";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";

interface SubscriptionManagementProps {
    token: string;
    onBack: () => void;
}

export default function SubscriptionManagement({
    token,
    onBack,
}: SubscriptionManagementProps) {
    const [subscriptionInfo, setSubscriptionInfo] =
        useState<SubscriptionInfo | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isCancelling, setIsCancelling] = useState(false);
    const [showCancelConfirm, setShowCancelConfirm] = useState(false);
    const [cancelSuccess, setCancelSuccess] = useState(false);

    useEffect(() => {
        loadSubscriptionInfo();
    }, []);

    const loadSubscriptionInfo = async () => {
        setIsLoading(true);
        setError(null);

        try {
            const info = await SettingsService.getSubscriptionInfo(token);
            setSubscriptionInfo(info);
        } catch (err) {
            setError(getFriendlyErrorMessage(err));
        } finally {
            setIsLoading(false);
        }
    };

    const handleCancelSubscription = async () => {
        setIsCancelling(true);
        setError(null);

        try {
            await SettingsService.cancelSubscription(token);
            setCancelSuccess(true);
            setShowCancelConfirm(false);
            // Reload subscription info to show updated status
            await loadSubscriptionInfo();
        } catch (err) {
            setError(getFriendlyErrorMessage(err));
        } finally {
            setIsCancelling(false);
        }
    };

    const getTierName = (tier: string) => {
        const tierNames: Record<string, string> = {
            S: "Starter",
            M: "Medium",
            L: "Large",
        };
        return tierNames[tier] || tier;
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case "active":
                return "bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800";
            case "canceled":
                return "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800";
            default:
                return "bg-gray-100 dark:bg-gray-900/30 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-800";
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
                    Subscription Management
                </h1>
                <p className="text-gray-600 dark:text-gray-400">
                    View and manage your subscription plan
                </p>
            </div>

            {/* Content */}
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                    </div>
                ) : error ? (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
                        <div className="flex items-center space-x-3">
                            <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                            <p className="text-red-800 dark:text-red-300">{error}</p>
                        </div>
                    </div>
                ) : subscriptionInfo ? (
                    <div className="space-y-6">
                        {/* Success Message */}
                        {cancelSuccess && (
                            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                                <p className="text-green-800 dark:text-green-300 text-sm">
                                    Your subscription has been scheduled for cancellation at the end
                                    of the current billing period.
                                </p>
                            </div>
                        )}

                        {/* Subscription Status */}
                        {subscriptionInfo.subscription ? (
                            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                                <div className="flex items-center justify-between mb-6">
                                    <div className="flex items-center space-x-3">
                                        <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 flex items-center justify-center">
                                            <CreditCard className="h-5 w-5 text-white" />
                                        </div>
                                        <div>
                                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                                                Current Plan: {getTierName(subscriptionInfo.subscription.tier)}
                                            </h2>
                                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                                {subscriptionInfo.subscription.minutes_per_period} minutes per month
                                            </p>
                                        </div>
                                    </div>
                                    <span
                                        className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(subscriptionInfo.subscription.status)}`}
                                    >
                                        {subscriptionInfo.subscription.status}
                                    </span>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                                    <div className="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                                            Current Period
                                        </p>
                                        <div className="flex items-center space-x-2">
                                            <Calendar className="h-4 w-4 text-gray-400" />
                                            <p className="text-sm font-medium text-gray-900 dark:text-white">
                                                {subscriptionInfo.subscription.current_period_start &&
                                                    subscriptionInfo.subscription.current_period_end
                                                    ? `${new Date(subscriptionInfo.subscription.current_period_start).toLocaleDateString()} - ${new Date(subscriptionInfo.subscription.current_period_end).toLocaleDateString()}`
                                                    : "N/A"}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                                            Minutes Remaining
                                        </p>
                                        <p className="text-2xl font-bold text-gray-900 dark:text-white">
                                            {subscriptionInfo.minutes.total_free}
                                        </p>
                                        <p className="text-xs text-gray-500 dark:text-gray-400">
                                            {subscriptionInfo.minutes.by_source.subscription} from
                                            subscription
                                        </p>
                                    </div>
                                </div>

                                {subscriptionInfo.subscription.cancel_at_period_end ? (
                                    <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
                                        <p className="text-sm text-yellow-800 dark:text-yellow-300">
                                            <strong>Scheduled for Cancellation:</strong> Your subscription
                                            will end on{" "}
                                            {subscriptionInfo.subscription.current_period_end &&
                                                new Date(
                                                    subscriptionInfo.subscription.current_period_end,
                                                ).toLocaleDateString()}
                                            . You'll retain access until then.
                                        </p>
                                    </div>
                                ) : (
                                    <div>
                                        {!showCancelConfirm ? (
                                            <button
                                                onClick={() => setShowCancelConfirm(true)}
                                                className="px-6 py-2 bg-red-600 text-white font-semibold rounded-lg shadow-sm hover:bg-red-700 transition-colors"
                                            >
                                                Cancel Subscription
                                            </button>
                                        ) : (
                                            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 space-y-4">
                                                <p className="text-sm text-red-800 dark:text-red-300">
                                                    Are you sure you want to cancel your subscription? You'll
                                                    keep access until the end of your current billing period.
                                                </p>
                                                <div className="flex space-x-3">
                                                    <button
                                                        onClick={handleCancelSubscription}
                                                        disabled={isCancelling}
                                                        className="px-4 py-2 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                                                    >
                                                        {isCancelling && (
                                                            <Loader2 className="h-4 w-4 animate-spin" />
                                                        )}
                                                        <span>
                                                            {isCancelling ? "Cancelling..." : "Yes, Cancel"}
                                                        </span>
                                                    </button>
                                                    <button
                                                        onClick={() => setShowCancelConfirm(false)}
                                                        disabled={isCancelling}
                                                        className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white font-semibold rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50"
                                                    >
                                                        Keep Subscription
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                                <p className="text-gray-600 dark:text-gray-400">
                                    No active subscription found. Visit the billing section to
                                    subscribe to a plan.
                                </p>
                            </div>
                        )}

                        {/* Minutes Breakdown */}
                        {subscriptionInfo.minutes.total_free > 0 && (
                            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                                    Minutes Breakdown
                                </h3>
                                <div className="space-y-3">
                                    {subscriptionInfo.minutes.by_source.subscription > 0 && (
                                        <div className="flex justify-between items-center">
                                            <span className="text-sm text-gray-600 dark:text-gray-400">
                                                Subscription
                                            </span>
                                            <span className="text-sm font-medium text-gray-900 dark:text-white">
                                                {subscriptionInfo.minutes.by_source.subscription} min
                                            </span>
                                        </div>
                                    )}
                                    {subscriptionInfo.minutes.by_source.packs > 0 && (
                                        <div className="flex justify-between items-center">
                                            <span className="text-sm text-gray-600 dark:text-gray-400">
                                                Packs
                                            </span>
                                            <span className="text-sm font-medium text-gray-900 dark:text-white">
                                                {subscriptionInfo.minutes.by_source.packs} min
                                            </span>
                                        </div>
                                    )}
                                    {subscriptionInfo.minutes.by_source.rollover > 0 && (
                                        <div className="flex justify-between items-center">
                                            <span className="text-sm text-gray-600 dark:text-gray-400">
                                                Rollover
                                            </span>
                                            <span className="text-sm font-medium text-gray-900 dark:text-white">
                                                {subscriptionInfo.minutes.by_source.rollover} min
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                ) : null}
            </div>
        </div>
    );
}
