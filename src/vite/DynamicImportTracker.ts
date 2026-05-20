import type { Page } from "playwright";

export class DynamicImportTracker {
  static async collect(page: Page): Promise<string[]> {
    return page.evaluate(() => ((window as any).__EXTRACTOR__?.chunks ?? []) as string[]);
  }
}
