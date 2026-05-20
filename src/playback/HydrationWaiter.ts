import type { Page } from "playwright";

export class HydrationWaiter {
  static async wait(page: Page, timeoutMs = 8000): Promise<number> {
    const start = Date.now();
    await page.waitForFunction(() => document.readyState !== "loading");
    await page.waitForFunction(() => {
      const root = document.querySelector("#root") || document.body;
      return !!root && root.childElementCount > 0;
    }, { timeout: timeoutMs });
    return Date.now() - start;
  }
}
