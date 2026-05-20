export class UrlUtils {
  static normalize(url: string): string {
    try {
      const u = new URL(url);
      u.hash = "";
      return u.toString();
    } catch {
      return url;
    }
  }

  static getFormat(url: string): "m3u8" | "mp4" | "mpd" | "blob" | "unknown" {
    const lower = url.toLowerCase();
    if (lower.startsWith("blob:")) return "blob";
    if (lower.includes(".m3u8")) return "m3u8";
    if (lower.includes(".mpd")) return "mpd";
    if (lower.includes(".mp4")) return "mp4";
    return "unknown";
  }

  static isCandidateMedia(url: string): boolean {
    return /(\.m3u8|\.mp4|\.mpd|manifest|playlist|hls|dash|stream)/i.test(url);
  }
}
