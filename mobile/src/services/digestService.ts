import { apiRequest } from "./apiClient";
import type { DailyDigest, WeeklyDigest } from "../types/digest";

/**
 * Digest service for the mobile app.
 * Uses the canonical /api/digest/* endpoints.
 */
export class DigestService {
  /**
   * Fetch the daily digest for a given date (defaults to today).
   * GET /api/digest/daily?date=YYYY-MM-DD
   */
  static async getDailyDigest(date?: string): Promise<DailyDigest> {
    const params = date ? `?date=${encodeURIComponent(date)}` : "";
    return apiRequest<DailyDigest>(`/api/digest/daily${params}`, {
      method: "GET",
    });
  }

  /**
   * Fetch the weekly digest for a given week start date (defaults to current week).
   * GET /api/digest/weekly?week_start=YYYY-MM-DD
   */
  static async getWeeklyDigest(weekStart?: string): Promise<WeeklyDigest> {
    const params = weekStart
      ? `?week_start=${encodeURIComponent(weekStart)}`
      : "";
    return apiRequest<WeeklyDigest>(`/api/digest/weekly${params}`, {
      method: "GET",
    });
  }
}
