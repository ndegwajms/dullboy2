import type { Diagnostics } from "../models/Diagnostics";

export class DiagnosticsManager {
  private diagnostics: Diagnostics = {
    extractionStrategy: "runtime+network+adaptive",
    overlaysDetected: [],
    hydrationTimeMs: 0,
    playbackTriggered: false,
    streamDetectedEarly: false,
    errors: [],
  };

  update(partial: Partial<Diagnostics>): void {
    this.diagnostics = { ...this.diagnostics, ...partial };
  }

  addError(err: unknown): void {
    this.diagnostics.errors.push(err instanceof Error ? err.message : String(err));
  }

  get(): Diagnostics { return this.diagnostics; }
}
