const BLOCK_PATTERNS = [/google-analytics/i, /doubleclick/i, /googletagmanager/i, /segment\.io/i, /hotjar/i];
const BLOCK_RESOURCE_TYPES = new Set(["image", "font"]);

export class RequestClassifier {
  static shouldBlock(url: string, resourceType: string): boolean {
    if (BLOCK_RESOURCE_TYPES.has(resourceType)) return true;
    return BLOCK_PATTERNS.some((r) => r.test(url));
  }
}
