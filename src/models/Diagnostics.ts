export interface Diagnostics {
  extractionStrategy: string;
  overlaysDetected: string[];
  hydrationTimeMs: number;
  playbackTriggered: boolean;
  streamDetectedEarly: boolean;
  errors: string[];
  chunkScores?: Array<{ chunk: string; score: number }>;
  iframeHierarchy?: string[];
  timings?: Record<string, number>;
}
