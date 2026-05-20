import type { ExtractionResult } from "../models/ExtractionResult";
import { BrowserManager } from "./BrowserManager";
import { RuntimeInterceptor } from "../runtime/RuntimeInterceptor";
import { ExtractionOrchestrator } from "./ExtractionOrchestrator";

export class ExtractorCore {
  private browserManager = new BrowserManager();
  private orchestrator = new ExtractionOrchestrator();

  async extract(url: string): Promise<ExtractionResult> {
    const { context, page } = await this.browserManager.createContextAndPage();
    try {
      await RuntimeInterceptor.install(page);
      return await this.orchestrator.run(page, url);
    } finally {
      await this.browserManager.close(context);
    }
  }
}
