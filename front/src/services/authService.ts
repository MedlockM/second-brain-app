import {
  RegisterRequest,
  LoginRequest,
  TokenVerificationResponse,
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

  static async register(
    data: RegisterRequest,
  ): Promise<TokenVerificationResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: "POST",
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
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      throw new Error("Logout failed");
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
}
