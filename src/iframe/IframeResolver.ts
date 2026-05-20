import type { Page } from "playwright";
import { NestedFrameCollector } from "./NestedFrameCollector";

export class IframeResolver {
  static async resolve(page: Page): Promise<string[]> {
    const runtimeFrames = await page.evaluate(() => ((window as any).__EXTRACTOR__?.iframes ?? []).map((f: any) => String(f.src || "")) as string[]);
    return [...new Set([...NestedFrameCollector.collect(page), ...runtimeFrames].filter(Boolean))];
  }
}
