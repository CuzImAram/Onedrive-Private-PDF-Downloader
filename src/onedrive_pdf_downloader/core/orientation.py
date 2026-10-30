"""
Detect and fix the orientation of scanned pages (sideways or upside down).

Uses the optional rapidocr package (`pip install .[rotate]`). The rotation
is stored in the PDF page, so the images are not re-encoded.
"""

import logging
import os

import pikepdf
from pikepdf import PdfImage

MAX_SIDE = 1200  # px, longest side of the image used for detection
MAX_LINES = 20  # number of text lines used to decide between 0 and 180
MIN_TEXT_SCORE = 0.8  # recognition confidence for a text line to count

_ocr = None  # pylint: disable=invalid-name


def _load_ocr():
    """
    Load the OCR engine once.

    Returns:
        RapidOCR | None: The OCR engine, or None if rapidocr is not installed
    """
    global _ocr  # pylint: disable=global-statement
    if _ocr is None:
        try:
            from rapidocr import RapidOCR  # pylint: disable=import-outside-toplevel
        except ImportError:
            logging.warning(
                "Cannot check the page orientation, rapidocr is not "
                "installed. Install it with: pip install rapidocr onnxruntime"
            )
            _ocr = False
            return None
        _ocr = RapidOCR(params={"Global.log_level": "critical"})
    return _ocr or None


def _text_lines(ocr, image):
    """
    Detect the text lines of an image.

    Args:
        ocr (RapidOCR): OCR engine
        image (PIL.Image.Image): Image to search

    Returns:
        tuple[int, list]: Number of horizontal lines and the crops of the
        longest lines
    """
    import numpy as np  # pylint: disable=import-outside-toplevel

    array = np.array(image)
    result = ocr._load_det_model()(array)  # pylint: disable=protected-access
    if result.boxes is None:
        return 0, []
    horizontal = sum(
        1 for box in result.boxes
        if np.linalg.norm(box[1] - box[0]) > np.linalg.norm(box[3] - box[0])
    )
    crops = ocr.crop_text_regions(array, result.boxes)
    crops.sort(key=lambda crop: -crop.shape[1])
    return horizontal, crops[:MAX_LINES]


def _text_score(ocr, crops) -> float:
    """
    Score how readable some text lines are.

    Args:
        ocr (RapidOCR): OCR engine
        crops (list): Images of text lines

    Returns:
        float: Number of confidently recognized characters
    """
    from rapidocr.ch_ppocr_rec import TextRecInput  # noqa: E501 pylint: disable=import-outside-toplevel

    result = ocr._load_rec_model()(  # pylint: disable=protected-access
        TextRecInput(img=crops))
    return sum(
        score * len(text)
        for text, score in zip(result.txts or [], result.scores or [])
        if score > MIN_TEXT_SCORE
    )


def detect_rotation(image) -> int:
    """
    Detect how much a page has to be turned to be upright.

    Args:
        image (PIL.Image.Image): Image of the page

    Returns:
        int: Clockwise rotation in degrees (0, 90, 180 or 270)
    """
    import numpy as np  # pylint: disable=import-outside-toplevel

    ocr = _load_ocr()
    if ocr is None:
        return 0

    image = image.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))

    # Text lines are wider than tall, unless the page is sideways
    rotation = 0
    horizontal, crops = _text_lines(ocr, image)
    if crops and horizontal < len(crops) / 2:
        rotation = 90
        _, crops = _text_lines(ocr, image.rotate(-90, expand=True))
    if not crops:
        return 0  # No text, e.g. an empty page

    # Upside down text is not readable, compare both directions
    upright = _text_score(ocr, crops)
    flipped = _text_score(ocr, [np.rot90(crop, 2).copy() for crop in crops])
    if flipped > upright:
        rotation += 180
    return rotation % 360


def fix_pdf_rotation(filename: str) -> int:
    """
    Turn every page of a PDF made of page images upright.

    Args:
        filename (str): Path of the PDF, changed in place

    Returns:
        int: Number of pages turned
    """
    if _load_ocr() is None:
        return 0

    turned = 0
    with pikepdf.open(filename, allow_overwriting_input=True) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            images = list(page.images.values())
            if len(images) != 1:
                continue  # Not a scanned page
            current = int(page.obj.get("/Rotate", 0)) % 360
            image = PdfImage(images[0]).as_pil_image()
            rotation = detect_rotation(image.rotate(-current, expand=True))
            if rotation:
                page.rotate(rotation, relative=True)
                turned += 1
                logging.info("Page %d turned by %d degrees.", number, rotation)
        if turned:
            pdf.save(filename)
    return turned


def fix_rotation(path: str) -> None:
    """
    Turn the pages of a PDF, or of all PDFs in a folder, upright.

    Args:
        path (str): PDF file or folder (searched recursively)
    """
    if os.path.isdir(path):
        files = sorted(
            os.path.join(root, name)
            for root, _, names in os.walk(path)
            for name in names if name.lower().endswith(".pdf")
        )
    else:
        files = [path]

    for filename in files:
        logging.info("Checking the orientation of '%s'.", filename)
        turned = fix_pdf_rotation(filename)
        if turned:
            logging.info("'%s': %d pages turned.", filename, turned)
