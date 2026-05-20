import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import { withRetry } from "../utils/RetryUtils";
import { RequestClassifier } from "../utils/RequestClassifier";

export class BrowserManager {
  private browser?: Browser;

  async createContextAndPage(): Promise<{ context: BrowserContext; page: Page }> {
    this.browser = await chromium.launch({
      headless: true,
      args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
    });

    const context = await this.browser.newContext({
      bypassCSP: true,
      ignoreHTTPSErrors: true,
    });

    await context.route("**/*", (route) => {
      const req = route.request();
      if (RequestClassifier.shouldBlock(req.url(), req.resourceType())) return route.abort();
      return route.continue();
    });

    const page = await withRetry(() => context.newPage(), 3);
    return { context, page };
  }

  async close(context?: BrowserContext): Promise<void> {
    await context?.close();
    await this.browser?.close();
  }
}
