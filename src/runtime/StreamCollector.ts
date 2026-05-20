import type { Page } from "playwright";
import type { StreamInfo } from "../models/StreamInfo";
import { UrlUtils } from "../utils/UrlUtils";

export class StreamCollector {
  private streams: StreamInfo[] = [];
  private manifests = new Set<string>();
  private requests = new Set<string>();

  attach(page: Page): void {
    page.on("request", (req) => {
      this.requests.add(req.url());
      this.capture(req.url(), "network", 0.7);
    });
    page.on("response", (res) => this.capture(res.url(), "network", 0.85));
  }

  capture(url: string, source: StreamInfo["source"], confidence: number): void {
    if (!UrlUtils.isCandidateMedia(url)) return;
    const normalized = UrlUtils.normalize(url);
    const format = UrlUtils.getFormat(normalized);
    if (["m3u8", "mpd"].includes(format)) this.manifests.add(normalized);
    this.streams.push({ url: normalized, format, source, confidence, qualityScore: this.score(normalized, format), isMasterPlaylist: /master|playlist/i.test(normalized) });
  }

  async collectRuntime(page: Page): Promise<void> {
    const runtime = await page.evaluate(() => (window as any).__EXTRACTOR__);
    for (const r of runtime?.requests ?? []) this.capture(String(r.url || ""), "runtime", 0.6);
    for (const r of runtime?.responses ?? []) this.capture(String(r.url || ""), "runtime", 0.75);
    for (const m of runtime?.manifests ?? []) this.capture(String(m), "runtime", 0.9);
    for (const b of runtime?.blobs ?? []) this.capture(String(b.blob || ""), "runtime", 0.65);
  }

  snapshot() {
    return { streams: this.streams, manifests: [...this.manifests], requests: [...this.requests] };
  }

  private score(url: string, format: string): number {
    let score = 40;
    if (format === "m3u8") score += 30;
    if (format === "mpd") score += 25;
    if (format === "mp4") score += 18;
    if (/master/i.test(url)) score += 20;
    if (/1080|2160|4k/i.test(url)) score += 10;
    return score;
  }
}
