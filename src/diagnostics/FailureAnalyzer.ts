export class FailureAnalyzer {
  static explain(errors: string[]): string {
    if (errors.length === 0) return "No failure";
    if (errors.some((e) => /timeout/i.test(e))) return "Synchronization timeout";
    return "Runtime or provider resolution failure";
  }
}
