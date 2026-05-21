import httpx
import re
import base64
import hashlib
import time
import urllib.parse
import os
from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class VidsrcExtractor:
    def __init__(self):
        self.base_url = os.getenv("VIDSRC_BASE_URL", "https://vixsrc.to").rstrip("/")
        self.fallback_base_urls = []
        self.browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
        }
        self.client = httpx.Client(headers={
            **self.browser_headers,
            "Referer": f"{self.base_url}/"
        })
        self.secret_prefix = "Cns#nGelOl"
        self.stream_cache = {}
        self.stream_cache_ttl = 300
        self.token_cache = {}
        self.token_cache_ttl = 900
        self.runtime_capture_timeout_ms = 20000
        self.expiring_stream_refresh_margin_seconds = 120
        self.stream_url_patterns = (
            ".m3u8",
            "master.m3u8",
            ".mp4",
            ".mpd",
            "/playlist",
            "/source",
            "/manifest",
            "/tracks",
            "/subs",
            "/license",
            "widevine",
        )

    def _extract_direct_iframe_url(self, html, soup, page_url):
        import urllib.parse

        iframe = soup.find("iframe", {"id": "player_iframe"}) or soup.find("iframe")
        if iframe:
            raw_src = iframe.get("src") or iframe.get("data-src")
            if raw_src:
                return urllib.parse.urljoin(page_url, raw_src.strip())

        script_text = "\n".join([s.get_text() for s in soup.find_all("script") if s.get_text(strip=True)])
        patterns = [
            r'player_iframe[^\\n\\r]{0,200}?src\\s*=\\s*["\\\']([^"\\\']+)["\\\']',
            r'var\\s+source\\s*=\\s*["\\\']([^"\\\']+)["\\\']',
            r'source\\s*:\\s*["\\\']([^"\\\']+)["\\\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, script_text)
            if match:
                return urllib.parse.urljoin(page_url, match.group(1).strip())
        return None

    def _resolve_provider_payload(self, base_url, iframe_url):
        iframe_url = urllib.parse.unquote(iframe_url)
        iframe_url = urllib.parse.urljoin(base_url, iframe_url)
        print("Iframe URL:", iframe_url)

        browser_result = self._resolve_provider_payload_with_browser(base_url, iframe_url)
        if browser_result:
            return browser_result

        lucky_res = self.client.get(iframe_url, follow_redirects=True, headers={
            **self.browser_headers,
            "Referer": f"{base_url}/",
        })
        next_url_match = re.search(r'var source = "(.*?)"', lucky_res.text)
        if not next_url_match:
            print(f"Failed to find source variable on page: {iframe_url}")
            return None

        next_url = next_url_match.group(1).replace(r'\/', '/').replace(r'\u0026', '&')
        next_url = urllib.parse.urljoin(iframe_url, next_url)
        print("Next URL:", next_url)

        embed_res = self.client.get(next_url, headers={
            **self.browser_headers,
            "Referer": iframe_url,
        })
        file_id_match = re.search(r'/e-1/(.*?)\?', next_url)
        if not file_id_match:
            print(f"Failed to extract file_id from: {next_url}")
            return None
        file_id = file_id_match.group(1)

        base_parts = next_url.split('/embed-')[0]
        embed_id_match = re.search(r'/(embed-\d+)/', next_url)
        if not embed_id_match:
            print(f"Failed to extract embed_id from: {next_url}")
            return None
        embed_id = embed_id_match.group(1)

        if "rapid-cloud" in next_url:
            sources_url = f"{base_parts}/{embed_id}/v3/e-1/getSources?id={file_id}"
            final_res = self.client.get(sources_url, headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": next_url
            })
            return final_res.json()

        k_token = self._extract_streameee_token(embed_res.text)
        if not k_token:
            k_token = self._fetch_streameee_token_http_only(next_url, iframe_url)
        elif next_url not in self.token_cache:
            self.token_cache[next_url] = {
                "token": k_token,
                "expires_at": time.time() + self.token_cache_ttl,
            }

        if not k_token:
            print("Embed page snippet:", embed_res.text[:1200])
            print(f"Failed to find _k token on: {next_url}")
            return None

        sources_url = f"{base_parts}/{embed_id}/v3/e-1/getSources?id={file_id}&_k={k_token}"
        final_res = self.client.get(sources_url, headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": next_url
        })
        return final_res.json()


    def _launch_playwright_chromium(self, playwright):
        launch_options = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }

        executable_path = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if executable_path:
            launch_options["executable_path"] = executable_path

        channel = os.getenv("PLAYWRIGHT_CHROMIUM_CHANNEL")
        if channel:
            launch_options["channel"] = channel

        return playwright.chromium.launch(**launch_options)

    def _resolve_provider_payload_with_browser(self, base_url, iframe_url):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            print(f"Playwright provider simulation unavailable: {e}")
            return None

        print("Browser provider simulation boot:", iframe_url)
        try:
            with sync_playwright() as p:
                browser = self._launch_playwright_chromium(p)
                context = browser.new_context(
                    user_agent=self.browser_headers.get("User-Agent"),
                    extra_http_headers={"Referer": f"{base_url}/"},
                )
                page = context.new_page()

                captured_json = []
                nested_iframes = []

                def capture_response(res):
                    url = res.url
                    if "/getSources" not in url:
                        return
                    try:
                        payload = res.json()
                        if isinstance(payload, dict) and payload.get("sources") is not None:
                            captured_json.append(payload)
                    except Exception:
                        return

                page.on("response", capture_response)
                page.goto(iframe_url, wait_until="domcontentloaded", timeout=self.runtime_capture_timeout_ms)
                page.wait_for_timeout(4500)

                for frame in page.frames:
                    frame_url = (frame.url or "").strip()
                    if frame_url and frame_url != "about:blank" and frame_url != iframe_url:
                        nested_iframes.append(frame_url)

                for frame_url in nested_iframes:
                    try:
                        follow_page = context.new_page()
                        follow_page.goto(frame_url, wait_until="domcontentloaded", timeout=self.runtime_capture_timeout_ms)
                        follow_page.wait_for_timeout(3000)
                        follow_page.close()
                    except Exception as nested_error:
                        print(f"Nested iframe follow failed ({frame_url}): {nested_error}")

                page.wait_for_timeout(2000)
                browser.close()

                if captured_json:
                    print("Browser provider simulation captured getSources payload")
                    return captured_json[0]

        except Exception as e:
            print(f"Browser provider simulation failed: {e}")
            return None

        return None

    def _is_likely_stream_url(self, url):
        if not url:
            return False
        lowered = str(url).lower()
        return any(pattern in lowered for pattern in self.stream_url_patterns)

    def _extract_runtime_stream_url(self, embed_url, referer_url=None):
        embed_url = urllib.parse.unquote(embed_url)
        candidates = []
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            print(f"Playwright runtime interception unavailable: {e}")
            return None

        print("Runtime interception boot:", embed_url)
        try:
            with sync_playwright() as p:
                browser = self._launch_playwright_chromium(p)
                context_kwargs = {
                    "user_agent": self.browser_headers.get("User-Agent"),
                }
                if referer_url:
                    context_kwargs["extra_http_headers"] = {"Referer": referer_url}

                context = browser.new_context(**context_kwargs)
                page = context.new_page()

                def add_candidate(url):
                    if isinstance(url, str) and ".m3u8" in url.lower():
                        candidates.append(url)

                page.on("request", lambda req: add_candidate(req.url))
                page.on("response", lambda res: add_candidate(res.url))

                page.goto(embed_url, wait_until="domcontentloaded", timeout=self.runtime_capture_timeout_ms)
                page.wait_for_timeout(10000)
                browser.close()
        except Exception as e:
            print(f"Runtime interception failed: {e}")
            return None

        for url in candidates:
            if ".m3u8" in str(url).lower():
                print("FOUND STREAM:", url)
                return url
        return None

    def _extract_embed_vars(self, html, soup, fallback_input_id):
        """
        Extract vars needed for /api/*/servers from modern and legacy embed pages.
        """
        def get_var(name, text):
            patterns = [
                fr'var\s+{name}\s*=\s*"([^"]+)"',
                fr"var\s+{name}\s*=\s*'([^']+)'",
                fr'"{name}"\s*:\s*"([^"]+)"',
                fr"'{name}'\s*:\s*'([^']+)'",
                fr"{name}\s*=\s*([^;]+);",
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1).strip().strip("'").strip('"')
            return None

        body = soup.find("body")
        body_attrs = body.attrs if body else {}
        body_data_i = body_attrs.get("data-i")
        body_data_v = body_attrs.get("data-v") or body_attrs.get("data-token")
        body_data_user = body_attrs.get("data-u") or body_attrs.get("data-user")
        body_data_imdb = body_attrs.get("data-imdb") or body_attrs.get("data-imdbid")

        script_texts = [s.get_text() for s in soup.find_all("script") if s.get_text(strip=True)]
        combined_text = "\n".join(script_texts + [html])

        v = get_var("v", combined_text) or body_data_v
        user_id = (
            get_var("userId", combined_text)
            or get_var("user_id", combined_text)
            or body_data_user
        )
        movie_id = (
            get_var("movieId", combined_text)
            or get_var("malId", combined_text)
            or get_var("anilistId", combined_text)
            or body_data_i
            or fallback_input_id
        )
        imdb_id = get_var("imdbId", combined_text) or body_data_imdb or ""

        return {
            "v": v,
            "user_id": user_id,
            "movie_id": movie_id,
            "imdb_id": imdb_id,
        }

    def _build_server_request_candidates(self, movie_id, request_id, is_tv, is_anime, season, episode, v, vrf, imdb_id):
        request_type = "anime" if is_anime else ("tv" if is_tv else "movie")

        base_payload = {
            "id": movie_id,
            "type": request_type,
            "imdbId": imdb_id,
        }
        if season is not None:
            base_payload["season"] = season
        if episode is not None:
            base_payload["episode"] = episode

        candidates = []
        candidate_payloads = [
            {**base_payload, "v": v, "vrf": vrf},
            {**base_payload, "v": v},
            {**base_payload, "vrf": vrf},
            {**base_payload},
        ]

        if request_id and request_id != movie_id:
            id_swap_payloads = []
            for payload in candidate_payloads:
                swapped = dict(payload)
                swapped["id"] = request_id
                id_swap_payloads.append(swapped)
            candidate_payloads.extend(id_swap_payloads)

        dedup = []
        seen = set()
        for payload in candidate_payloads:
            key = tuple(sorted((k, str(vv)) for k, vv in payload.items() if vv not in (None, "")))
            if key in seen:
                continue
            seen.add(key)
            dedup.append({k: vv for k, vv in payload.items() if vv is not None and vv != ""})

        return dedup

    def _extract_embed_vars_from_sources_js(self, js_text):
        def get_js_value(key):
            patterns = [
                fr'{key}\s*:\s*"([^"]+)"',
                fr"{key}\s*:\s*'([^']+)'",
                fr'{key}\s*:\s*([A-Za-z0-9_\-\.]+)',
            ]
            for pattern in patterns:
                m = re.search(pattern, js_text)
                if m:
                    return m.group(1).strip().strip("'").strip('"')
            return None

        return {
            "v": get_js_value("v"),
            "user_id": get_js_value("userId") or get_js_value("user_id"),
            "movie_id": get_js_value("movieId") or get_js_value("id"),
            "imdb_id": get_js_value("imdbId") or "",
        }

    def _extract_streameee_token(self, html):
        xy_ws_match = re.search(r'window\._xy_ws\s*=\s*"([^"]+)"', html)
        if xy_ws_match:
            raw_token = xy_ws_match.group(1)
            return raw_token[:-1] if raw_token.endswith("X") else raw_token

        is_th_match = re.search(r'<!--\s*_is_th:([^\s<]+)\s*-->', html)
        if is_th_match:
            return is_th_match.group(1)

        meta_tag = BeautifulSoup(html, 'html.parser').find('meta', {'name': '_gg_fb'})
        if meta_tag:
            return meta_tag.get('content')

        return None

    def _fetch_streameee_token_http_only(self, url, referer):
        cached = self.token_cache.get(url)
        if cached and cached["expires_at"] > time.time():
            return cached["token"]

        request_profiles = [
            {
                **self.browser_headers,
                "Referer": referer,
                "Sec-Fetch-Dest": "iframe",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
            },
            {
                **self.browser_headers,
                "Referer": referer,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
            },
            {
                **self.browser_headers,
                "Referer": url,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
            },
        ]

        try:
            for headers in request_profiles:
                response = self.client.get(url, headers=headers, follow_redirects=True)
                token = self._extract_streameee_token(response.text)
                if token:
                    self.token_cache[url] = {
                        "token": token,
                        "expires_at": time.time() + self.token_cache_ttl,
                    }
                    return token

            time.sleep(0.15)
            response = self.client.get(url, headers=request_profiles[-1], follow_redirects=True)
            token = self._extract_streameee_token(response.text)
            if token:
                self.token_cache[url] = {
                    "token": token,
                    "expires_at": time.time() + self.token_cache_ttl,
                }
            return token
        except Exception as e:
            print(f"HTTP token fallback failed: {e}")
            return None

    def generate_vrf(self, movie_id, user_id):
        secret = f"{self.secret_prefix}X_{user_id}"
        key = hashlib.sha256(secret.encode("utf-8")).digest()
        
        pad_len = 16 - (len(movie_id) % 16)
        padded_data = movie_id.encode("utf-8") + bytes([pad_len] * pad_len)

        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(bytes(16)),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        vrf = (
            base64.b64encode(ciphertext)
            .decode("ascii")
            .replace("+", "-")
            .replace("/", "_")
            .rstrip("=")
        )
        return vrf

    def _build_vixsrc_watch_url(self, id, is_tv=False, season=None, episode=None, is_anime=False, sub_or_dub="sub"):
        """
        Build the client-side Vixsrc route. Vixsrc is a hash-router SPA, so the useful
        route must be opened by a browser as https://vixsrc.to/#/movie/<tmdb id>.
        """
        if is_anime:
            episode_segment = f"/{episode}" if episode is not None else ""
            return f"{self.base_url}/#/anime/{id}{episode_segment}?lang={urllib.parse.quote(str(sub_or_dub))}"
        if is_tv:
            if season is None or episode is None:
                raise ValueError("season and episode are required for TV extraction")
            return f"{self.base_url}/#/tv/{id}/{season}/{episode}"
        return f"{self.base_url}/#/movie/{id}"

    def _normalise_stream_type(self, url):
        lowered = str(url).lower()
        if ".m3u8" in lowered:
            return "hls"
        if ".mpd" in lowered or "/dash" in lowered:
            return "dash"
        if ".mp4" in lowered:
            return "mp4"
        return "stream"

    def _dedupe_sources(self, urls):
        sources = []
        seen = set()
        for url in urls:
            if not isinstance(url, str):
                continue
            clean_url = url.strip()
            if not clean_url or clean_url in seen:
                continue
            seen.add(clean_url)
            sources.append({"file": clean_url, "type": self._normalise_stream_type(clean_url)})
        return sources

    def _extract_url_expiry_timestamp(self, url):
        if not isinstance(url, str) or not url.strip():
            return None

        try:
            parsed = urllib.parse.urlparse(url)
            query_values = urllib.parse.parse_qs(parsed.query)
        except Exception:
            query_values = {}

        for key in ("expires", "expires_at", "expire", "exp", "e"):
            for value in query_values.get(key, []):
                if isinstance(value, str) and re.fullmatch(r"\d{10,13}", value):
                    timestamp = int(value)
                    return timestamp // 1000 if timestamp > 9999999999 else timestamp

        # Some CDN tokens encode the UNIX expiry as the final dot-delimited token,
        # for example: st=<signature>.1.1779154217
        for value in query_values.values():
            for item in value:
                match = re.search(r"(?:^|\.)(\d{10,13})(?:$|[^0-9])", str(item))
                if match:
                    timestamp = int(match.group(1))
                    return timestamp // 1000 if timestamp > 9999999999 else timestamp

        return None

    def _source_url(self, source):
        if isinstance(source, dict):
            return source.get("file") or source.get("url") or source.get("src")
        if isinstance(source, str):
            return source
        return None

    def _extract_stream_urls_from_json(self, payload):
        urls = []
        seen = set()

        def remember(url):
            if not isinstance(url, str):
                return
            candidate = url.strip()
            if not candidate:
                return
            lowered = candidate.lower()
            if any(token in lowered for token in (".m3u8", ".mpd", ".mp4")) and candidate not in seen:
                seen.add(candidate)
                urls.append(candidate)

        def walk(value):
            if isinstance(value, dict):
                for nested in value.values():
                    walk(nested)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, str):
                remember(value)

        walk(payload)
        return urls

    def _resolve_source_pointer(self, source_url, referer_url):
        if not isinstance(source_url, str) or not source_url.strip():
            return None

        parsed = urllib.parse.urlparse(source_url)
        if parsed.scheme not in ("http", "https"):
            return None

        if "/api/sources" not in parsed.path:
            return None

        try:
            response = self.client.get(
                source_url,
                headers={
                    **self.browser_headers,
                    "Referer": referer_url,
                    "Accept": "application/json, text/plain, */*",
                },
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Source pointer fetch failed ({source_url}): {e}")
            return None

    def _resolve_indirect_sources(self, result, referer_url):
        if not isinstance(result, dict):
            return result

        sources = result.get("sources")
        if not isinstance(sources, list):
            return result

        resolved_urls = []
        for source in sources:
            source_url = self._source_url(source)
            if not source_url:
                continue
            payload = self._resolve_source_pointer(source_url, referer_url)
            if not payload:
                continue
            resolved_urls.extend(self._extract_stream_urls_from_json(payload))

        deduped = self._dedupe_sources(resolved_urls)
        if deduped:
            result["sources"] = deduped
            result["detected_via"] = "vixsrc-source-pointer-resolution"
            result["resolved_from"] = referer_url

        return result

    def _annotate_expiring_sources(self, result):
        if not isinstance(result, dict):
            return result

        now = int(time.time())
        expiries = []
        sources = result.get("sources")
        if isinstance(sources, list):
            for index, source in enumerate(sources):
                source_url = self._source_url(source)
                expires_at = self._extract_url_expiry_timestamp(source_url)
                if not expires_at:
                    continue

                expiries.append(expires_at)
                metadata = {
                    "expires_at": expires_at,
                    "expires_in_seconds": max(0, expires_at - now),
                    "is_expiring": True,
                }
                if isinstance(source, dict):
                    source.update(metadata)
                elif isinstance(source, str):
                    sources[index] = {
                        "file": source,
                        "type": self._normalise_stream_type(source),
                        **metadata,
                    }

        if expiries:
            earliest_expiry = min(expiries)
            refresh_after = max(now, earliest_expiry - self.expiring_stream_refresh_margin_seconds)
            result["expires_at"] = earliest_expiry
            result["expires_in_seconds"] = max(0, earliest_expiry - now)
            result["refresh_after"] = refresh_after
            result["refresh_after_seconds"] = max(0, refresh_after - now)
            result["refresh_required"] = earliest_expiry <= now

        return result

    def _capture_vixsrc_runtime_payload(self, watch_url):
        stream_urls = []
        tracks = []
        provider_payloads = []
        iframe_urls = []

        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            print(f"Playwright Vixsrc extraction unavailable: {e}")
            return None

        def remember_stream_url(url):
            if self._is_likely_stream_url(url):
                stream_urls.append(url)

        def remember_track_url(url):
            if not isinstance(url, str):
                return
            lowered = url.lower()
            if any(ext in lowered for ext in (".vtt", ".srt", ".ass", ".ssa")):
                tracks.append({"file": url, "kind": "captions"})

        def walk_json(value):
            if isinstance(value, dict):
                if value.get("sources") is not None:
                    provider_payloads.append(value)
                for key, nested in value.items():
                    lowered_key = str(key).lower()
                    if lowered_key in {"file", "url", "src", "source"} and isinstance(nested, str):
                        remember_stream_url(nested)
                        remember_track_url(nested)
                    else:
                        walk_json(nested)
            elif isinstance(value, list):
                for item in value:
                    walk_json(item)

        print("Vixsrc browser extraction boot:", watch_url)
        try:
            with sync_playwright() as p:
                browser = self._launch_playwright_chromium(p)
                context = browser.new_context(
                    user_agent=self.browser_headers.get("User-Agent"),
                    extra_http_headers={"Referer": f"{self.base_url}/"},
                )
                page = context.new_page()

                def capture_request(req):
                    remember_stream_url(req.url)
                    remember_track_url(req.url)

                def capture_response(res):
                    url = res.url
                    remember_stream_url(url)
                    remember_track_url(url)
                    content_type = (res.headers or {}).get("content-type", "")
                    if "json" not in content_type.lower() and not any(token in url.lower() for token in ("source", "stream", "playlist", "server", "embed")):
                        return
                    try:
                        walk_json(res.json())
                    except Exception:
                        return

                page.on("request", capture_request)
                page.on("response", capture_response)
                page.goto(watch_url, wait_until="domcontentloaded", timeout=self.runtime_capture_timeout_ms)
                page.wait_for_timeout(3500)

                click_selectors = [
                    "button:has-text('Play')",
                    "button:has-text('Watch')",
                    "a:has-text('Play')",
                    "a:has-text('Watch')",
                    "[aria-label*='Play' i]",
                    "[class*='play' i]:not(svg)",
                    "[class*='watch' i]",
                ]

                click_blockers = [
                    ".absolute.inset-0.z-50",
                    r".fixed.inset-0.z-\[150\]",
                    "[data-premid-title] .absolute.inset-0",
                ]

                def wait_for_click_blockers_to_clear(timeout_ms=2200):
                    for blocker_selector in click_blockers:
                        try:
                            blocker = page.locator(blocker_selector).first
                            if blocker.count() > 0:
                                blocker.wait_for(state="hidden", timeout=timeout_ms)
                        except Exception:
                            continue

                for selector in click_selectors:
                    try:
                        locator = page.locator(selector).first
                        if locator.count() > 0 and locator.is_visible(timeout=1000):
                            wait_for_click_blockers_to_clear()
                            try:
                                locator.click(timeout=2500)
                            except Exception:
                                locator.click(timeout=2500, force=True)
                            page.wait_for_timeout(3500)
                            break
                    except Exception as click_error:
                        print(f"Vixsrc click candidate skipped ({selector}): {click_error}")

                for frame in page.frames:
                    frame_url = (frame.url or "").strip()
                    if frame_url and frame_url != "about:blank" and frame_url != page.url:
                        iframe_urls.append(frame_url)

                iframe_handles = page.locator("iframe").element_handles()
                for handle in iframe_handles:
                    try:
                        src = handle.get_attribute("src") or handle.get_attribute("data-src")
                        if src:
                            iframe_urls.append(urllib.parse.urljoin(page.url, src))
                    except Exception:
                        continue

                for iframe_url in dict.fromkeys(iframe_urls):
                    remember_stream_url(iframe_url)
                    try:
                        follow_page = context.new_page()
                        follow_page.on("request", capture_request)
                        follow_page.on("response", capture_response)
                        follow_page.goto(iframe_url, wait_until="domcontentloaded", timeout=self.runtime_capture_timeout_ms)
                        follow_page.wait_for_timeout(4500)
                        follow_page.close()
                    except Exception as iframe_error:
                        print(f"Vixsrc iframe follow failed ({iframe_url}): {iframe_error}")

                page.wait_for_timeout(2500)
                browser.close()
        except Exception as e:
            print(f"Vixsrc browser extraction failed: {e}")
            return None

        if provider_payloads:
            payload = provider_payloads[0]
            payload.setdefault("detected_via", "vixsrc-runtime-json")
            payload.setdefault("page", watch_url)
            return payload

        sources = self._dedupe_sources(stream_urls)
        if sources:
            unique_tracks = []
            seen_tracks = set()
            for track in tracks:
                file_url = track.get("file")
                if file_url and file_url not in seen_tracks:
                    seen_tracks.add(file_url)
                    unique_tracks.append(track)
            return {
                "sources": sources,
                "tracks": unique_tracks,
                "encrypted": False,
                "detected_via": "vixsrc-runtime-network-intercept",
                "page": watch_url,
            }

        return None

    def get_stream(self, id, is_tv=False, season=None, episode=None, is_anime=False, sub_or_dub="sub", force_refresh=False):
        cache_key = (id, is_tv, season, episode, is_anime, sub_or_dub, self.base_url)
        cached = self.stream_cache.get(cache_key)
        if not force_refresh and cached and cached["expires_at"] > time.time():
            return self._annotate_expiring_sources(cached["result"])

        watch_url = self._build_vixsrc_watch_url(
            id=id,
            is_tv=is_tv,
            season=season,
            episode=episode,
            is_anime=is_anime,
            sub_or_dub=sub_or_dub,
        )
        result = self._capture_vixsrc_runtime_payload(watch_url)
        if result:
            result = self._resolve_indirect_sources(result, watch_url)
            result = self._annotate_expiring_sources(result)
            cache_ttl = self.stream_cache_ttl
            if result.get("expires_at"):
                cache_ttl = max(0, min(cache_ttl, result["expires_at"] - int(time.time()) - self.expiring_stream_refresh_margin_seconds))
            if cache_ttl > 0:
                self.stream_cache[cache_key] = {
                    "result": result,
                    "expires_at": time.time() + cache_ttl,
                }
            else:
                self.stream_cache.pop(cache_key, None)
            return result

        return None

if __name__ == "__main__":
    extractor = VidsrcExtractor()
    # Test with Fast X (movie)
    print(extractor.get_stream("385687"))
