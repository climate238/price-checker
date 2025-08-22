# -*- coding: utf-8 -*-
"""Scheduled Price Checker with Logging and Email Notifications - GitHub Actions Compatible

Automatically runs price checking at scheduled times and sends email alerts when criteria is met.
Modified for GitHub Actions environment.
"""

import time
import schedule
import logging
from datetime import datetime
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from selenium_stealth import stealth
import re

# Default Configuration (can be overridden by environment variables)
URL = "https://sameday.costco.com/store/costco/products/19230835-kirkland-signature-wild-alaskan-cod-individually-wrapped-2-lb-2-lb"
TARGET_PRICE = 21.00
ZIP_CODE = "78726"

# Email Configuration (will be loaded from environment variables)
RECIPIENT_EMAIL = "climate127@gmail.com"
SENDER_EMAIL = ""  # Will be set from environment
SENDER_PASSWORD = ""  # Will be set from environment
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def load_config_from_env():
    """Load configuration from environment variables (for GitHub Actions)"""
    global SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL, TARGET_PRICE, ZIP_CODE
    
    # Override with environment variables if they exist
    SENDER_EMAIL = os.getenv('SENDER_EMAIL', SENDER_EMAIL)
    SENDER_PASSWORD = os.getenv('SENDER_PASSWORD', SENDER_PASSWORD)
    RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', RECIPIENT_EMAIL)
    
    target_price_env = os.getenv('TARGET_PRICE')
    if target_price_env:
        try:
            TARGET_PRICE = float(target_price_env)
        except ValueError:
            pass
    
    zip_code_env = os.getenv('ZIP_CODE')
    if zip_code_env:
        ZIP_CODE = zip_code_env

# --- REVISED SCRIPT PATH LOGIC ---
# Get the absolute path of the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Logging and Data configuration (now relative to the script's location)
LOG_DIR = os.path.join(SCRIPT_DIR, "price_logs")
DATA_DIR = os.path.join(SCRIPT_DIR, "price_data")

def setup_logging():
    """Set up logging to file and console"""
    # Create directories if they don't exist
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Create log filename with date
    log_filename = os.path.join(LOG_DIR, f"price_checker_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    return logging.getLogger(__name__)

def send_price_alert_email(result_data):
    """Send email notification when price criteria is met"""
    logger = logging.getLogger(__name__)
    
    # Check if email credentials are configured
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.warning("Email credentials not configured. Skipping email notification.")
        logger.info("Please configure SENDER_EMAIL and SENDER_PASSWORD environment variables.")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = f"🚨 PRICE ALERT: Costco item on sale - ${result_data['price']:.2f}"
        
        # Create HTML email content
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .alert {{ background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .success {{ background-color: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .info {{ background-color: #e2e3e5; border: 1px solid #d6d8db; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .price {{ font-size: 24px; font-weight: bold; color: #28a745; }}
                .target {{ font-size: 18px; color: #dc3545; }}
                .button {{ 
                    background-color: #007bff; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    display: inline-block;
                    margin: 10px 0;
                }}
            </style>
        </head>
        <body>
            <h2>🚨 COSTCO PRICE ALERT!</h2>
            
            <div class="alert">
                <h3>Price Drop Detected!</h3>
                <p>The price has dropped below your target threshold.</p>
            </div>
            
            <div class="info">
                <h4>Product Details:</h4>
                <p><strong>Product:</strong> {result_data['product_title']}</p>
                <p><strong>Current Price:</strong> <span class="price">${result_data['price']:.2f}</span></p>
                <p><strong>Your Target:</strong> <span class="target">${result_data['target_price']:.2f}</span></p>
                <p><strong>Savings:</strong> <span class="price">${result_data['target_price'] - result_data['price']:.2f}</span></p>
                <p><strong>Availability:</strong> {result_data['availability']}</p>
                <p><strong>Check Time:</strong> {result_data['date']} at {result_data['time']}</p>
            </div>
            
            <div class="success">
                <a href="{result_data['url']}" class="button" target="_blank">🛒 Shop Now on Costco</a>
            </div>
            
            <div style="margin-top: 20px; font-size: 12px; color: #6c757d;">
                <p>This alert was generated by your automated price monitoring system running on GitHub Actions.</p>
                <p>Timestamp: {result_data['timestamp']}</p>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        text_content = f"""
🚨 COSTCO PRICE ALERT!

Price Drop Detected!
The price has dropped below your target threshold.

Product Details:
Product: {result_data['product_title']}
Current Price: ${result_data['price']:.2f}
Your Target: ${result_data['target_price']:.2f}
Savings: ${result_data['target_price'] - result_data['price']:.2f}
Availability: {result_data['availability']}
Check Time: {result_data['date']} at {result_data['time']}

Shop Now: {result_data['url']}

This alert was generated by your automated price monitoring system running on GitHub Actions.
Timestamp: {result_data['timestamp']}
        """
        
        # Attach both versions
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email
        logger.info("Sending price alert email...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            text = msg.as_string()
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, text)
        
        logger.info(f"✅ Price alert email sent successfully to {RECIPIENT_EMAIL}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return False

def send_daily_summary_email(result_data):
    """Send daily summary email (optional - for regular updates)"""
    logger = logging.getLogger(__name__)
    
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        
        if result_data['below_target']:
            msg['Subject'] = f"🚨 Daily Price Check: ALERT - ${result_data['price']:.2f}"
        else:
            msg['Subject'] = f"📊 Daily Price Check: ${result_data['price']:.2f} (No Alert)"
        
        # Create simple summary
        text_content = f"""
Daily Price Check Summary

Product: {result_data['product_title']}
Current Price: ${result_data['price']:.2f}
Target Price: ${result_data['target_price']:.2f}
Availability: {result_data['availability']}
Status: {'🚨 BELOW TARGET!' if result_data['below_target'] else '📈 Above Target'}
Check Time: {result_data['date']} at {result_data['time']}

{'⚡ ACTION REQUIRED: Price is below your target!' if result_data['below_target'] else 'No action needed - price is still above target.'}

Shop: {result_data['url']}

Automated check via GitHub Actions
        """
        
        msg.attach(MIMEText(text_content, 'plain'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        
        logger.info(f"Daily summary email sent to {RECIPIENT_EMAIL}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send daily summary email: {e}")
        return False

def save_price_data(data):
    """Save price data to JSON file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(DATA_DIR, f"price_data_{timestamp}.json")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logging.info(f"Price data saved to: {filename}")
    except Exception as e:
        logging.error(f"Failed to save price data: {e}")

def append_to_csv(data):
    """Append price data to CSV file for historical tracking"""
    csv_filename = os.path.join(DATA_DIR, "price_history.csv")
    
    # Check if file exists, if not create with headers
    file_exists = os.path.isfile(csv_filename)
    
    try:
        import csv
        with open(csv_filename, 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['timestamp', 'date', 'time', 'price', 'availability', 'below_target', 'product_title', 'email_sent']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(data)
        logging.info(f"Data appended to CSV: {csv_filename}")
    except Exception as e:
        logging.error(f"Failed to append to CSV: {e}")

def check_price_scheduled():
    """
    Modified price checking function with logging and data saving - GitHub Actions compatible
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Starting scheduled price check ===")
    
    # Set up Chrome options for GitHub Actions environment
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-images")
    options.add_argument("--disable-javascript")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--proxy-server='direct://'")
    options.add_argument("--proxy-bypass-list=*")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
            )

    result_data = {
        'timestamp': datetime.now().isoformat(),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'url': URL,
        'target_price': TARGET_PRICE,
        'zip_code': ZIP_CODE,
        'price': None,
        'availability': 'Unknown',
        'below_target': False,
        'product_title': 'Title not found',
        'success': False,
        'error_message': None,
        'email_sent': False
    }

    try:
        logger.info(f"Navigating to: {URL}")
        driver.get(URL)

        # Handle ZIP Code Entry
        logger.info("Handling ZIP code entry...")
        try:
            zip_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Enter ZIP code']"))
            )
            zip_input.click()
            zip_input.clear()
            zip_input.send_keys(ZIP_CODE)
            zip_input.send_keys(Keys.TAB)
            logger.info(f"Entered ZIP code: {ZIP_CODE}")
            time.sleep(1)

            # Find and click Start Shopping button
            button_found = False
            quick_selectors = [
                (By.XPATH, "//button[contains(text(), 'Start Shopping')]"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.XPATH, "//button[normalize-space()='Start Shopping']")
            ]

            for by_type, selector in quick_selectors:
                try:
                    start_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((by_type, selector))
                    )
                    start_button.click()
                    button_found = True
                    logger.info("Clicked 'Start Shopping' button")
                    break
                except TimeoutException:
                    continue

            if not button_found:
                raise TimeoutException("Could not find Start Shopping button")

            time.sleep(2)

        except TimeoutException as e:
            error_msg = "Failed to handle ZIP code entry"
            logger.error(error_msg)
            result_data['error_message'] = error_msg
            return result_data

        # Extract price information
        logger.info("Extracting price information...")
        
        try:
            WebDriverWait(driver, 8).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Get product title
        title_element = soup.find("h1")
        if title_element:
            result_data['product_title'] = title_element.get_text(strip=True)

        # Extract price
        current_price = None
        page_text = soup.get_text()
        price_pattern = r'\$(\d+\.?\d*)'
        price_matches = re.findall(price_pattern, page_text)
        
        # Look for reasonable prices (between $10-$50)
        for match in price_matches:
            price_val = float(match)
            if 10.0 <= price_val <= 50.0:
                current_price = price_val
                logger.info(f"Found price: ${current_price}")
                break
        
        # Try specific selectors if no price found
        if current_price is None:
            price_selectors = [
                "[data-testid='product-price']",
                "span[class*='price']",
                ".price"
            ]
            
            for selector in price_selectors:
                price_element = soup.select_one(selector)
                if price_element:
                    price_text = price_element.get_text(strip=True)
                    price_numbers = re.findall(r'\d+\.?\d*', price_text.replace("$", ""))
                    if price_numbers:
                        current_price = float(price_numbers[0])
                        break

        if current_price is None:
            logger.warning("Could not find price information")
            result_data['error_message'] = "Price not found"
            return result_data

        result_data['price'] = current_price

        # Check availability
        availability = "Unavailable"
        if "add to cart" in page_text.lower():
            availability = "Available"
        else:
            cart_button = soup.find("button", string=re.compile("add to cart", re.IGNORECASE))
            if cart_button:
                availability = "Available"

        result_data['availability'] = availability
        result_data['below_target'] = current_price < TARGET_PRICE
        result_data['success'] = True

        # Log results
        logger.info("=== Price Check Results ===")
        logger.info(f"Product: {result_data['product_title']}")
        logger.info(f"Current Price: ${current_price:.2f}")
        logger.info(f"Availability: {availability}")
        logger.info("=" * 30)

        # Price alert check and email sending
        if current_price < TARGET_PRICE:
            alert_msg = f"🚨 PRICE ALERT! Price ${current_price:.2f} is below target of ${TARGET_PRICE:.2f}"
            logger.warning(alert_msg)
            logger.info(f"Availability: {availability}")
            logger.info(f"URL: {URL}")
            
            # Send email alert
            email_sent = send_price_alert_email(result_data)
            result_data['email_sent'] = email_sent
            
        else:
            logger.info(f"Price ${current_price:.2f} is above target of ${TARGET_PRICE:.2f}")
            # Optionally send daily summary (uncomment if you want daily emails regardless)
            # send_daily_summary_email(result_data)

    except Exception as e:
        error_msg = f"An error occurred: {e}"
        logger.error(error_msg)
        result_data['error_message'] = error_msg
    finally:
        driver.quit()
        logger.info("Browser closed.")

    return result_data

def job():
    """Job function to be scheduled"""
    logger = logging.getLogger(__name__)
    logger.info("Starting price check job...")
    
    try:
        # Run price check
        result = check_price_scheduled()
        
        # Save data
        save_price_data(result)
        
        # Append to CSV for historical tracking
        csv_data = {
            'timestamp': result['timestamp'],
            'date': result['date'],
            'time': result['time'],
            'price': result['price'],
            'availability': result['availability'],
            'below_target': result['below_target'],
            'product_title': result['product_title'],
            'email_sent': result.get('email_sent', False)
        }
        append_to_csv(csv_data)
        
        logger.info("Price check job completed successfully")
        
        # Print summary for GitHub Actions logs
        if result['success']:
            logger.info(f"✅ SUCCESS: Found price ${result['price']:.2f} for {result['product_title']}")
            if result['below_target']:
                logger.info("🚨 ALERT: Price is below target!")
                if result.get('email_sent'):
                    logger.info("📧 Email alert sent successfully")
                else:
                    logger.warning("📧 Email alert failed to send")
            else:
                logger.info("📈 Price is above target threshold")
        else:
            logger.error(f"❌ FAILED: {result.get('error_message', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"Error in scheduled job: {e}")

def run_scheduler():
    """Run the scheduler (for local use)"""
    logger = setup_logging()
    logger.info("=== Price Checker Scheduler Started ===")
    logger.info("Scheduled to run daily at 9:00 AM")
    
    # Schedule the job for 9:00 AM daily
    schedule.every().day.at("09:00").do(job)
    
    logger.info("Scheduler is running... Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")

def run_once():
    """Run the price check once (for GitHub Actions)"""
    logger = setup_logging()
    logger.info("=== Running price check once (GitHub Actions mode) ===")
    job()

def test_email():
    """Test email functionality"""
    logger = setup_logging()
    logger.info("Testing email functionality...")
    
    # Create test data
    test_data = {
        'timestamp': datetime.now().isoformat(),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'url': URL,
        'target_price': TARGET_PRICE,
        'price': 19.99,  # Below target for testing
        'availability': 'Available',
        'below_target': True,
        'product_title': 'Test - Kirkland Signature Wild Alaskan Cod',
        'success': True
    }
    
    success = send_price_alert_email(test_data)
    if success:
        logger.info("✅ Test email sent successfully!")
    else:
        logger.error("❌ Test email failed!")

if __name__ == "__main__":
    # Load configuration from environment variables
    load_config_from_env()
    
    import sys
    
    # Check if we have email credentials
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("⚠️  EMAIL SETUP REQUIRED!")
        print("Please configure SENDER_EMAIL and SENDER_PASSWORD environment variables.")
        print("\nFor GitHub Actions:")
        print("1. Go to your repository Settings → Secrets and variables → Actions")
        print("2. Add these secrets:")
        print("   - SENDER_EMAIL: Your Gmail address")
        print("   - SENDER_PASSWORD: Your Gmail app password")
        print("   - RECIPIENT_EMAIL: Email to receive alerts")
        print("   - TARGET_PRICE: Your target price (e.g., '21.00')")
        print("   - ZIP_CODE: Your ZIP code (e.g., '78726')")
        
        # Don't exit completely in GitHub Actions - still try to run without email
        if os.getenv('GITHUB_ACTIONS'):
            print("Running in GitHub Actions - will continue without email notifications")
        else:
            exit()
    
    # Command line arguments for different modes
    if len(sys.argv) > 1:
        if sys.argv[1] == "test-email":
            test_email()
        elif sys.argv[1] == "scheduler":
            run_scheduler()
        else:
            run_once()
    else:
        # Default behavior for GitHub Actions: run once
        run_once()
