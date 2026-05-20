const TOKENS = ["m3u8", "mp4", "manifest", "provider", "iframe", "source", "playlist", "mediasource", "fetch(", "axios(", "hls", "dash", "moviedetails", "tvdetails"];

export class ChunkAnalyzer {
  static score(chunk: string): number {
    const lower = chunk.toLowerCase();
    return TOKENS.reduce((acc, t) => acc + (lower.includes(t) ? 8 : 0), 0);
  }

  static rank(chunks: string[]): Array<{ chunk: string; score: number }> {
    return chunks.map((chunk) => ({ chunk, score: this.score(chunk) })).sort((a, b) => b.score - a.score);
  }
}
