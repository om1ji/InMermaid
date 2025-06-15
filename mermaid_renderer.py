import asyncio
import base64
import hashlib
import logging
from io import BytesIO
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, Page
from PIL import Image

logger = logging.getLogger(__name__)

class MermaidRenderer:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.cache = {}
        
    async def start(self):
        """Initialize the browser"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            logger.info("Mermaid renderer started successfully")
        except Exception as e:
            logger.error(f"Failed to start Mermaid renderer: {e}")
            raise
    
    async def stop(self):
        """Close the browser"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        logger.info("Mermaid renderer stopped")
    
    def _get_cache_key(self, mermaid_code: str) -> str:
        """Generate cache key for mermaid code"""
        return hashlib.md5(mermaid_code.encode()).hexdigest()
    
    async def render_diagram(self, mermaid_code: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Render Mermaid diagram to PNG image
        Returns: (image_bytes, error_message)
        """
        if not self.browser:
            return None, "Renderer not initialized"
        
        cache_key = self._get_cache_key(mermaid_code)
        if cache_key in self.cache:
            logger.info("Returning cached result")
            return self.cache[cache_key]
        
        page = None
        try:
            page = await self.browser.new_page()
            
            await page.set_viewport_size({"width": 1200, "height": 800})
            
            html_content = self._create_html_content(mermaid_code)
            
            await page.set_content(html_content)
            
            try:
                # Wait for either success or error
                await page.wait_for_function(
                    "window.mermaidReady === true || window.mermaidError !== undefined",
                    timeout=10000
                )
                
                # Check if there was an error
                error_message = await page.evaluate("window.mermaidError")
                if error_message:
                    result = (None, f"Mermaid error: {error_message}")
                    self.cache[cache_key] = result
                    return result
                
            except Exception as e:
                logger.error(f"Timeout waiting for Mermaid: {e}")
                result = (None, "Failed to render diagram: timeout")
                self.cache[cache_key] = result
                return result
            
            svg_element = await page.query_selector('#mermaid-container svg')
            if not svg_element:
                result = (None, "Failed to find rendered diagram")
                self.cache[cache_key] = result
                return result
            
            bbox = await svg_element.bounding_box()
            if not bbox:
                result = (None, "Failed to get diagram dimensions")
                self.cache[cache_key] = result
                return result
            
            padding = 20
            screenshot_bytes = await page.screenshot(
                clip={
                    "x": max(0, bbox["x"] - padding),
                    "y": max(0, bbox["y"] - padding),
                    "width": bbox["width"] + 2 * padding,
                    "height": bbox["height"] + 2 * padding
                },
                type="png"
            )
            
            optimized_bytes = await self._optimize_image(screenshot_bytes)
            
            result = (optimized_bytes, None)
            self.cache[cache_key] = result
            return result
            
        except Exception as e:
            logger.error(f"Error rendering Mermaid diagram: {e}")
            result = (None, f"Rendering error: {str(e)}")
            self.cache[cache_key] = result
            return result
        finally:
            if page:
                await page.close()
    
    def _create_html_content(self, mermaid_code: str) -> str:
        """Create HTML content with Mermaid diagram"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    font-family: Arial, sans-serif;
                    background: white;
                    min-height: 100vh;
                }}
                #mermaid-container {{
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 400px;
                }}
                .mermaid {{
                    background: white;
                }}
                .error {{
                    color: red;
                    font-weight: bold;
                    padding: 20px;
                    border: 2px solid red;
                    border-radius: 5px;
                    background: #ffe6e6;
                    max-width: 600px;
                }}
                #status {{
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    padding: 5px 10px;
                    background: #f0f0f0;
                    border-radius: 3px;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div id="status">Loading...</div>
            <div id="mermaid-container">
                <div class="mermaid" id="diagram">
{mermaid_code}
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"></script>
            <script>
                console.log('Starting Mermaid initialization...');
                document.getElementById('status').textContent = 'Initializing...';
                
                // Wait for mermaid to be available
                function waitForMermaid() {{
                    return new Promise((resolve, reject) => {{
                        let attempts = 0;
                        const maxAttempts = 50;
                        
                        function check() {{
                            attempts++;
                            if (typeof mermaid !== 'undefined') {{
                                resolve();
                            }} else if (attempts >= maxAttempts) {{
                                reject(new Error('Mermaid failed to load'));
                            }} else {{
                                setTimeout(check, 100);
                            }}
                        }}
                        check();
                    }});
                }}
                
                async function initAndRender() {{
                    try {{
                        console.log('Waiting for Mermaid to load...');
                        await waitForMermaid();
                        
                        console.log('Initializing Mermaid...');
                        mermaid.initialize({{
                            startOnLoad: false,
                            theme: 'default',
                            securityLevel: 'loose',
                            flowchart: {{
                                useMaxWidth: false,
                                htmlLabels: true
                            }},
                            sequence: {{
                                useMaxWidth: false
                            }},
                            class: {{
                                useMaxWidth: false
                            }}
                        }});
                        
                        console.log('Rendering diagram...');
                        document.getElementById('status').textContent = 'Rendering...';
                        
                        const element = document.getElementById('diagram');
                        const diagramCode = `{mermaid_code}`;
                        
                        console.log('Diagram code:', diagramCode);
                        
                        const {{svg}} = await mermaid.render('generatedDiagram', diagramCode);
                        
                        element.innerHTML = svg;
                        document.getElementById('status').textContent = 'Ready';
                        console.log('Diagram rendered successfully');
                        
                        // Signal that rendering is complete
                        window.mermaidReady = true;
                        
                    }} catch (error) {{
                        console.error('Mermaid render error:', error);
                        document.getElementById('status').textContent = 'Error';
                        document.getElementById('mermaid-container').innerHTML = 
                            '<div class="error">Syntax Error: ' + error.message + '</div>';
                        window.mermaidError = error.message;
                    }}
                }}
                
                // Start when page is loaded
                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', initAndRender);
                }} else {{
                    initAndRender();
                }}
            </script>
        </body>
        </html>
        """
    
    async def _optimize_image(self, image_bytes: bytes) -> bytes:
        try:
            image = Image.open(BytesIO(image_bytes))
            
            if image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image, mask=image.split()[-1])
                image = background
            
            output = BytesIO()
            image.save(output, format='PNG', optimize=True, quality=85)
            return output.getvalue()
        except Exception as e:
            logger.warning(f"Failed to optimize image: {e}")
            return image_bytes

renderer = MermaidRenderer() 