import type { Page } from "playwright";

export class NestedFrameCollector {
  static collect(page: Page): string[] {
    return page.frames().map((f) => f.url()).filter(Boolean);
  }
}
