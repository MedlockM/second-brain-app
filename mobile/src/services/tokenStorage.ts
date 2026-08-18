import * as SecureStore from "expo-secure-store";
import type { AuthUser } from "../types/auth";

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const TOKEN_EXPIRY_KEY = "token_expiry";
const USER_KEY = "auth_user";

/**
 * Secure session storage using expo-secure-store.
 * Replaces localStorage/sessionStorage from the web frontend.
 * Everything here lives in the device keychain (iOS) or Keystore (Android).
 *
 * The signed-in profile is stored next to the tokens: a cold start with no
 * network can then restore the session from the keychain alone, without a /me
 * round trip it would have no way of completing.
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

  async saveUser(user: AuthUser): Promise<void> {
    await SecureStore.setItemAsync(USER_KEY, JSON.stringify(user));
  },

  async getAccessToken(): Promise<string | null> {
    return SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
  },

  async getRefreshToken(): Promise<string | null> {
    return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
  },

  async getUser(): Promise<AuthUser | null> {
    const raw = await SecureStore.getItemAsync(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      return null;
    }
  },

  async getTokenExpiry(): Promise<number | null> {
    const expiry = await SecureStore.getItemAsync(TOKEN_EXPIRY_KEY);
    if (!expiry) return null;
    const parsed = parseInt(expiry, 10);
    return Number.isNaN(parsed) ? null : parsed;
  },

  async clearAll(): Promise<void> {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
    await SecureStore.deleteItemAsync(TOKEN_EXPIRY_KEY);
    await SecureStore.deleteItemAsync(USER_KEY);
  },
} as const;
