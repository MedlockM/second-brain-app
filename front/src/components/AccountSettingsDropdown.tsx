import { User, Settings, CreditCard, LogOut } from "lucide-react";
import { useState, useRef, useEffect } from "react";

interface AccountSettingsDropdownProps {
    onNavigate: (page: "account" | "subscription" | "payment") => void;
    onLogout: () => void;
    userEmail: string;
}

export default function AccountSettingsDropdown({
    onNavigate,
    onLogout,
    userEmail,
}: AccountSettingsDropdownProps) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (
                dropdownRef.current &&
                !dropdownRef.current.contains(event.target as Node)
            ) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener("mousedown", handleClickOutside);
        }

        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [isOpen]);

    const handleNavigate = (page: "account" | "subscription" | "payment") => {
        setIsOpen(false);
        onNavigate(page);
    };

    const handleLogout = () => {
        setIsOpen(false);
        onLogout();
    };

    return (
        <div className="relative" ref={dropdownRef}>
            {/* Profile Icon Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center space-x-2 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Account settings"
            >
                <div className="w-8 h-8 rounded-full bg-gradient-to-r from-blue-600 to-purple-600 flex items-center justify-center">
                    <User className="h-5 w-5 text-white" />
                </div>
                <span className="text-sm text-gray-700 dark:text-gray-300 hidden sm:inline">
                    {userEmail}
                </span>
            </button>

            {/* Dropdown Menu */}
            {isOpen && (
                <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 z-50 overflow-hidden">
                    {/* Header */}
                    <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-gray-900 dark:to-gray-900">
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                            Signed in as
                        </p>
                        <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                            {userEmail}
                        </p>
                    </div>

                    {/* Menu Items */}
                    <div className="py-2">
                        <button
                            onClick={() => handleNavigate("account")}
                            className="w-full flex items-center space-x-3 px-4 py-3 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                        >
                            <Settings className="h-4 w-4 text-gray-500" />
                            <span>Account Settings</span>
                        </button>

                        <button
                            onClick={() => handleNavigate("subscription")}
                            className="w-full flex items-center space-x-3 px-4 py-3 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                        >
                            <CreditCard className="h-4 w-4 text-gray-500" />
                            <span>Subscription</span>
                        </button>

                        <button
                            onClick={() => handleNavigate("payment")}
                            className="w-full flex items-center space-x-3 px-4 py-3 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                        >
                            <CreditCard className="h-4 w-4 text-gray-500" />
                            <span>Payment Methods</span>
                        </button>
                    </div>

                    {/* Logout */}
                    <div className="border-t border-gray-200 dark:border-gray-700 py-2">
                        <button
                            onClick={handleLogout}
                            className="w-full flex items-center space-x-3 px-4 py-3 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                        >
                            <LogOut className="h-4 w-4" />
                            <span>Logout</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
