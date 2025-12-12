#!/usr/bin/env python3
"""
Mini Countryman E Favoured Pack Availability Monitor

Monitors the Mini Turkey online store for:
1. "Tasarla" button availability for Countryman E (enables preorder)
2. "Favoured" pack vehicles in stock list

Sends Telegram notifications when availability is detected.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

# ============================================================================
# CONFIGURATION - Edit these values
# ============================================================================

# Telegram Bot Configuration
# Create a bot via @BotFather on Telegram and get your chat ID via @userinfobot
TELEGRAM_BOT_TOKEN = "8559897411:AAHzGFFrMek5-Uwnnm9ksmCOM1WLbEdq2og"  # e.g., "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHAT_ID = "8245984629"    # e.g., "123456789"

# Email Configuration (optional fallback)
EMAIL_ENABLED = False
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = ""
EMAIL_PASSWORD = ""  # Use app password for Gmail

# Check interval in minutes (be respectful to the server)
CHECK_INTERVAL_MINUTES = 5

# Status report interval (send a "still alive" report every X hours)
STATUS_REPORT_HOURS = 24

# URLs
MAIN_STORE_URL = "https://onlinestore.mini.com.tr"
STOCK_LIST_URL = "https://onlinestore.mini.com.tr/stok-listesi?modelCodes=41GA"

# Target model
TARGET_MODEL = "COUNTRYMAN E"
TARGET_PACK = "Favoured"

# Tracking variables
check_count = 0
start_time = None

# ============================================================================
# Logging Setup
# ============================================================================

import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mini_monitor.log'),
        logging.StreamHandler(sys.stdout)  # Use stdout instead of stderr
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Notification Functions
# ============================================================================

async def send_telegram_notification(message: str):
    """Send notification via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured. Skipping notification.")
        return False
    
    try:
        import httpx
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully!")
                return True
            else:
                logger.error(f"Telegram error: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False


def send_email_notification(subject: str, message: str):
    """Send notification via email."""
    if not EMAIL_ENABLED or not EMAIL_ADDRESS:
        return False
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info("Email notification sent!")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


async def notify(title: str, message: str, link: str = None):
    """Send notification through all configured channels."""
    full_message = f"🚗 <b>{title}</b>\n\n{message}"
    if link:
        full_message += f"\n\n🔗 <a href='{link}'>Hemen Sipariş Ver</a>"
    
    # Try Telegram first (instant)
    await send_telegram_notification(full_message)
    
    # Email fallback
    plain_message = f"{title}\n\n{message}"
    if link:
        plain_message += f"\n\nLink: {link}"
    send_email_notification(f"MINI Monitor: {title}", plain_message)
    
    # macOS desktop notification as backup
    try:
        import subprocess
        subprocess.run([
            'osascript', '-e',
            f'display notification "{message}" with title "{title}" sound name "Glass"'
        ], check=False)
    except Exception:
        pass

# ============================================================================
# Check Functions
# ============================================================================

async def check_tasarla_button(page) -> tuple[bool, str]:
    """
    Check if "Tasarla" button is available for Countryman E.
    
    Returns: (is_available, message)
    """
    logger.info("Checking for Tasarla button on Countryman E...")
    
    try:
        await page.goto(MAIN_STORE_URL, wait_until="networkidle", timeout=30000)
        
        # Accept cookies if present
        try:
            cookie_btn = page.locator("button:has-text('TÜMÜNÜ KABUL ET')")
            if await cookie_btn.is_visible(timeout=3000):
                await cookie_btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass  # Cookie banner might not appear
        
        # Find the carousel and navigate to Countryman E
        # The carousel has Next/Previous buttons - need to find Countryman E slide
        max_slides = 10
        found_countryman = False
        
        for i in range(max_slides):
            # Check current slide content
            page_content = await page.content()
            
            if "COUNTRYMAN E" in page_content.upper():
                found_countryman = True
                logger.info("Found Countryman E slide!")
                
                # Now check if Tasarla button exists
                tasarla_button = page.locator("button:has-text('Tasarla'), a:has-text('Tasarla')")
                
                if await tasarla_button.count() > 0:
                    # Verify it's visible (not hidden)
                    if await tasarla_button.first.is_visible(timeout=2000):
                        logger.info("✅ TASARLA BUTTON FOUND!")
                        return True, "Tasarla button is now available for Countryman E!"
                
                # Button not found on Countryman E slide
                logger.info("Tasarla button not present on Countryman E slide")
                return False, "Tasarla button not available"
            
            # Click Next to go to next slide
            next_btn = page.locator("button[aria-label='Next'], button:has-text('›')")
            if await next_btn.count() > 0 and await next_btn.first.is_visible():
                await next_btn.first.click()
                await page.wait_for_timeout(1500)  # Wait for animation
            else:
                break
        
        if not found_countryman:
            logger.warning("Could not find Countryman E in carousel")
            return False, "Countryman E not found in carousel"
        
        return False, "Check completed"
        
    except Exception as e:
        logger.error(f"Error checking Tasarla button: {e}")
        return False, f"Error: {e}"


async def check_stock_for_favoured(page) -> tuple[bool, str, list]:
    """
    Check stock list for Favoured pack Countryman E.
    
    Returns: (is_available, message, matching_vehicles)
    """
    logger.info("Checking stock for Favoured pack...")
    
    try:
        await page.goto(STOCK_LIST_URL, wait_until="networkidle", timeout=30000)
        
        # Accept cookies if present
        try:
            cookie_btn = page.locator("button:has-text('TÜMÜNÜ KABUL ET')")
            if await cookie_btn.is_visible(timeout=3000):
                await cookie_btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass
        
        # Wait for stock list to load
        await page.wait_for_timeout(3000)
        
        # Use JavaScript to check VISIBLE text content (not raw HTML which may have false positives)
        has_favoured = await page.evaluate(
            f"document.body.innerText.toLowerCase().includes('{TARGET_PACK.lower()}')"
        )
        
        if has_favoured:
            logger.info("✅ FAVOURED PACK FOUND IN STOCK!")
            
            # Try to extract more details about matching vehicles
            matching_info = []
            
            # Get all visible text and look for context around "Favoured"
            visible_text = await page.evaluate("document.body.innerText")
            
            # Look for lines containing "Favoured"
            for line in visible_text.split('\n'):
                if TARGET_PACK.lower() in line.lower():
                    matching_info.append(line.strip()[:200])
            
            if not matching_info:
                matching_info = ["Favoured pack detected on page - check stock list!"]
            
            return True, f"Found Countryman E with Favoured pack!", matching_info
        
        logger.info("No Favoured pack in current stock")
        return False, "No Favoured pack available", []
        
    except Exception as e:
        logger.error(f"Error checking stock: {e}")
        return False, f"Error: {e}", []


# ============================================================================
# Main Monitor Loop
# ============================================================================

async def run_checks():
    """Run all availability checks."""
    logger.info("=" * 50)
    logger.info(f"Starting check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="tr-TR"
        )
        page = await context.new_page()
        
        try:
            # Check 1: Tasarla button
            tasarla_available, tasarla_msg = await check_tasarla_button(page)
            
            if tasarla_available:
                await notify(
                    "🎉 Tasarla Butonu Aktif!",
                    "Mini Countryman E için Tasarla butonu artık aktif! Hemen tasarlayıp sipariş verebilirsin!",
                    MAIN_STORE_URL
                )
            
            # Check 2: Stock availability
            stock_available, stock_msg, vehicles = await check_stock_for_favoured(page)
            
            if stock_available:
                vehicle_info = "\n".join(vehicles[:3])  # Show first 3 matches
                await notify(
                    "🎉 Favoured Paket Stokta!",
                    f"Mini Countryman E Favoured paket stokta bulundu!\n\n{vehicle_info}",
                    STOCK_LIST_URL
                )
            
            # Summary
            logger.info(f"Check complete - Tasarla: {'✅' if tasarla_available else '❌'}, Stock: {'✅' if stock_available else '❌'}")
            
            return tasarla_available, stock_available
            
        finally:
            await browser.close()


async def send_status_report():
    """Send a status report to Telegram."""
    global check_count, start_time
    
    if not start_time:
        return
    
    uptime = datetime.now() - start_time
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    
    message = (
        f"📊 <b>Status Report</b>\n\n"
        f"✅ Monitor is running\n"
        f"⏱ Uptime: {hours}h {minutes}m\n"
        f"🔍 Checks completed: {check_count}\n"
        f"📅 Next report in {STATUS_REPORT_HOURS}h\n\n"
        f"<i>Tasarla: ❌ | Stock: ❌</i>"
    )
    
    await send_telegram_notification(message)
    logger.info(f"Status report sent - {check_count} checks, uptime {hours}h {minutes}m")


async def main():
    """Main entry point."""
    global check_count, start_time
    
    start_time = datetime.now()
    check_count = 0
    last_report_time = datetime.now()
    
    logger.info("🚗 Mini Countryman E Favoured Monitor Started")
    logger.info(f"Target: {TARGET_MODEL} - {TARGET_PACK} pack")
    logger.info(f"Check interval: {CHECK_INTERVAL_MINUTES} minutes")
    logger.info(f"Status report interval: {STATUS_REPORT_HOURS} hours")
    
    # Validate Telegram config
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️  Telegram not configured! Edit mini_monitor.py to add your bot token and chat ID.")
        logger.warning("   See README.md for setup instructions.")
    else:
        # Send test notification
        await send_telegram_notification(
            "🚗 <b>Mini Monitor Started!</b>\n\n"
            f"Monitoring Countryman E - {TARGET_PACK} pack\n"
            f"Check interval: {CHECK_INTERVAL_MINUTES} min\n"
            f"Status reports every {STATUS_REPORT_HOURS}h"
        )
    
    # Initial check with error handling
    try:
        await run_checks()
        check_count += 1
    except Exception as e:
        logger.error(f"Initial check failed: {e}")
        await send_telegram_notification(f"⚠️ Initial check failed: {e}")
    
    # Continuous monitoring
    while True:
        logger.info(f"Next check in {CHECK_INTERVAL_MINUTES} minutes...")
        await asyncio.sleep(CHECK_INTERVAL_MINUTES * 60)
        
        try:
            tasarla, stock = await run_checks()
            check_count += 1
            
            # If either is available, notify!
            if tasarla or stock:
                logger.info("🎉 AVAILABILITY DETECTED! Continuing monitoring...")
            
            # Check if it's time for a status report
            hours_since_report = (datetime.now() - last_report_time).total_seconds() / 3600
            if hours_since_report >= STATUS_REPORT_HOURS:
                await send_status_report()
                last_report_time = datetime.now()
                
        except Exception as e:
            logger.error(f"Error during check: {e}")
            # Don't crash - just continue to next check
            await asyncio.sleep(60)  # Wait a minute before retrying


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nMonitor stopped by user.")
    except Exception as e:
        # Log fatal errors but don't crash immediately
        logging.error(f"Fatal error: {e}")
        import time
        time.sleep(300)  # Wait 5 minutes before Railway restarts

