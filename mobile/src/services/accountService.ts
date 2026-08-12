import { apiRequest } from "./apiClient";

/**
 * Account lifecycle calls that are not authentication.
 *
 * Deletion is a single DELETE on /api/account: the backend derives the account
 * from the bearer token, so no user id is sent and one client cannot ask for
 * another account's erasure even by accident.
 */
export class AccountService {
  /**
   * Permanently delete the signed-in account and everything it owns.
   *
   * Resolves only once the backend reports the purge complete (204). It throws on
   * any failure, and the account is still usable in that case: the purge removes
   * the identity rows last precisely so a failed attempt can be retried.
   *
   * Note this does not cancel an App Store / Play Store subscription. Only the
   * store can do that, so the caller must tell the user before confirming.
   */
  static async deleteAccount(token: string): Promise<void> {
    await apiRequest<void>("/api/account", { method: "DELETE", token });
  }
}
