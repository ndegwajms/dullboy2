import type { Page } from "playwright";
import type { ExtractionResult } from "../models/ExtractionResult";
import { StreamRanker } from "../utils/StreamRanker";
import { StreamCollector } from "../runtime/StreamCollector";
import { ChunkDiscovery } from "../vite/ChunkDiscovery";
import { ChunkAnalyzer } from "../vite/ChunkAnalyzer";
import { DynamicImportTracker } from "../vite/DynamicImportTracker";
import { HydrationWaiter } from "../playback/HydrationWaiter";
import { OverlayResolver } from "../playback/OverlayResolver";
import { PlaybackTrigger } from "../playback/PlaybackTrigger";
import { IframeResolver } from "../iframe/IframeResolver";
import { JsonCapture } from "../runtime/JsonCapture";
import { MediaSourceInterceptor } from "../runtime/MediaSourceInterceptor";
import { DiagnosticsManager } from "../diagnostics/DiagnosticsManager";
import { FailureAnalyzer } from "../diagnostics/FailureAnalyzer";
import { SnapshotManager } from "../diagnostics/SnapshotManager";

export class ExtractionOrchestrator {
  async run(page: Page, targetUrl: string): Promise<ExtractionResult> {
    const diagnostics = new DiagnosticsManager();
    const collector = new StreamCollector();
    collector.attach(page);

    try {
      await page.goto(targetUrl, { waitUntil: "domcontentloaded", timeout: 25000 });
      const hydrationTimeMs = await HydrationWaiter.wait(page);
      diagnostics.update({ hydrationTimeMs });

      const [overlaysDetected, chunks] = await Promise.all([
        OverlayResolver.resolve(page),
        ChunkDiscovery.discover(page),
      ]);
      diagnostics.update({ overlaysDetected });

      const playbackTriggered = await PlaybackTrigger.trigger(page);
      diagnostics.update({ playbackTriggered });

      const early = collector.snapshot().streams.length > 0;
      diagnostics.update({ streamDetectedEarly: early, chunkScores: ChunkAnalyzer.rank(chunks) });

      await page.waitForTimeout(1200);
      await collector.collectRuntime(page);

      const imports = await DynamicImportTracker.collect(page);
      const iframes = await IframeResolver.resolve(page);
      const json = await JsonCapture.collect(page);
      const mediaSources = await MediaSourceInterceptor.collect(page);

      for (const item of json) {
        const text = JSON.stringify(item);
        const match = text.match(/https?:\/\/[^"'\s]+(\.m3u8|\.mp4|\.mpd)[^"'\s]*/gi) ?? [];
        for (const u of match) collector.capture(u, "runtime", 0.7);
      }

      const ranked = StreamRanker.rank(StreamRanker.dedupe(collector.snapshot().streams));
      const manifests = [...new Set([...collector.snapshot().manifests, ...ranked.filter((s) => s.format !== "mp4").map((s) => s.url)])];

      return {
        success: ranked.length > 0,
        streams: ranked,
        manifests,
        subtitles: [],
        providers: [...new Set(iframes.map((f) => new URL(f).hostname).filter(Boolean))],
        iframes,
        chunks: [...new Set([...chunks, ...imports])],
        requests: collector.snapshot().requests,
        diagnostics: { ...diagnostics.get(), extractionStrategy: `runtime+network+adaptive; mediaSources=${mediaSources.length}` },
      };
    } catch (error) {
      diagnostics.addError(error);
      diagnostics.addError(FailureAnalyzer.explain(diagnostics.get().errors));
      await SnapshotManager.saveOnFailure(page);
      return { success: false, streams: [], manifests: [], subtitles: [], providers: [], iframes: [], chunks: [], requests: [], diagnostics: diagnostics.get() };
    }
  }
}
