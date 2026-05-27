import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle, XCircle, Loader2, Mail } from "lucide-react";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import { createHttpError, parseErrorResponse } from "../lib/httpError";

const API_BASE_URL = import.meta.env.VITE_API_URL || "";

interface VerificationState {
  status: "loading" | "success" | "error" | "invalid";
  message: string;
}

export default function EmailVerification() {
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<VerificationState>({
    status: "loading",
    message: "Verifying your email...",
  });

  const token = searchParams.get("token");
  const email = searchParams.get("email");

  useEffect(() => {
    const verifyEmail = async () => {
      if (!token || !email) {
        setState({
          status: "invalid",
          message:
            "Invalid verification link. Please check your email and try again.",
        });
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/auth/verify-email`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ token, email }),
          },
        );

        if (response.ok) {
          setState({
            status: "success",
            message:
              "Your email has been verified successfully! You can now sign in.",
          });
        } else {
          const { message, code } = await parseErrorResponse(
            response,
            "Verification failed",
          );
          const error = createHttpError(message, response.status, code);
          setState({
            status: "error",
            message: getFriendlyErrorMessage(error),
          });
        }
      } catch (err) {
        setState({
          status: "error",
          message: getFriendlyErrorMessage(err),
        });
      }
    };

    verifyEmail();
  }, [token, email]);

  const handleGoToLogin = () => {
    window.location.href = "/login";
  };

  const handleResendVerification = () => {
    window.location.href = "/register";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
          {/* Icon */}
          <div className="mb-6">
            {state.status === "loading" && (
              <div className="w-16 h-16 mx-auto bg-blue-100 rounded-full flex items-center justify-center">
                <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
              </div>
            )}
            {state.status === "success" && (
              <div className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center">
                <CheckCircle className="h-8 w-8 text-green-600" />
              </div>
            )}
            {(state.status === "error" || state.status === "invalid") && (
              <div className="w-16 h-16 mx-auto bg-red-100 rounded-full flex items-center justify-center">
                <XCircle className="h-8 w-8 text-red-600" />
              </div>
            )}
          </div>

          {/* Title */}
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            {state.status === "loading" && "Verifying Email"}
            {state.status === "success" && "Email Verified!"}
            {state.status === "error" && "Verification Failed"}
            {state.status === "invalid" && "Invalid Link"}
          </h1>

          {/* Message */}
          <p className="text-gray-600 mb-8">{state.message}</p>

          {/* Actions */}
          <div className="space-y-3">
            {state.status === "success" && (
              <button
                onClick={handleGoToLogin}
                className="w-full px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transform hover:scale-[1.02] transition-all duration-200"
              >
                Go to Sign In
              </button>
            )}

            {(state.status === "error" || state.status === "invalid") && (
              <>
                <button
                  onClick={handleResendVerification}
                  className="w-full px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transform hover:scale-[1.02] transition-all duration-200 flex items-center justify-center gap-2"
                >
                  <Mail className="h-5 w-5" />
                  Request New Verification
                </button>
                <button
                  onClick={handleGoToLogin}
                  className="w-full px-6 py-3 bg-gray-100 text-gray-700 font-semibold rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Back to Sign In
                </button>
              </>
            )}
          </div>

          {/* Help text */}
          {state.status === "loading" && (
            <p className="mt-6 text-sm text-gray-500">
              Please wait while we verify your email address...
            </p>
          )}

          {email && state.status !== "loading" && (
            <p className="mt-6 text-sm text-gray-500">
              Email: <span className="font-medium">{email}</span>
            </p>
          )}
        </div>

        {/* Footer link */}
        <p className="text-center mt-6 text-sm text-gray-500">
          Need help?{" "}
          <a
            href="mailto:support@podquiz.io"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Contact Support
          </a>
        </p>
      </div>
    </div>
  );
}
