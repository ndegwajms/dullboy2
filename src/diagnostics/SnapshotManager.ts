import type { Page } from "playwright";

export class SnapshotManager {
  static async saveOnFailure(page: Page, base = "artifacts"): Promise<void> {
    await page.screenshot({ path: `${base}-failure.png`, fullPage: true }).catch(() => undefined);
    const html = await page.content().catch(() => "");
    if (html) await import("node:fs/promises").then((fs) => fs.writeFile(`${base}-failure.html`, html));
  }
}
