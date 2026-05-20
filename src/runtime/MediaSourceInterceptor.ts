import type { Page } from "playwright";

export class MediaSourceInterceptor {
  static async collect(page: Page): Promise<Array<Record<string, unknown>>> {
    return page.evaluate(() => ((window as any).__EXTRACTOR__?.mediaSources ?? []) as Array<Record<string, unknown>>);
  }
}
