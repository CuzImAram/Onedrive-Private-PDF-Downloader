"""
Utility functions for browser interaction.
"""

import logging

from selenium import webdriver
from selenium.common.exceptions import (  # noqa: E501 pylint: disable=line-too-long
    JavascriptException,
    NoSuchElementException,
)
from selenium.webdriver.common.by import By

from onedrive_pdf_downloader.browser.constants import (
    CLASS_NAMES_TOOLBAR,
    CSS_PAGE,
)


def find_element(browser: webdriver, identifiers: list[str], by: By):
    """
    Find an element using multiple possible identifiers.

    Args:
        browser (webdriver): Browser instance
        identifiers (list[str]): List of identifiers to try
        by (By): The method to use for finding the element

    Returns:
        WebElement: The found element

    Raises:
        NoSuchElementException: If no element is found with any identifier
    """
    for identifier in identifiers:
        try:
            match by:
                case By.CLASS_NAME:
                    element = browser.find_element(by, identifier)
                case By.XPATH:
                    element = browser.find_elements(
                        by, f"//button[@aria-label='{identifier}']"
                    )[-1]
                case _:
                    raise ValueError(f"Unsupported method: {by}")
            logging.debug("Element found using %s: '%s'", by, identifier)
            return element
        except (NoSuchElementException, IndexError):
            logging.debug("Element not found using %s: '%s'", by, identifier)
            continue

    raise NoSuchElementException(
        f"No element found with any of the identifiers: {identifiers}"
    )


def find_page(browser: webdriver, page_number: int):
    """
    Find the element of a page in the PDF viewer.

    Args:
        browser (webdriver): Browser instance
        page_number (int): Number of the page, starting at 1

    Returns:
        WebElement | None: The page element, if it is rendered
    """
    return browser.execute_script(
        "return [...document.querySelectorAll(arguments[0])].find("
        "e => e.getAttribute('aria-label').endsWith(' ' + arguments[1] + '.'))"
        " || null;",
        CSS_PAGE, page_number,
    )


def go_to_first_page(browser: webdriver) -> None:
    """
    Scroll the PDF viewer back to the first page.

    Args:
        browser (webdriver): Browser instance

    Raises:
        NoSuchElementException: If the scrollable viewer is not found
    """
    scrolled = browser.execute_script(
        "let e = document.querySelector(arguments[0]);"
        "while (e && !(e.scrollHeight > e.clientHeight"
        " && /(auto|scroll)/.test(getComputedStyle(e).overflowY)))"
        " e = e.parentElement;"
        "if (!e) return false;"
        "e.scrollTop = 0;"
        "return true;",
        CSS_PAGE,
    )
    if not scrolled:
        raise NoSuchElementException("No scrollable PDF viewer found")


def hide_class_names(browser: webdriver, class_names: list[str]) -> None:
    """
    Hide all elements with the given class names, including elements that
    are only added to the page later.

    Args:
        browser (webdriver): Browser instance
        class_names (list[str]): List of class names to hide
    """
    browser.execute_script(
        "const style = document.createElement('style');"
        "style.textContent = arguments[0].map(c => '.' + c).join(',')"
        " + '{visibility: hidden !important}';"
        "document.head.appendChild(style);",
        class_names,
    )
    logging.debug("Elements hidden using class names: %s", class_names)


def hide_toolbar(browser: webdriver, class_names: list[str] = None) -> None:
    """
    Hide the toolbar to get clean screenshots.

    Args:
        browser (webdriver): Browser instance
        class_names (list[str]): List of possible class names for the toolbar

    Raises:
        NoSuchElementException: If no toolbar is found
    """

    if class_names is None:
        class_names = CLASS_NAMES_TOOLBAR
    for class_name in class_names:
        try:
            browser.execute_script(
                f"document.getElementsByClassName('{class_name}')[0].style.visibility = 'hidden'"  # noqa: E501 pylint: disable=line-too-long
            )
            logging.debug("Toolbar hidden using class name: '%s'", class_name)
            return
        except (IndexError, NoSuchElementException, JavascriptException):
            logging.debug(
                "Toolbar not found using class name: '%s'", class_name
            )
            continue

    raise NoSuchElementException(
        f"No toolbar found with any of the class names: {class_names}"
    )
