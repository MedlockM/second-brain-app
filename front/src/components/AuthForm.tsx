import { useEffect, useState } from "react";
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  Loader2,
  ArrowRight,
  CheckCircle,
  ArrowLeft,
} from "lucide-react";
import { AuthService, AUTH_ERROR_STORAGE_KEY } from "../services/authService";
import { AuthError } from "../types/auth";
import { getFriendlyErrorMessage } from "../lib/getFriendlyErrorMessage";
import {
  getEmailValidationError,
  getPasswordValidationError,
} from "../utils/validation";

interface AuthFormProps {
  onSuccess: (token: string) => void;
  initialMode?: FormMode;
}

type FormMode = "login" | "register";

export default function AuthForm({
  onSuccess,
  initialMode = "login",
}: AuthFormProps) {
  const [mode, setMode] = useState<FormMode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<AuthError | null>(null);
  const [registrationComplete, setRegistrationComplete] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState("");

  useEffect(() => {
    const storedCode = sessionStorage.getItem(AUTH_ERROR_STORAGE_KEY);
    if (!storedCode) {
      return;
    }
    sessionStorage.removeItem(AUTH_ERROR_STORAGE_KEY);
    setError({
      message: getFriendlyErrorMessage({ code: storedCode }),
      code: storedCode,
    });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate email before submission
    const emailError = getEmailValidationError(email);
    if (emailError) {
      setError({
        message: emailError,
      });
      return;
    }

    // Validate password
    const passwordError = getPasswordValidationError(password, 6);
    if (passwordError) {
      setError({
        message: passwordError,
      });
      return;
    }

    setLoading(true);

    try {
      if (mode === "login") {
        const response = await AuthService.login({ email, password });
        AuthService.saveToken(response.access_token, response.expires_in);
        onSuccess(response.access_token);
      } else {
        // Registration - email verification required
        await AuthService.register({ email, password });
        setRegisteredEmail(email);
        setRegistrationComplete(true);
      }
    } catch (err) {
      setError({
        message: getFriendlyErrorMessage(err),
        code: (err as { code?: string }).code,
      });
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setMode(mode === "login" ? "register" : "login");
    setError(null);
    setRegistrationComplete(false);
  };

  const handleBackToLogin = () => {
    setMode("login");
    setRegistrationComplete(false);
    setEmail(registeredEmail);
    setPassword("");
    setError(null);
  };

  const handleOAuthLogin = (provider: "google" | "apple") => {
    // When VITE_API_URL is empty, use relative URLs (for Vite proxy)
    const API_BASE_URL = import.meta.env.VITE_API_URL || "";
    window.location.href = `${API_BASE_URL}/api/v1/auth/${provider}/login`;
  };

  // Email verification confirmation screen
  if (registrationComplete) {
    return (
      <div className="w-full max-w-md relative">
        {/* Decorative Elements */}
        <div className="absolute -top-20 -left-20 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob pointer-events-none"></div>
        <div className="absolute -top-20 -right-20 w-72 h-72 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000 pointer-events-none"></div>
        <div className="absolute -bottom-20 left-1/2 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000 pointer-events-none"></div>

        <div className="bg-white rounded-2xl shadow-xl p-8 relative z-10">
          <div className="text-center">
            {/* Success Icon */}
            <div className="mx-auto w-16 h-16 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center mb-6">
              <Mail className="h-8 w-8 text-white" />
            </div>

            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Check your inbox
            </h1>

            <p className="text-gray-600 mb-6">
              We've sent a verification link to
            </p>

            <p className="text-lg font-semibold text-gray-900 bg-gray-100 rounded-lg py-3 px-4 mb-6">
              {registeredEmail}
            </p>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <div className="flex items-start">
                <CheckCircle className="h-5 w-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
                <p className="text-sm text-blue-800 text-left">
                  Click the link in the email to verify your address and
                  activate your account.
                </p>
              </div>
            </div>

            <p className="text-sm text-gray-500 mb-6">
              Didn't receive the email? Check your spam folder or try signing up
              again.
            </p>

            <button
              type="button"
              onClick={handleBackToLogin}
              className="group w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 px-4 rounded-lg font-semibold hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 flex items-center justify-center shadow-lg transform hover:scale-105"
            >
              <ArrowLeft
                size={20}
                className="mr-2 group-hover:-translate-x-1 transition-transform"
              />
              Back to Sign In
            </button>
          </div>
        </div>

        <div className="mt-6 text-center text-sm text-gray-600">
          <p>Secure authentication powered by your API</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md relative">
      {/* Decorative Elements */}
      <div className="absolute -top-20 -left-20 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob pointer-events-none"></div>
      <div className="absolute -top-20 -right-20 w-72 h-72 bg-blue-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-2000 pointer-events-none"></div>
      <div className="absolute -bottom-20 left-1/2 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-blob animation-delay-4000 pointer-events-none"></div>

      <div className="bg-white rounded-2xl shadow-xl p-8 relative z-10">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            {mode === "login" ? "Welcome Back" : "Create Account"}
          </h1>
          <p className="text-gray-600">
            {mode === "login"
              ? "Sign in to continue to your account"
              : "Sign up to get started"}
          </p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-6">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Email Address
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Mail className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="email"
                type="email"
                name="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="block w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                placeholder="you@example.com"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                name="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="block w-full pl-10 pr-10 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                placeholder="Enter your password"
                minLength={6}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5 text-gray-400 hover:text-gray-600" />
                ) : (
                  <Eye className="h-5 w-5 text-gray-400 hover:text-gray-600" />
                )}
              </button>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-800">{error.message}</p>
              {error.code === "EMAIL_NOT_VERIFIED" && (
                <p className="text-sm text-red-700 mt-2">
                  Didn't receive the email?{" "}
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        setError(null);
                        setLoading(true);
                        // We need a token to resend, so we'll show the registration success page instead
                        setRegisteredEmail(email);
                        setRegistrationComplete(true);
                      } catch (err) {
                        setError({
                          message: getFriendlyErrorMessage(err, {
                            fallback: "Failed to resend email",
                          }),
                        });
                      } finally {
                        setLoading(false);
                      }
                    }}
                    className="text-red-900 font-semibold underline hover:text-red-700"
                  >
                    Click here to see instructions
                  </button>
                </p>
              )}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="group w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-3 px-4 rounded-lg font-semibold hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center justify-center shadow-lg transform hover:scale-105"
          >
            {loading ? (
              <>
                <Loader2 className="animate-spin h-5 w-5 mr-2" />
                {mode === "login" ? "Signing In..." : "Creating Account..."}
              </>
            ) : (
              <>
                {mode === "login" ? "Sign In" : "Create Account"}
                <ArrowRight
                  size={20}
                  className="ml-2 group-hover:translate-x-1 transition-transform"
                />
              </>
            )}
          </button>
        </form>

        <div className="mt-6">
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white text-gray-500">
                Or continue with
              </span>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => handleOAuthLogin("google")}
              className="flex items-center justify-center px-4 py-3 border border-gray-300 rounded-lg shadow-sm bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all"
            >
              <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Google
            </button>

            <button
              type="button"
              onClick={() => handleOAuthLogin("apple")}
              className="flex items-center justify-center px-4 py-3 border border-gray-300 rounded-lg shadow-sm bg-black text-sm font-medium text-white hover:bg-gray-900 transition-all"
            >
              <svg
                className="h-5 w-5 mr-2"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
              </svg>
              Apple
            </button>
          </div>
        </div>

        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={toggleMode}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            {mode === "login"
              ? "Don't have an account? Sign up"
              : "Already have an account? Sign in"}
          </button>
        </div>
      </div>

      <div className="mt-6 text-center text-sm text-gray-600">
        <p>Secure authentication powered by your API</p>
      </div>
    </div>
  );
}
