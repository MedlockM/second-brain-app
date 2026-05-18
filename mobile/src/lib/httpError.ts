export type HttpError = Error & { status?: number; code?: string };

export function createHttpError(
  message: string,
  status?: number,
  code?: string,
): HttpError {
  const error = new Error(message) as HttpError;
  if (status !== undefined) {
    error.status = status;
  }
  if (code) {
    error.code = code;
  }
  return error;
}

export async function parseErrorResponse(
  response: Response,
  fallbackMessage: string,
): Promise<{ message: string; code?: string }> {
  try {
    const data = await response.json();
    const errorData = data?.error ?? data ?? {};
    const message =
      errorData.message ||
      errorData.detail ||
      data?.detail ||
      fallbackMessage;
    const code = errorData.code || data?.code;
    return { message, code };
  } catch {
    return { message: fallbackMessage };
  }
}
