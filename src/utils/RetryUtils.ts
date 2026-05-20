export async function withRetry<T>(fn: () => Promise<T>, maxAttempts = 3, baseMs = 150): Promise<T> {
  let lastError: unknown;
  for (let i = 1; i <= maxAttempts; i += 1) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (i === maxAttempts) break;
      await new Promise((r) => setTimeout(r, baseMs * i));
    }
  }
  throw lastError;
}
