import type { Page } from "playwright";
import { AdaptiveSelectorEngine } from "./AdaptiveSelectorEngine";

export class PlaybackTrigger {
  static async trigger(page: Page): Promise<boolean> {
    for (const loc of AdaptiveSelectorEngine.build(page)) {
      const count = await loc.count();
      for (let i = 0; i < Math.min(3, count); i += 1) {
        const target = loc.nth(i);
        if (await target.isVisible().catch(() => false)) {
          try { await target.click({ timeout: 700 }); return true; } catch {}
          try { await target.dispatchEvent("click"); return true; } catch {}
        }
      }
    }
    return page.evaluate(() => {
      const el = document.querySelector("video") as HTMLVideoElement | null;
      if (el) { void el.play().catch(() => undefined); return true; }
      return false;
    });
  }
}
