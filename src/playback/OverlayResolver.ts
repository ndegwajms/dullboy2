import type { Page } from "playwright";

export class OverlayResolver {
  static async resolve(page: Page): Promise<string[]> {
    return page.evaluate(() => {
      const overlays: string[] = [];
      const nodes = Array.from(document.querySelectorAll("body *"));
      for (const el of nodes) {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        const isFullscreen = rect.width > window.innerWidth * 0.9 && rect.height > window.innerHeight * 0.8;
        const highZ = Number(style.zIndex || 0) >= 100;
        if ((style.position === "fixed" || style.position === "absolute") && isFullscreen && highZ) {
          overlays.push(`${el.tagName}.${el.className}`);
          if (style.pointerEvents !== "none") (el as HTMLElement).style.pointerEvents = "none";
        }
      }
      return overlays;
    });
  }
}
