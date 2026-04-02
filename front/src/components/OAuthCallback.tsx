import { useEffect, useState } from "react";
import { Loader2, CheckCircle, XCircle } from "lucide-react";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { createHttpError, parseErrorResponse } from "../lib/httpError";

// When VITE_API_URL is empty, use relative URLs (for Vite proxy)
// Otherwise use the full URL (for production)
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

interface OAuthCallbackProps {
  onSuccess: (token: string) => void;
}

export default function OAuthCallback({ onSuccess }: OAuthCallbackProps) {
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [message, setMessage] = useState<string>("Finalizing connection...");
  const [provider, setProvider] = useState<string>("");

  useEffect(() => {
    const handleCallback = async () => {
      try {
        console.log("[OAuthCallback] Starting callback handling");
        console.log("[OAuthCallback] Current URL:", window.location.href);

        // Parse URL parameters
        const params = new URLSearchParams(window.location.search);
        const callbackProvider = params.get("provider") || "unknown";
        const reason = params.get("reason");

        console.log("[OAuthCallback] Provider:", callbackProvider);
        console.log("[OAuthCallback] Reason:", reason);

        setProvider(callbackProvider);

        // Check if this is an error callback
        if (window.location.pathname.includes("/auth/callback-error")) {
          console.log("[OAuthCallback] Error callback detected");
          setStatus("error");
          setMessage(getErrorMessage(reason || "unknown_error"));
          return;
        }

        // Success callback - exchange refresh token for access token
        if (window.location.pathname.includes("/auth/callback-success")) {
          console.log("[OAuthCallback] Success callback detected");
          setMessage("Retrieving your session...");

          // The refresh token should be in an httpOnly cookie
          // We need to call the backend to exchange it for an access token
          console.log("[OAuthCallback] Calling refresh endpoint...");
          const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
            method: "POST",
            credentials: "include", // Important: include cookies
            headers: {
              "Content-Type": "application/json",
            },
          });

          console.log(
            "[OAuthCallback] Refresh response status:",
            response.status,
          );

          if (!response.ok) {
            const { message, code } = await parseErrorResponse(
              response,
              "Failed to exchange refresh token",
            );
            console.error("[OAuthCallback] Refresh failed:", message);
            throw createHttpError(message, response.status, code);
          }

          const data = await response.json();
          console.log("[OAuthCallback] Received access token");
          const accessToken = data.access_token;
          const expiresIn = data.expires_in || 3600;

          // Save token to localStorage
          localStorage.setItem("access_token", accessToken);
          const expiryTime = Date.now() + expiresIn * 1000;
          localStorage.setItem("token_expiry", expiryTime.toString());
          console.log("[OAuthCallback] Token saved to localStorage");

          setStatus("success");
          setMessage("Connection successful! Redirecting...");

          // Redirect to dashboard immediately - don't wait
          console.log("[OAuthCallback] Calling onSuccess callback");
          // Clean up URL first
          window.history.replaceState({}, document.title, "/");
          // Then trigger the redirect
          onSuccess(accessToken);
        }
      } catch (error) {
        console.error("[OAuthCallback] Error:", error);
        setStatus("error");
        setMessage(
          `Error: ${getFriendlyErrorMessage(error, {
            fallback: "An error occurred during connection",
          })}`,
        );
      }
    };

    handleCallback();
  }, [onSuccess]);

  const getErrorMessage = (reason: string): string => {
    const errorMessages: Record<string, string> = {
      state_mismatch: "Security error: invalid state",
      missing_code: "Missing authorization code",
      no_id_token: "Missing identification token",
      invalid_audience_or_issuer: "Invalid token",
      invalid_claims: "Invalid credentials",
      http_error: "Server communication error",
      server_error: "Server error",
      unknown_error: "An unknown error occurred",
    };

    return errorMessages[reason] || errorMessages.unknown_error;
  };

  const getProviderName = (provider: string): string => {
    const providers: Record<string, string> = {
      google: "Google",
      apple: "Apple",
    };
    return providers[provider] || provider;
  };

  const handleRetry = () => {
    window.history.replaceState({}, document.title, "/");
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 md:p-12 max-w-md w-full">
        <div className="text-center space-y-6">
          {/* Icon */}
          <div className="flex justify-center">
            {status === "loading" && (
              <div className="inline-flex items-center justify-center w-20 h-20 bg-blue-100 rounded-full">
                <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
              </div>
            )}
            {status === "success" && (
              <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full">
                <CheckCircle className="w-10 h-10 text-green-600" />
              </div>
            )}
            {status === "error" && (
              <div className="inline-flex items-center justify-center w-20 h-20 bg-red-100 rounded-full">
                <XCircle className="w-10 h-10 text-red-600" />
              </div>
            )}
          </div>

          {/* Title */}
          <div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              {status === "loading" && "Connecting..."}
              {status === "success" && "Connection successful!"}
              {status === "error" && "Connection error"}
            </h1>
            {provider && (
              <p className="text-sm text-gray-600">
                via {getProviderName(provider)}
              </p>
            )}
          </div>

          {/* Message */}
          <p className="text-gray-600">{message}</p>

          {/* Retry button for errors */}
          {status === "error" && (
            <button
              onClick={handleRetry}
              className="w-full px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
            >
              Back to login
            </button>
          )}

          {/* Loading indicator */}
          {status === "loading" && (
            <div className="flex items-center justify-center space-x-2 text-sm text-gray-500">
              <div
                className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"
                style={{ animationDelay: "0ms" }}
              ></div>
              <div
                className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"
                style={{ animationDelay: "150ms" }}
              ></div>
              <div
                className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"
                style={{ animationDelay: "300ms" }}
              ></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
