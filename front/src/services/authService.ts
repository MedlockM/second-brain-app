import {
  RegisterRequest,
  LoginRequest,
  TokenVerificationResponse,
  AuthUser,
} from "../types/auth";

// When VITE_API_URL is empty, use relative URLs (for Vite proxy)
// Otherwise use the full URL (for production)
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export class AuthService {
  private static getAuthHeaders(token?: string): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
  }

  static async register(data: RegisterRequest): Promise<AuthUser> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: "POST",
      credentials: "include",
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Registration failed" }));
      throw new Error(error.message || error.detail || "Registration failed");
    }

    return response.json();
  }

  static async login(data: LoginRequest): Promise<TokenVerificationResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Login failed" }));
      throw new Error(error.message || error.detail || "Login failed");
    }

    return response.json();
  }

  static async getCurrentUser(token: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      method: "GET",
      credentials: "include",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      throw new Error("Failed to fetch user info");
    }

    return response.json();
  }

  static async logout(token: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      throw new Error("Logout failed");
    }
  }

  static async resendVerificationEmail(token: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/resend-verification`, {
      method: "POST",
      credentials: "include",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to resend verification email" }));
      throw new Error(error.message || error.detail || "Failed to resend verification email");
    }
  }

  static saveToken(token: string, expiresIn: number): void {
    localStorage.setItem("access_token", token);
    const expiryTime = Date.now() + expiresIn * 1000;
    localStorage.setItem("token_expiry", expiryTime.toString());
  }

  static getToken(): string | null {
    const token = localStorage.getItem("access_token");
    const expiry = localStorage.getItem("token_expiry");

    if (!token || !expiry) {
      return null;
    }

    if (Date.now() > parseInt(expiry)) {
      this.clearToken();
      return null;
    }

    return token;
  }

  static clearToken(): void {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_expiry");
  }

  static async refresh(): Promise<TokenVerificationResponse> {
    const API_BASE_URL = import.meta.env.VITE_API_URL || "";
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include", // Important: envoie les cookies (refresh token)
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      this.clearToken();
      throw new Error("Failed to refresh token");
    }

    const data = await response.json();
    this.saveToken(data.access_token, data.expires_in);
    return data;
  }

  static async getValidToken(): Promise<string | null> {
    const token = this.getToken();

    // Si le token existe et n'est pas expiré, on le retourne
    if (token) {
      return token;
    }

    // Si le token est expiré ou n'existe pas, on essaie de le rafraîchir
    try {
      const response = await this.refresh();
      return response.access_token;
    } catch (error) {
      console.error("Failed to refresh token:", error);
      return null;
    }
  }
}
