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
STATUS_REPORT_HOURS = 8

# URLs
MAIN_STORE_URL = "https://onlinestore.mini.com.tr"
STOCK_LIST_URL = "https://onlinestore.mini.com.tr/stok-listesi?modelCodes=41GA"

# Target model
TARGET_MODEL = "COUNTRYMAN E"
TARGET_PACK = "Favoured"

# Tracking variables
check_count = 0
start_time = None
pack_counts = {}  # Track how many times each pack was seen

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
        await page.goto(MAIN_STORE_URL, wait_until="load", timeout=60000)
        await page.wait_for_timeout(5000)  # Wait for JS carousel to initialize
        
        # Accept cookies if present
        try:
            cookie_btn = page.locator("button:has-text('TÜMÜNÜ KABUL ET')")
            if await cookie_btn.is_visible(timeout=3000):
                await cookie_btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass  # Cookie banner might not appear
        
        # The carousel shows multiple models. We need to navigate to Countryman E
        # and check if THAT slide has Tasarla button.
        # Strategy: Click Next until we see "COUNTRYMAN E" as the main heading
        
        max_slides = 10
        found_countryman = False
        
        for i in range(max_slides):
            await page.wait_for_timeout(1500)  # Wait for slide transition
            
            # Get visible text on the page to find the current active model name
            # The active model name appears prominently in the carousel
            visible_text = await page.evaluate("document.body.innerText")
            
            # Check if Countryman E is the currently VISIBLE main model
            # Look for the model name pattern that indicates it's the active slide
            lines = visible_text.split('\n')
            is_countryman_e_slide = False
            
            for line in lines:
                line_upper = line.strip().upper()
                # The active model shows as "MINI COUNTRYMAN E" prominently
                if "MINI COUNTRYMAN E" in line_upper and "MINI COUNTRYMAN C" not in line_upper:
                    is_countryman_e_slide = True
                    break
            
            if is_countryman_e_slide:
                found_countryman = True
                logger.info(f"Found Countryman E slide at position {i}!")
                
                # Now check if this slide has both Otomobilleri Göster AND Tasarla
                # or just Otomobilleri Göster
                buttons_text = await page.locator('button').all_text_contents()
                buttons_text = [b.strip() for b in buttons_text if b.strip()]
                
                # Count how many Tasarla buttons are visible
                tasarla_count = sum(1 for b in buttons_text if 'Tasarla' in b)
                otomobil_count = sum(1 for b in buttons_text if 'Otomobilleri' in b)
                
                logger.info(f"Buttons visible - Tasarla: {tasarla_count}, Otomobilleri: {otomobil_count}")
                
                # Simple logic: We're on the Countryman E slide.
                # If there's at least 1 Tasarla button visible, Countryman E has Tasarla enabled.
                # (Previous models like Cooper are no longer visible at position 3)
                if tasarla_count >= 1:
                    logger.info("✅ TASARLA BUTTON FOUND FOR COUNTRYMAN E!")
                    return True, "Tasarla button is now available for Countryman E!"
                
                # No Tasarla button visible - only Otomobilleri Göster
                logger.info("Tasarla button not present for Countryman E")
                return False, "Tasarla button not available"
            
            # Click Next to go to next slide
            next_btn = page.locator("button:has-text('Next')")
            if await next_btn.count() > 0 and await next_btn.first.is_visible(timeout=2000):
                await next_btn.first.click()
            else:
                logger.warning(f"Next button not found at slide {i}")
                break
        
        if not found_countryman:
            logger.warning("Could not find Countryman E in carousel after checking all slides")
            return False, "Countryman E not found in carousel"
        
        return False, "Check completed"
        
    except Exception as e:
        logger.error(f"Error checking Tasarla button: {e}")
        return False, f"Error: {e}"


async def check_stock_for_favoured(page) -> tuple[bool, str, list]:
    """
    Check stock list for Favoured pack Countryman E.
    Also tracks all pack types found for status reports.
    
    Returns: (is_available, message, matching_vehicles)
    """
    global pack_counts
    
    logger.info("Checking stock for Favoured pack...")
    
    try:
        await page.goto(STOCK_LIST_URL, wait_until="load", timeout=60000)
        await page.wait_for_timeout(5000)
        
        # Accept cookies if present
        try:
            cookie_btn = page.locator("button:has-text('TÜMÜNÜ KABUL ET')")
            if await cookie_btn.is_visible(timeout=3000):
                await cookie_btn.click()
                await page.wait_for_timeout(1000)
        except Exception:
            pass
        
        # Get all visible text
        visible_text = await page.evaluate("document.body.innerText")
        
        # Extract pack names from the stock list
        # Packs typically appear as "John Cooper Works" or "Favoured" etc.
        packs_found = []
        lines = visible_text.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            # Look for known pack names
            if 'John Cooper Works' in line_stripped:
                packs_found.append('John Cooper Works')
            if 'Favoured' in line_stripped:
                packs_found.append('Favoured')
            if 'Essential' in line_stripped:
                packs_found.append('Essential')
            if 'Classic' in line_stripped:
                packs_found.append('Classic')
        
        # Get unique packs found this check (avoid counting duplicates from page text)
        unique_packs = set(packs_found)
        
        # Update pack counts - count once per check, not per text occurrence
        for pack in unique_packs:
            pack_counts[pack] = pack_counts.get(pack, 0) + 1
        
        if unique_packs:
            logger.info(f"Packs found in stock: {unique_packs}")
        else:
            logger.info("No packs found in stock list")
        
        # Check specifically for Favoured
        has_favoured = TARGET_PACK in packs_found
        
        if has_favoured:
            logger.info("✅ FAVOURED PACK FOUND IN STOCK!")
            
            # Get context lines for Favoured
            matching_info = []
            for line in lines:
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
    global check_count, start_time, pack_counts
    
    if not start_time:
        return
    
    uptime = datetime.now() - start_time
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    
    # Build pack summary
    pack_summary = ""
    if pack_counts:
        pack_lines = []
        for pack, count in sorted(pack_counts.items()):
            emoji = "⭐" if pack == TARGET_PACK else "📦"
            pack_lines.append(f"{emoji} {pack}: {count}x")
        pack_summary = "\n".join(pack_lines)
    else:
        pack_summary = "No packs found yet"
    
    message = (
        f"📊 <b>Status Report</b>\n\n"
        f"✅ Monitor is running\n"
        f"⏱ Uptime: {hours}h {minutes}m\n"
        f"🔍 Checks completed: {check_count}\n"
        f"📅 Next report in {STATUS_REPORT_HOURS}h\n\n"
        f"<b>Packs seen (Countryman E):</b>\n{pack_summary}\n\n"
        f"<i>Looking for: {TARGET_PACK} ⭐</i>"
    )
    
    await send_telegram_notification(message)
    logger.info(f"Status report sent - {check_count} checks, uptime {hours}h {minutes}m, packs: {pack_counts}")
    
    # Reset counters for next reporting period
    check_count = 0
    pack_counts = {}


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

