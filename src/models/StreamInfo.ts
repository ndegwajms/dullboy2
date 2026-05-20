export type StreamFormat = "m3u8" | "mp4" | "mpd" | "blob" | "unknown";

export interface StreamInfo {
  url: string;
  format: StreamFormat;
  qualityScore: number;
  confidence: number;
  headers?: Record<string, string>;
  source: "network" | "runtime" | "iframe" | "media-source" | "dom";
  isMasterPlaylist?: boolean;
  subtitles?: string[];
  provider?: string;
}
