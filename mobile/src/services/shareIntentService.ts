import { Platform } from "react-native";

/**
 * Represents a parsed share intent payload.
 */
export interface ShareIntentPayload {
  /** The raw text/URL shared from the external app */
  text: string | null;
  /** The source app bundle ID or name, if available */
  sourceApp?: string;
  /** Timestamp when the share was received */
  receivedAt: string;
}

/**
 * ShareIntentService handles receiving and parsing incoming share intents.
 *
 * On iOS, the share extension uses App Groups to pass data from the extension
 * to the main app. On Android, the intent filter handles text/plain SEND intents.
 *
 * This service abstracts the platform-specific reception logic and provides
 * a unified interface for the app to consume shared content.
 */
export class ShareIntentService {
  private static listeners: Array<(payload: ShareIntentPayload) => void> = [];
  private static pendingPayload: ShareIntentPayload | null = null;

  /**
   * Register a listener to be called when a share intent is received.
   * If there is already a pending payload (received before listener was registered),
   * it will be dispatched immediately.
   */
  static subscribe(
    listener: (payload: ShareIntentPayload) => void,
  ): () => void {
    this.listeners.push(listener);

    // Dispatch pending payload if one exists
    if (this.pendingPayload) {
      listener(this.pendingPayload);
      this.pendingPayload = null;
    }

    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  /**
   * Called when a share intent is received (from native module or URL scheme).
   * Dispatches to all registered listeners, or queues if none are registered yet.
   */
  static receive(rawText: string | null, sourceApp?: string): void {
    const payload: ShareIntentPayload = {
      text: rawText,
      sourceApp: sourceApp ?? this.getDefaultSourceApp(),
      receivedAt: new Date().toISOString(),
    };

    if (this.listeners.length > 0) {
      for (const listener of this.listeners) {
        listener(payload);
      }
    } else {
      // Queue for later consumption
      this.pendingPayload = payload;
    }
  }

  /**
   * Check and consume any pending share intent payload.
   * Useful for checking on app launch before listeners are set up.
   */
  static consumePending(): ShareIntentPayload | null {
    const payload = this.pendingPayload;
    this.pendingPayload = null;
    return payload;
  }

  /**
   * Returns a default source app identifier based on platform.
   */
  private static getDefaultSourceApp(): string {
    return Platform.OS === "ios" ? "ios-share-extension" : "android-share-intent";
  }

  /**
   * Clear all listeners and pending state. Useful for testing.
   */
  static reset(): void {
    this.listeners = [];
    this.pendingPayload = null;
  }
}
