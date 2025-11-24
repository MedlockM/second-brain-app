// When VITE_API_URL is empty, use relative URLs (for Vite proxy)
// Otherwise use the full URL (for production)
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export interface SpotifyStatusResponse {
  linked: boolean;
  spotify_user_id?: string;
  scope?: string;
  token_expires_at?: string;
}

export class SpotifyService {
  private static getAuthHeaders(token: string): HeadersInit {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  }

  static async checkStatus(token: string): Promise<SpotifyStatusResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/spotify/status`, {
      method: "GET",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to check Spotify status" }));
      throw new Error(
        error.message || error.detail || "Failed to check Spotify status",
      );
    }

    return response.json();
  }

  static async linkAccount(token: string): Promise<{ url: string }> {
    // Get Spotify OAuth URL from backend (with Bearer token authentication)
    const response = await fetch(
      `${API_BASE_URL}/api/v1/auth/spotify/auth-url`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to get Spotify auth URL" }));
      throw new Error(
        error.message || error.detail || "Failed to get Spotify auth URL",
      );
    }

    const data = await response.json();
    // Redirect to Spotify OAuth URL
    window.location.href = data.url;
    return { url: data.url };
  }

  static async unlinkAccount(token: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/spotify/unlink`, {
      method: "DELETE",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to unlink Spotify account" }));
      throw new Error(
        error.message || error.detail || "Failed to unlink Spotify account",
      );
    }

    return response.json();
  }

  static async syncTosumPlaylist(token: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/spotify/sync-tosum`, {
      method: "POST",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to sync Tosum playlist" }));
      throw new Error(
        error.message || error.detail || "Failed to sync Tosum playlist",
      );
    }

    return response.json();
  }

  static async getPlaylists(token: string, signal?: AbortSignal): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/spotify/playlists`, {
      method: "GET",
      headers: this.getAuthHeaders(token),
      signal,
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to get playlists" }));
      throw new Error(
        error.message || error.detail || "Failed to get playlists",
      );
    }

    return response.json();
  }

  static async getSubscriptions(token: string): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/spotify/subscriptions`, {
      method: "GET",
      headers: this.getAuthHeaders(token),
    });

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to get subscriptions" }));
      throw new Error(
        error.message || error.detail || "Failed to get subscriptions",
      );
    }

    return response.json();
  }

  static async updateSubscription(
    token: string,
    playlistId: string,
    enabled: boolean,
  ): Promise<any> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/spotify/playlists/${playlistId}/subscription`,
      {
        method: "PUT",
        headers: this.getAuthHeaders(token),
        body: JSON.stringify({ enabled }),
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to update subscription" }));
      throw new Error(
        error.message || error.detail || "Failed to update subscription",
      );
    }

    return response.json();
  }

  static async syncPlaylist(token: string, playlistId: string): Promise<any> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/spotify/playlists/${playlistId}/sync`,
      {
        method: "POST",
        headers: this.getAuthHeaders(token),
      },
    );

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Failed to sync playlist" }));
      throw new Error(
        error.message || error.detail || "Failed to sync playlist",
      );
    }

    return response.json();
  }
}
