"""
Constants related to browser element selectors and identifiers.
"""

# Class names used to identify elements - these can change if the UI is updated
CLASS_NAMES_TOTAL_PAGES = ["status_4196ef6e", "status_5a88b9b2"]
CLASS_NAMES_FILE_NAME = [
    "OneUpNonInteractiveCommandNewDesign_5d658c6e",
    "OneUpNonInteractiveCommandNewDesign_156f96ef",
]
CLASS_NAMES_TOOLBAR = ["root_4196ef6e", "root_5a88b9b2"]
# Banners over the page, e.g. "This file is protected" for PDFs with an owner password
CLASS_NAMES_BANNER = ["topArea_7516adf3"]

# Selectors for the folder list view (data-automationid values are stable)
CSS_FOLDER_ROW = (
    "[role=row][data-automationid^='row-']"
    ":not([data-automationid='row-header'])"
)
CSS_FOLDER_ITEM_NAME = "[data-id=heroField]"
CSS_FOLDER_ITEM_ICON = "[data-automationid=field-DocIcon]"
# Words in the icon's src/alt/aria-label that mark a row as a folder
FOLDER_ICON_KEYWORDS = ["folder", "ordner", "cartella"]

# CSS viewport used for rendering; the screenshot resolution is this times
# the --scale factor (OneDrive fits the page into the viewport)
VIEWPORT_SIZE = (1400, 1980)

# Aria labels for navigation elements
ARIA_LABELS_NEXT_PAGE = [
    "Vai alla pagina successiva.",
    "Go to the next page.",
    "Zur nächsten Seite wechseln.",
]
