"""
Factory module for creating browser instances.
"""

import argparse
import logging
import os
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

from onedrive_pdf_downloader.browser.constants import (
    VIEWPORT_SIZE,
    VIEWPORT_SIZE_LANDSCAPE,
)


def set_viewport(browser: webdriver, args: argparse.Namespace,
                 landscape: bool = False) -> bool:
    """
    Use a larger viewport with a higher pixel ratio, which makes OneDrive
    render the PDF canvas at a higher resolution. Chrome only.

    Args:
        browser (webdriver): Browser instance
        args (argparse.Namespace): Command line arguments
        landscape (bool): Use a landscape viewport, for landscape pages

    Returns:
        bool: True if the viewport was changed
    """
    if args.browser != "chrome" or not args.scale or args.scale == 1:
        return False
    width, height = VIEWPORT_SIZE_LANDSCAPE if landscape else VIEWPORT_SIZE
    browser.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": height,
         "deviceScaleFactor": args.scale, "mobile": False},
    )
    return True


def create_browser(args: argparse.Namespace) -> webdriver:
    """
    Create a browser instance based on the provided arguments.

    Args:
        args (argparse.Namespace): Command line arguments

    Returns:
        webdriver: The configured browser instance

    Raises:
        ValueError: If an unsupported browser is specified
    """
    options = None
    service = None

    logging.info("Initializing browser: '%s'", args.browser)

    match args.browser:
        case "firefox":
            options = webdriver.FirefoxOptions()
            service = FirefoxService(log_path=os.devnull)
            if args.profile_dir:
                options.profile = webdriver.FirefoxProfile(args.profile_dir)
            return webdriver.Firefox(service=service, options=options)

        case "chrome":
            options = webdriver.ChromeOptions()
            service = ChromeService(log_path=os.devnull)
            if args.profile_dir and args.profile_name:
                options.add_argument(f"user-data-dir={args.profile_dir}")
                options.add_argument(
                    f"--profile-directory={args.profile_name}")
            browser = webdriver.Chrome(service=service, options=options)
            if set_viewport(browser, args):
                logging.info("Rendering at scale %s.", args.scale)
            return browser

        case _:
            raise ValueError(f"Unsupported browser: {args.browser}")


@contextmanager
def browser_context(args: argparse.Namespace):
    """
    Context manager to handle the browser session.

    Args:
        args (argparse.Namespace): Command line arguments

    Yields:
        webdriver: The browser instance
    """
    browser = create_browser(args)
    try:
        yield browser
    finally:
        browser.quit()
        print()  # Add a new line after the browser is closed
        logging.info("Browser session ended.")
