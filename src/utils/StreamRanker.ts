import type { StreamInfo } from "../models/StreamInfo";

export class StreamRanker {
  static rank(streams: StreamInfo[]): StreamInfo[] {
    return [...streams].sort((a, b) => b.qualityScore - a.qualityScore || b.confidence - a.confidence);
  }

  static dedupe(streams: StreamInfo[]): StreamInfo[] {
    const seen = new Set<string>();
    return streams.filter((s) => {
      const key = `${s.url}|${s.format}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }
}
