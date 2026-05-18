import { useState, useEffect } from "react";

/**
 * Debounce hook - delays updating the returned value until after
 * the specified delay has elapsed since the last change.
 *
 * @param value The value to debounce
 * @param delayMs Delay in milliseconds (default 300)
 * @returns The debounced value
 */
export function useDebounce<T>(value: T, delayMs: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debouncedValue;
}
