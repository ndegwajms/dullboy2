import type { Locator, Page } from "playwright";

export class AdaptiveSelectorEngine {
  static build(page: Page): Locator[] {
    return [
      page.getByRole("button", { name: /watch|play/i }),
      page.getByRole("link", { name: /watch|play/i }),
      page.locator("button:has(svg), [role='button']:has(svg)"),
      page.locator("[aria-label*='play' i], [title*='play' i]"),
      page.locator("video, .player, [class*='play' i]"),
    ];
  }
}
