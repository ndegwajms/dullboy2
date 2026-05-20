import type { Page } from "playwright";

export class ChunkDiscovery {
  static async discover(page: Page): Promise<string[]> {
    return page.evaluate(() => {
      const set = new Set<string>();
      document.querySelectorAll('script[type="module"],script[src]').forEach((s) => {
        const src = (s as HTMLScriptElement).src;
        if (src) set.add(src);
      });
      const rt = (window as any).__EXTRACTOR__;
      for (const c of rt?.chunks ?? []) set.add(String(c));
      return [...set];
    });
  }
}
