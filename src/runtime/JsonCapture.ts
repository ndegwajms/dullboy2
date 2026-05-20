import type { Page } from "playwright";

export class JsonCapture {
  static async collect(page: Page): Promise<Array<Record<string, unknown>>> {
    return page.evaluate(() => ((window as any).__EXTRACTOR__?.json ?? []) as Array<Record<string, unknown>>);
  }
}
