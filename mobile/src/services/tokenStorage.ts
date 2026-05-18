import * as SecureStore from "expo-secure-store";

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const TOKEN_EXPIRY_KEY = "token_expiry";

/**
 * Secure token storage using expo-secure-store.
 * Replaces localStorage/sessionStorage from the web frontend.
 * Tokens are stored in the device keychain (iOS) or Keystore (Android).
 */
export const TokenStorage = {
  async saveAccessToken(token: string, expiresIn: number): Promise<void> {
    const expiryTime = Date.now() + expiresIn * 1000;
    await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, token);
    await SecureStore.setItemAsync(TOKEN_EXPIRY_KEY, expiryTime.toString());
  },

  async saveRefreshToken(token: string): Promise<void> {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
  },

  async getAccessToken(): Promise<string | null> {
    return SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
  },

  async getRefreshToken(): Promise<string | null> {
    return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
  },

  async getTokenExpiry(): Promise<number | null> {
    const expiry = await SecureStore.getItemAsync(TOKEN_EXPIRY_KEY);
    if (!expiry) return null;
    const parsed = parseInt(expiry, 10);
    return Number.isNaN(parsed) ? null : parsed;
  },

  async isTokenExpired(): Promise<boolean> {
    const expiry = await this.getTokenExpiry();
    if (expiry === null) return true;
    return Date.now() > expiry;
  },

  async clearAll(): Promise<void> {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
    await SecureStore.deleteItemAsync(TOKEN_EXPIRY_KEY);
  },
} as const;
