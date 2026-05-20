import { ExtractorCore } from "./core/ExtractorCore";
import type { ExtractionResult } from "./models/ExtractionResult";

export class AdaptiveStreamingExtractor {
  private core = new ExtractorCore();

  async extract(url: string): Promise<ExtractionResult> {
    return this.core.extract(url);
  }
}
