export type FriendlyErrorRule = {
  regex: RegExp;
  message: string;
};

export interface FriendlyErrorOptions {
  fallback?: string;
  additionalRules?: FriendlyErrorRule[];
}
