import { Clock } from "lucide-react";
import { useState, useEffect } from "react";

interface MinutesDisplayProps {
    minutes: number;
    loading?: boolean;
}

export default function MinutesDisplay({ minutes, loading = false }: MinutesDisplayProps) {
    const [isAnimating, setIsAnimating] = useState(false);

    // Animate when minutes change
    useEffect(() => {
        setIsAnimating(true);
        const timer = setTimeout(() => setIsAnimating(false), 300);
        return () => clearTimeout(timer);
    }, [minutes]);

    // Format minutes for display
    const formatMinutes = (mins: number): string => {
        if (mins >= 1000) {
            return `${(mins / 1000).toFixed(1)}k`;
        }
        return mins.toString();
    };

    return (
        <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border border-blue-200 dark:border-purple-800/50">
            <Clock className="h-3.5 w-3.5 text-blue-600 dark:text-purple-400" />
            <span
                className={`text-xs font-semibold text-blue-700 dark:text-purple-400 transition-all duration-300 ${isAnimating ? "scale-110" : "scale-100"
                    }`}
            >
                {loading ? (
                    <span className="inline-block w-12 h-3 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                ) : (
                    `${formatMinutes(minutes)} min`
                )}
            </span>
        </div>
    );
}
