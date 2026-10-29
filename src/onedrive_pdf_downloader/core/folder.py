"""
Recursive export of all PDFs inside a OneDrive/SharePoint folder.
"""

import logging
import os
from time import sleep
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

from selenium.common.exceptions import (  # noqa: E501 pylint: disable=line-too-long
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from onedrive_pdf_downloader.browser import find_element
from onedrive_pdf_downloader.browser.constants import (
    CLASS_NAMES_TOTAL_PAGES,
    CSS_FOLDER_ITEM_ICON,
    CSS_FOLDER_ITEM_NAME,
    CSS_FOLDER_ROW,
    FOLDER_ICON_KEYWORDS,
)
from onedrive_pdf_downloader.core.export import export_pdf

LOAD_TIMEOUT = 60  # seconds to wait for a folder or a PDF preview to load


def get_item_path(url: str) -> str | None:
    """
    Get the server relative path of the item a OneDrive URL points to.

    Args:
        url (str): OneDrive/SharePoint URL

    Returns:
        str | None: The value of the `id` query parameter, if any
    """
    values = parse_qs(urlsplit(url).query).get("id")
    return values[0] if values else None


def build_item_url(url: str, item_path: str, parent: str = None) -> str:
    """
    Build a URL that opens another item, keeping the other query parameters.

    Args:
        url (str): URL to take the base and query parameters from
        item_path (str): Server relative path of the item to open
        parent (str): Parent folder path, needed to open a file preview

    Returns:
        str: The new URL
    """
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    query["id"] = [item_path]
    query.pop("parent", None)
    if parent:
        query["parent"] = [parent]
    return urlunsplit(parts._replace(
        query=urlencode(query, doseq=True, quote_via=quote)))


def is_folder_row(row) -> bool:
    """
    Check if a row of the folder list is a folder, based on its icon.

    Args:
        row (WebElement): Row of the folder list

    Returns:
        bool: True if the row is a folder
    """
    icon = row.find_element(By.CSS_SELECTOR, CSS_FOLDER_ITEM_ICON)
    labels = " ".join(
        (element.get_attribute(attr) or "")
        for element in icon.find_elements(By.CSS_SELECTOR, "*")
        for attr in ("src", "alt", "aria-label", "data-icon-name")
    ).lower()
    return any(keyword in labels for keyword in FOLDER_ICON_KEYWORDS)


def list_folder(browser, url: str, folder_path: str) -> tuple[list, list]:
    """
    Open a folder and list the PDFs and subfolders it contains.

    Args:
        browser (webdriver): Browser instance
        url (str): URL to take the base and query parameters from
        folder_path (str): Server relative path of the folder

    Returns:
        tuple[list, list]: Names of the PDF files and of the subfolders
    """
    browser.get(build_item_url(url, folder_path))
    folder_name = folder_path.rstrip("/").rsplit("/", 1)[-1]
    WebDriverWait(browser, LOAD_TIMEOUT).until(
        lambda b: b.title.startswith(folder_name) and b.find_elements(
            By.CSS_SELECTOR, "[data-automationid='row-header']")
    )
    sleep(2)  # Give the rows a moment to render after the header

    files, folders = {}, {}
    # The list is virtualized, scroll until no new rows show up
    while True:
        rows = browser.find_elements(By.CSS_SELECTOR, CSS_FOLDER_ROW)
        found_new = False
        for row in rows:
            try:
                name = row.find_element(
                    By.CSS_SELECTOR, CSS_FOLDER_ITEM_NAME
                ).get_attribute("title")
                if not name or name in files or name in folders:
                    continue
                found_new = True
                if is_folder_row(row):
                    folders[name] = True
                elif name.lower().endswith(".pdf"):
                    files[name] = True
                else:
                    files.setdefault(name, False)  # Not a PDF, skipped
            except (NoSuchElementException, StaleElementReferenceException):
                continue
        if not found_new or not rows:
            break
        browser.execute_script("arguments[0].scrollIntoView();", rows[-1])
        sleep(1.5)  # Wait for the next rows to load

    pdfs = [name for name, is_pdf in files.items() if is_pdf]
    logging.debug("Folder '%s': %d PDFs, %d subfolders, %d other files.",
                  folder_path, len(pdfs), len(folders),
                  len(files) - len(pdfs))
    return pdfs, list(folders)


def wait_for_pdf_preview(browser) -> int:
    """
    Wait until the PDF preview is loaded and return its number of pages.

    Args:
        browser (webdriver): Browser instance

    Returns:
        int: Total number of pages
    """
    def page_count(b):
        try:
            text = find_element(
                b, CLASS_NAMES_TOTAL_PAGES, By.CLASS_NAME
            ).get_attribute("textContent")
            return int(text.replace("/", "").strip())
        except (NoSuchElementException, ValueError):
            return False

    return WebDriverWait(browser, LOAD_TIMEOUT).until(
        lambda b: b.title.lower().endswith(".pdf") and page_count(b)
    )


def export_folder_pdf(args, browser, file_url: str, filename: str) -> str:
    """
    Export a single PDF of a folder, unless it already exists locally.

    Args:
        args (argparse.Namespace): Command line arguments
        browser (webdriver): Browser instance
        file_url (str): URL of the PDF preview
        filename (str): Local path to save the PDF to

    Returns:
        str: "exported", "skipped" or "failed"
    """
    if os.path.exists(filename):
        logging.info("Skipping '%s', it already exists.", filename)
        return "skipped"

    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    browser.get(file_url)
    try:
        total_of_pages = wait_for_pdf_preview(browser)
    except TimeoutException:
        logging.error("The preview of '%s' did not load.", filename)
        return "failed"

    logging.info('Exporting "%s" (%d pages).', filename, total_of_pages)
    if export_pdf(args, browser, total_of_pages, filename):
        return "exported"
    return "failed"


def export_folder(args, browser, url: str, folder_path: str) -> bool:
    """
    Export all PDFs of a folder and its subfolders, mirroring the structure.

    PDFs that already exist locally are skipped, so an interrupted run can
    be resumed by starting it again.

    Args:
        args (argparse.Namespace): Command line arguments
        browser (webdriver): Browser instance
        url (str): URL of the folder
        folder_path (str): Server relative path of the folder

    Returns:
        bool: True if every PDF was exported
    """
    root_dir = args.output_file or folder_path.rstrip("/").rsplit("/", 1)[-1]
    results = {"exported": [], "skipped": [], "failed": []}
    pending = [(folder_path, root_dir)]

    while pending:
        current_path, local_dir = pending.pop(0)
        try:
            pdfs, subfolders = list_folder(browser, url, current_path)
        except (TimeoutException, WebDriverException) as e:
            logging.error("Cannot list folder '%s': %s", current_path, e.msg)
            results["failed"].append(current_path)
            continue

        logging.info("Folder '%s': %d PDFs, %d subfolders.",
                     local_dir, len(pdfs), len(subfolders))
        pending.extend(
            (f"{current_path}/{name}", os.path.join(local_dir, name))
            for name in subfolders
        )

        for name in pdfs:
            filename = os.path.join(local_dir, name)
            results[export_folder_pdf(
                args, browser, build_item_url(
                    url, f"{current_path}/{name}", parent=current_path),
                filename)].append(filename)

    logging.info("Folder export done: %d exported, %d skipped, %d failed.",
                 *(len(results[key])
                   for key in ("exported", "skipped", "failed")))
    for item in results["failed"]:
        logging.warning("Failed: %s", item)
    return not results["failed"]
