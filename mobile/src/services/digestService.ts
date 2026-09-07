import { apiRequest } from "./apiClient";
import type { Digest } from "../types/digest";

/**
 * Digest service for the mobile app.
 * Uses the canonical /api/digest/* endpoints.
 */
export class DigestService {
  /**
   * Fetch the daily digest currently live: the 24 hours the last 18:30 send
   * announced. No date parameter — asking for another day would answer a digest
   * no notification ever named.
   * GET /api/digest/daily
   */
  static async getDailyDigest(): Promise<Digest> {
    return apiRequest<Digest>("/api/digest/daily", { method: "GET" });
  }

  /**
   * Fetch the weekly digest currently live: the Monday-to-Sunday week the last
   * Monday 09:30 send announced.
   * GET /api/digest/weekly
   */
  static async getWeeklyDigest(): Promise<Digest> {
    return apiRequest<Digest>("/api/digest/weekly", { method: "GET" });
  }
}
