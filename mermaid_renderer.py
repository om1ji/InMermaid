import asyncio
import hashlib
import logging
import os
from collections import OrderedDict
from io import BytesIO
from typing import Optional, Tuple

from PIL import Image
from playwright.async_api import Browser, Page, async_playwright

logger = logging.getLogger(__name__)

MERMAID_VERSION = "10.6.1"
# Bundled into the Docker image; locally falls back to the CDN
MERMAID_JS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "static", "mermaid.min.js"
)
MERMAID_CDN_URL = (
    f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"
)

RENDER_TIMEOUT = 10
CACHE_SIZE = 256

PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: white;
        }
        #mermaid-container {
            display: inline-block;
            padding: 20px;
            background: white;
        }
    </style>
</head>
<body>
    <div id="mermaid-container"></div>
</body>
</html>
"""

INIT_JS = """
() => {
    mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'strict',
        flowchart: { useMaxWidth: false, htmlLabels: true },
        sequence: { useMaxWidth: false },
        class: { useMaxWidth: false }
    });
}
"""

# The diagram code is passed as an argument, never interpolated into JS/HTML
RENDER_JS = """
async ([id, code]) => {
    const container = document.getElementById('mermaid-container');
    container.innerHTML = '';
    try {
        const { svg } = await mermaid.render(id, code);
        container.innerHTML = svg;
        return null;
    } catch (error) {
        return error.message || String(error);
    } finally {
        // mermaid leaves its temporary element behind when parsing fails
        document.getElementById('d' + id)?.remove();
    }
}
"""


class MermaidRenderer:
    def __init__(self):
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.cache: OrderedDict[str, tuple[bytes | None, str | None]] = (
            OrderedDict()
        )
        # One page renders one diagram at a time
        self.lock = asyncio.Lock()
        self.render_counter = 0

    async def start(self):
        """Initialize the browser and a page with mermaid preloaded"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            await self._open_page()
            logger.info("Mermaid renderer started successfully")
        except Exception as e:
            logger.error(f"Failed to start Mermaid renderer: {e}")
            raise

    async def _open_page(self):
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass

        self.page = await self.browser.new_page(viewport={"width": 1200, "height": 800})
        await self.page.set_content(PAGE_HTML)

        if os.path.exists(MERMAID_JS_PATH):
            await self.page.add_script_tag(path=MERMAID_JS_PATH)
        else:
            logger.warning(f"{MERMAID_JS_PATH} not found, loading mermaid from CDN")
            await self.page.add_script_tag(url=MERMAID_CDN_URL)

        await self.page.evaluate(INIT_JS)

    async def stop(self):
        """Close the browser"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, "playwright"):
            await self.playwright.stop()
        logger.info("Mermaid renderer stopped")

    def _get_cache_key(self, mermaid_code: str) -> str:
        """Generate cache key for mermaid code"""
        return hashlib.md5(mermaid_code.encode()).hexdigest()

    def _cache_put(self, key: str, result: tuple[bytes | None, str | None]):
        self.cache[key] = result
        self.cache.move_to_end(key)
        if len(self.cache) > CACHE_SIZE:
            self.cache.popitem(last=False)

    async def render_diagram(
        self, mermaid_code: str
    ) -> tuple[bytes | None, str | None]:
        """
        Render Mermaid diagram to PNG image
        Returns: (image_bytes, error_message)
        """
        if not self.browser:
            return None, "Renderer not initialized"

        cache_key = self._get_cache_key(mermaid_code)
        if cache_key in self.cache:
            logger.info("Returning cached result")
            self.cache.move_to_end(cache_key)
            return self.cache[cache_key]

        async with self.lock:
            try:
                result = await asyncio.wait_for(
                    self._render(mermaid_code), RENDER_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.error("Timeout rendering Mermaid diagram, reopening page")
                await self._reopen_page()
                return None, "Failed to render diagram: timeout"
            except Exception as e:
                logger.error(f"Error rendering Mermaid diagram: {e}")
                await self._reopen_page()
                return None, f"Rendering error: {e!s}"

        self._cache_put(cache_key, result)
        return result

    async def _reopen_page(self):
        try:
            await self._open_page()
        except Exception as e:
            logger.error(f"Failed to reopen renderer page: {e}")

    async def _render(self, mermaid_code: str) -> tuple[bytes | None, str | None]:
        self.render_counter += 1
        diagram_id = f"diagram{self.render_counter}"

        error_message = await self.page.evaluate(RENDER_JS, [diagram_id, mermaid_code])
        if error_message:
            return None, f"Mermaid error: {error_message}"

        container = await self.page.query_selector("#mermaid-container")
        if not container or not await container.query_selector("svg"):
            return None, "Failed to find rendered diagram"

        screenshot_bytes = await container.screenshot(type="png")
        optimized_bytes = await self._optimize_image(screenshot_bytes)
        return optimized_bytes, None

    async def _optimize_image(self, image_bytes: bytes) -> bytes:
        try:
            image = Image.open(BytesIO(image_bytes))

            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background

            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
            return output.getvalue()
        except Exception as e:
            logger.warning(f"Failed to optimize image: {e}")
            return image_bytes


renderer = MermaidRenderer()
