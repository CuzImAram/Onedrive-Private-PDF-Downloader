"""
Core functionality for exporting PDFs from web browser.
"""

import logging
import os
import shutil
import tempfile
from time import sleep

import img2pdf
from selenium.common.exceptions import (  # noqa: E501 pylint: disable=line-too-long
    JavascriptException,
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

from onedrive_pdf_downloader.browser.constants import (
    ARIA_LABELS_NEXT_PAGE,
    CLASS_NAMES_BANNER,
    CLASS_NAMES_SIDE_PANEL,
    CSS_PAGE,
)
from onedrive_pdf_downloader.browser.factory import set_viewport
from onedrive_pdf_downloader.browser.utils import (
    find_element,
    find_page,
    go_to_first_page,
    hide_class_names,
    hide_toolbar,
)


def prepare_viewer(args, browser) -> None:
    """
    Match the viewport to the page orientation and go to the first page.

    The viewer remembers the last viewed position, so the document may not
    open on the first page.

    Args:
        args (argparse.Namespace): Command line arguments
        browser (webdriver): Browser instance
    """
    pages = browser.find_elements(By.CSS_SELECTOR, CSS_PAGE)
    if pages:
        size = pages[0].size
        landscape = size["width"] > size["height"]
        if set_viewport(browser, args, landscape=landscape):
            logging.debug("Viewport set for %s pages.",
                          "landscape" if landscape else "portrait")
            sleep(3)  # Wait for the viewer to re-render

    try:
        go_to_first_page(browser)
        sleep(3)
    except (NoSuchElementException, WebDriverException):
        logging.warning(
            "Cannot jump to the first page, the export starts at the "
            "currently visible page."
        )


def export_pdf(args, browser, total_of_pages, filename):
    """
    Export the PDF by taking screenshots of each page.

    Args:
        args (argparse.Namespace): Command line arguments
        browser (webdriver): Browser instance
        total_of_pages (int): Total number of pages
        filename (str): Output filename

    Returns:
        bool: True if successful, False otherwise
    """
    files_list = []

    with tempfile.TemporaryDirectory() as temp_dir:
        prepare_viewer(args, browser)

        # Hide the toolbar for screenshots
        try:
            hide_toolbar(browser)
            logging.info("Toolbar hidden for clean screenshots.")
        except NoSuchElementException:
            logging.warning(
                "The toolbar is not visible or class names are not up-to-date. "  # noqa: E501 pylint: disable=line-too-long
                "Screenshots might contain the toolbar."
            )

        # Hide the banner if present (not every file shows one)
        try:
            hide_toolbar(browser, CLASS_NAMES_BANNER)
            logging.info("Banner hidden for clean screenshots.")
        except NoSuchElementException:
            logging.debug("No banner found to hide.")

        # The table of contents panel can open at any time, hide it for good
        hide_class_names(browser, CLASS_NAMES_SIDE_PANEL)

        # Process each page
        page_number = 1
        while page_number <= total_of_pages:
            sleep(5)  # Wait for page to load properly
            image_path = f"{temp_dir}/{str(page_number)}.png"

            try:
                # Capture only the current page; the canvas can also show
                # parts of the pages before and after it
                page = find_page(browser, page_number)
                if page is None:
                    logging.debug("Page element %d not found, capturing "
                                  "the whole canvas.", page_number)
                    page = browser.find_element(By.CSS_SELECTOR, "canvas")
                page.screenshot(image_path)
            except NoSuchElementException:
                logging.error(
                    "Cannot find the PDF canvas within the page. "
                    "This may be due to internal changes in OneDrive."
                )
                return False

            files_list.append(image_path)

            logging.info(
                "Page %s of %s exported.",
                str(page_number),
                str(total_of_pages)
            )

            page_number += 1

            # Go to the next page if not on the last page
            if page_number <= total_of_pages:
                try:
                    next_page_button = find_element(
                        browser, ARIA_LABELS_NEXT_PAGE, By.XPATH
                    )
                    browser.execute_script(
                        "arguments[0].click();", next_page_button)
                except (NoSuchElementException, JavascriptException):
                    logging.error(
                        "Cannot find the next page button. Navigation aria labels may be outdated. "  # noqa: E501 pylint: disable=line-too-long
                        "Saving the pages obtained so far."
                    )
                    break

        # Save the PDF
        try:
            logging.info("Saving the file as '%s'.", filename)
            with open(filename, "wb") as out_file:
                out_file.write(img2pdf.convert(files_list))

            # Save images if requested
            if args.keep_imgs:
                keep_dir = f"{filename}_images"
                os.makedirs(keep_dir, exist_ok=True)
                for file_path in files_list:
                    shutil.copy(file_path, keep_dir)
                logging.info("Images kept in directory '%s'.", keep_dir)

            logging.info("PDF export completed successfully.")
            return True

        except IOError as e:
            logging.error("Error saving PDF: %s", str(e))
            return False
