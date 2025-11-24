import { useState } from "react";
import { ArrowLeft, CreditCard, Loader2, ExternalLink } from "lucide-react";
import { SettingsService } from "../services/settingsService";

interface PaymentMethodsProps {
    token: string;
    onBack: () => void;
}

export default function PaymentMethods({ token, onBack }: PaymentMethodsProps) {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleOpenPortal = async () => {
        setIsLoading(true);
        setError(null);

        try {
            const { url } = await SettingsService.createPortalSession(token);
            // Redirect to Stripe Customer Portal
            window.location.href = url;
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to open payment portal",
            );
            setIsLoading(false);
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
                    Payment Methods
                </h1>
                <p className="text-gray-600 dark:text-gray-400">
                    Manage your payment methods and billing information
                </p>
            </div>

            {/* Content */}
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                    <div className="flex items-center space-x-3 mb-6">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 flex items-center justify-center">
                            <CreditCard className="h-5 w-5 text-white" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                                Stripe Customer Portal
                            </h2>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                Manage your payment methods securely with Stripe
                            </p>
                        </div>
                    </div>

                    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
                        <p className="text-sm text-blue-800 dark:text-blue-300">
                            You'll be redirected to Stripe's secure portal where you can:
                        </p>
                        <ul className="mt-2 space-y-1 text-sm text-blue-700 dark:text-blue-300 list-disc list-inside">
                            <li>Add or remove payment methods</li>
                            <li>Update billing information</li>
                            <li>View payment history</li>
                            <li>Download invoices</li>
                        </ul>
                    </div>

                    {error && (
                        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                            <p className="text-sm text-red-800 dark:text-red-300">{error}</p>
                        </div>
                    )}

                    <button
                        onClick={handleOpenPortal}
                        disabled={isLoading}
                        className="w-full sm:w-auto px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-lg shadow-sm hover:shadow-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="h-5 w-5 animate-spin" />
                                <span>Opening Portal...</span>
                            </>
                        ) : (
                            <>
                                <span>Open Payment Portal</span>
                                <ExternalLink className="h-5 w-5" />
                            </>
                        )}
                    </button>

                    <p className="mt-4 text-xs text-gray-500 dark:text-gray-400">
                        You'll be returned to this page after managing your payment methods.
                    </p>
                </div>
            </div>
        </div>
    );
}
