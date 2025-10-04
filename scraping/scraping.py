import random
import asyncio
from urllib.parse import urlparse
from playwright.async_api import async_playwright, BrowserContext
from dataclasses import dataclass
from models.models import ScrapedSites

@dataclass
class BrowserPersona:
    user_agent: str
    platform: str
    language: str
    languages: list[str]
    timezone: str
    webgl_vendor: str
    webgl_renderer: str
    screen_width: int
    screen_height: int
    cores: int
    memory: int
    
ATTEMPTS = 3
SEMAPHORE = asyncio.Semaphore(5) 

BLOCKED_RESOURCE_TYPES = {
    "stylesheet", "font", "image", "media", "manifest", "other", "csp_report", "preflight"
}

BLOCKED_DOMAINS = {
    "google-analytics.com", "doubleclick.net", "facebook.net", "ads.google.com",
    "googletagmanager.com", "googlesyndication.com", "adservice.google.com",
    "scorecardresearch.com", "adobedtm.com"
}  

ARGS = [
    "--disable-blink-features=AutomationControlled", 
    "--disable-infobars", 
    "--window-position=0,0", 
    "--no-first-run",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials"
]

BROWSER_PERSONAS = [
    BrowserPersona(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        platform="Win32",
        language="en-US",
        languages=["en-US", "en"],
        timezone="America/New_York",
        webgl_vendor="Google Inc.",
        webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics 630, OpenGL 4.1)",
        screen_width=1920,
        screen_height=1080,
        cores=8,
        memory=16
    ),
    BrowserPersona(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        platform="MacIntel",
        language="en-US",
        languages=["en-US", "en"],
        timezone="America/Los_Angeles",
        webgl_vendor="Intel Inc.",
        webgl_renderer="Intel Iris OpenGL Engine",
        screen_width=2560,
        screen_height=1440,
        cores=8,
        memory=16
    ),
    BrowserPersona(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
        platform="Win32",
        language="en-US",
        languages=["en-US", "en"],
        timezone="America/Chicago",
        webgl_vendor="NVIDIA Corporation",
        webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti, OpenGL 4.5)",
        screen_width=1920,
        screen_height=1080,
        cores=12,
        memory=16
    ),
    BrowserPersona(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        platform="Linux x86_64",
        language="en-US",
        languages=["en-US", "en"],
        timezone="America/New_York",
        webgl_vendor="AMD",
        webgl_renderer="ANGLE (AMD, AMD Radeon RX 580, OpenGL 4.5)",
        screen_width=1920,
        screen_height=1080,
        cores=16,
        memory=16
    ),
    BrowserPersona(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        platform="MacIntel",
        language="en-US",
        languages=["en-US", "en"],
        timezone="America/Los_Angeles",
        webgl_vendor="Intel Inc.",
        webgl_renderer="Intel Iris OpenGL Engine",
        screen_width=1440,
        screen_height=900,
        cores=8,
        memory=8
    ),
    BrowserPersona(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        platform="Win32",
        language="en-GB",
        languages=["en-GB", "en"],
        timezone="Europe/London",
        webgl_vendor="Google Inc.",
        webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics 630, OpenGL 4.1)",
        screen_width=1366,
        screen_height=768,
        cores=4,
        memory=8
    ),
    BrowserPersona(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        platform="Win32",
        language="fr-FR",
        languages=["fr-FR", "fr"],
        timezone="Europe/Paris",
        webgl_vendor="NVIDIA Corporation",
        webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Ti, OpenGL 4.5)",
        screen_width=1920,
        screen_height=1080,
        cores=8,
        memory=16
    ),
]

NO_BOT_SCRIPT_TEMPLATE = """
Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});

Object.defineProperty(navigator, 'platform', {{get: () => '{platform}'}});

Object.defineProperty(navigator, 'language', {{get: () => '{language}'}});
Object.defineProperty(navigator, 'languages', {{get: () => {languages}}});

window.chrome = {{
    runtime: {{}},
    loadTimes: function() {{}},
    csi: function() {{}},
    app: {{}}
}};

Object.defineProperty(navigator, 'plugins', {{
    get: () => {{
        return [
            {{name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'}},
            {{name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''}},
            {{name: 'Native Client', filename: 'internal-nacl-plugin', description: ''}}
        ];
    }}
}});

const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({{state: Notification.permission}}) :
        originalQuery(parameters)
);

Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {cores}}});
Object.defineProperty(navigator, 'deviceMemory', {{get: () => {memory}}});

const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {{
    if (parameter === 37445) return '{webgl_vendor}';
    if (parameter === 37446) return '{webgl_renderer}';
    return getParameter.call(this, parameter);
}};

Object.defineProperty(navigator, 'connection', {{
    get: () => ({{
        effectiveType: '4g',
        rtt: {rtt},
        downlink: {downlink},
        saveData: false
    }})
}});

delete navigator.__proto__.webdriver;

const originalToString = Function.prototype.toString;
Function.prototype.toString = function() {{
    if (this === navigator.permissions.query) {{
        return 'function query() {{ [native code] }}';
    }}
    return originalToString.call(this);
}};

const originalGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type, attributes) {{
    const context = originalGetContext.call(this, type, attributes);
    if (type === '2d') {{
        const originalFillText = context.fillText;
        context.fillText = function(text, x, y, maxWidth) {{
            const noise = {canvas_noise};
            return originalFillText.call(this, text, x + noise, y + noise, maxWidth);
        }};
    }}
    return context;
}};

const AudioContext = window.AudioContext || window.webkitAudioContext;
if (AudioContext) {{
    const originalCreateOscillator = AudioContext.prototype.createOscillator;
    AudioContext.prototype.createOscillator = function() {{
        const oscillator = originalCreateOscillator.call(this);
        const originalStart = oscillator.start;
        oscillator.start = function(when) {{
            const noise = {audio_noise};
            return originalStart.call(this, when + noise);
        }};
        return oscillator;
    }};
}}

Object.defineProperty(window, 'screen', {{
    get: () => ({{
        width: {screen_width},
        height: {screen_height},
        availWidth: {screen_width},
        availHeight: {screen_height} - 40,
        colorDepth: 24,
        pixelDepth: 24
    }})
}});

Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', {{
    value: function() {{
        return {{
            locale: '{language}',
            calendar: 'gregory',
            numberingSystem: 'latn',
            timeZone: '{timezone}',
            year: 'numeric',
            month: 'numeric',
            day: 'numeric'
        }};
    }}
}});

navigator.getBattery = () => {{
    return Promise.resolve({{
        charging: {battery_charging},
        chargingTime: Infinity,
        dischargingTime: {battery_time},
        level: {battery_level}
    }});
}};
"""

def get_no_bot_script(persona: BrowserPersona):
    return NO_BOT_SCRIPT_TEMPLATE.format(
        platform=persona.platform,
        language=persona.language,
        languages=f"{persona.languages}",
        cores=persona.cores,
        memory=persona.memory,
        webgl_vendor=persona.webgl_vendor,
        webgl_renderer=persona.webgl_renderer,
        rtt=random.randint(20, 100),
        downlink=round(random.uniform(1.5, 10.0), 2),
        canvas_noise=round(random.uniform(-0.0001, 0.0001), 6),
        audio_noise=round(random.uniform(0, 0.00001), 8),
        screen_width=persona.screen_width,
        screen_height=persona.screen_height,
        timezone=persona.timezone,
        battery_charging=str(random.choice([True, False])).lower(),
        battery_time=random.randint(3600, 28800),
        battery_level=round(random.uniform(0.2, 1.0), 2)
    )

def normalize_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc

async def route_filter(route):
    try:
        req = route.request
        url = req.url
        resource_type = req.resource_type
        
        if resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
        elif any(domain in url for domain in BLOCKED_DOMAINS):
            await route.abort()
        else:
            await route.continue_()
    except Exception as e:
        if "closed" not in str(e).lower():
            print(f"Route filter error: {e}")

async def simulate_human_behavior(page):
    scroll_patterns = [
        [(0, 200), (0, 400), (0, 300)],
        [(0, 150), (0, 350), (0, 600)],
        [(0, 100), (0, -50), (0, 200)],
        [(0, 250), (0, 150), (0, 400)],
    ]
    
    pattern = random.choice(scroll_patterns)
    for x, y in pattern:
        try:
            await page.evaluate(f"window.scrollBy({x}, {y})")
            await asyncio.sleep(random.uniform(0.2, 0.6))
        except Exception:
            break
    
    for _ in range(random.randint(2, 4)):
        try:
            await page.mouse.move(
                random.randint(100, 800),
                random.randint(100, 600),
                steps=random.randint(10, 30)
            )
            await asyncio.sleep(random.uniform(0.2, 0.6))
        except Exception:
            break
    
    if random.random() < 0.3:
        try:
            await page.evaluate("""
                () => {
                    const x = Math.random() * window.innerWidth * 0.8;
                    const y = Math.random() * window.innerHeight * 0.8;
                    document.elementFromPoint(x, y);
                }
            """)
        except Exception:
            pass
        
async def scrape_site(browser: BrowserContext, url: str, persona: BrowserPersona) -> ScrapedSites:
    async with SEMAPHORE:
        for attempt in range(ATTEMPTS):
            page = None
            try:
                page = await browser.new_page()
                
                await page.add_init_script(get_no_bot_script(persona))
                
                await page.set_extra_http_headers({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": f"{persona.language},{persona.languages[1]};q=0.9",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Cache-Control": "max-age=0"
                })
                
                await page.route("**/*", route_filter)
               
                print(f"Scraping {url}")
                await page.goto(url, timeout=60000)
                
                await asyncio.sleep(random.uniform(0.2, 0.6))
                
                await simulate_human_behavior(page)
                
                content = await page.content()
                
                await asyncio.sleep(random.uniform(0.2, 0.6))
                
                return ScrapedSites(
                    url=url,
                    content=content
                )
            
            except Exception as e:
                error_msg = str(e).lower()
                
                if "timeout" in error_msg:
                    print(f"Attempt {attempt + 1} failed for {url}: Timeout")
                elif "closed" in error_msg:
                    print(f"Attempt {attempt + 1} failed for {url}: Page/Context closed")
                else:
                    print(f"Attempt {attempt + 1} failed for {url}: {e}")
                
                if attempt == (ATTEMPTS - 1):
                    return ScrapedSites(url=url, content=None)
                
                await asyncio.sleep(2 ** attempt * random.uniform(1.5, 3.0))
           
            finally:
                if page and not page.is_closed():
                    try:
                        await page.close()
                    except Exception:
                        pass
        
        return ScrapedSites(url=url, content=None)

async def scrape_sites(urls: list[str], same_site = False) -> list[ScrapedSites]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=ARGS,
            headless=True
        )
        
        persona = random.choice(BROWSER_PERSONAS)
        
        geo_map = {
            "America/New_York": (40.7128, -74.0060),
            "America/Chicago": (41.8781, -87.6298),
            "America/Los_Angeles": (34.0522, -118.2437),
            "Europe/London": (51.5074, -0.1278),
            "Europe/Paris": (48.8566, 2.3522),
        }
        lat, lon = geo_map.get(persona.timezone, (40.7128, -74.0060))
        
        context = await browser.new_context(
            user_agent=persona.user_agent,
            locale=persona.language,
            viewport={"width": persona.screen_width, "height": persona.screen_height},
            screen={"width": persona.screen_width, "height": persona.screen_height},
            color_scheme='dark',
            permissions=[],
            geolocation={"latitude": lat, "longitude": lon},
            timezone_id=persona.timezone,
        )

        try:
            if same_site is False:
                results = await asyncio.gather(
                    *[scrape_site(context, url, persona) for url in urls],
                    return_exceptions=True
                )
                
                final_results = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"Failed to scrape {urls[i]}: {result}")
                        final_results.append(ScrapedSites(url=urls[i], content=None))
                    else:
                        final_results.append(result)
                
                return final_results
            else:
                results = []
                for url in urls:
                    try:
                        result = await scrape_site(context, url, persona)
                        results.append(result)
                        
                        await asyncio.sleep(random.uniform(0.2, 0.6))
                    except Exception as e:
                        print(f"Failed to scrape {url}: {e}")
                        results.append(ScrapedSites(url=url, content=None))
                
                return results
        finally:
            try:
                await context.close()
                await browser.close()
            except Exception:
                pass