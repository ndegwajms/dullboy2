import type { Diagnostics } from "./Diagnostics";
import type { StreamInfo } from "./StreamInfo";

export interface ExtractionResult {
  success: boolean;
  streams: StreamInfo[];
  manifests: string[];
  subtitles: string[];
  providers: string[];
  iframes: string[];
  chunks: string[];
  requests: string[];
  diagnostics: Diagnostics;
}
