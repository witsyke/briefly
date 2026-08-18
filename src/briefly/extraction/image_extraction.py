import asyncio
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader

from briefly.extraction.extraction import ImageReference

DEFAULT_MIN_DIMENSION = 250
FALLBACK_RENDER_SCALE = 2

MARGIN_BAND_FRACTION = 0.08
REGION_PADDING = 8.0

BBox = tuple[float, float, float, float]


class VisualType(IntEnum):
    PATH = 2
    IMAGE = 3
    SHADING = 4
    FORM = 5


def _in_margin_band(bounds: BBox, page_height: float) -> bool:
    _, bottom, _, top = bounds
    band = page_height * MARGIN_BAND_FRACTION
    return top <= band or bottom >= page_height - band


def _visual_objects(page: pdfium.PdfPage) -> list:
    height = page.get_height()
    return [
        object
        for object in page.get_objects(max_depth=0)
        if object.type in VisualType
        and not _in_margin_band(object.get_bounds(), height)
    ]


def _region_bbox(objects: list, page_size: tuple[float, float]) -> BBox | None:
    if not objects:
        return None
    width, height = page_size
    bounds = [object.get_bounds() for object in objects]
    left = max(0.0, min(bound[0] for bound in bounds) - REGION_PADDING)
    bottom = max(0.0, min(bound[1] for bound in bounds) - REGION_PADDING)
    right = min(width, max(bound[2] for bound in bounds) + REGION_PADDING)
    top = min(height, max(bound[3] for bound in bounds) + REGION_PADDING)
    return (left, bottom, right, top)


def _render_region(page: pdfium.PdfPage, region: BBox, page_size: tuple[float, float]):
    width, height = page_size
    left, bottom, right, top = region
    crop = (left, bottom, width - right, height - top)
    return page.render(scale=FALLBACK_RENDER_SCALE, crop=crop).to_pil().convert("RGB")


def _center_inside(region: BBox, bounds: BBox) -> bool:
    left, bottom, right, top = region
    cx, cy = (
        (bounds[0] + bounds[2]) / 2,
        (bounds[1] + bounds[3]) / 2,
    )
    return left <= cx <= right and bottom <= cy <= top


def _contained_images(
    page_number,
    region: BBox,
    page: pdfium.PdfPage,
    reader: PdfReader,
    min_dimension,
):
    pdfium_images = [
        object
        for object in page.get_objects(max_depth=0)
        if object.type == VisualType.IMAGE
    ]
    pypdf_images = list(reader.pages[page_number - 1].images)

    return [
        pil_image
        for object, pil_image in zip(pdfium_images, pypdf_images, strict=False)
        if pil_image.image.width >= min_dimension
        and pil_image.image.height >= min_dimension
        and _center_inside(region, object.get_bounds())
    ]


@dataclass(frozen=True)
class SavedImage:
    order: int
    page: int
    file_path: Path


@dataclass(frozen=True)
class ImageExtractionOutcome:
    path: Path
    files: list[SavedImage] | None
    error: str | None = None
    retryable: bool = False

    @property
    def succeeded(self) -> bool:
        return self.files is not None

    @classmethod
    def ok(cls, path: Path, files: list[SavedImage]) -> "ImageExtractionOutcome":
        return cls(path=path, files=files)

    @classmethod
    def failure(
        cls, path: Path, error: BaseException, *, retryable: bool
    ) -> "ImageExtractionOutcome":
        return cls(path=path, files=None, error=str(error), retryable=retryable)


def _qualifying_raster_images(reader: PdfReader, min_dimension: int) -> dict[int, list]:
    by_page: dict[int, list] = {}
    for page_number, page in enumerate(reader.pages, start=1):
        qualifying = [
            image
            for image in page.images
            if (
                image.image.width >= min_dimension
                and image.image.height >= min_dimension
            )
        ]
        if qualifying:
            by_page[page_number] = qualifying
    return by_page


def _extract_images_sync(
    pdf_path: Path,
    output_dir: Path,
    expected: list[ImageReference],
    min_dimension: int = DEFAULT_MIN_DIMENSION,
) -> ImageExtractionOutcome:
    try:
        reader = PdfReader(pdf_path)
        raster_by_page = _qualifying_raster_images(reader, min_dimension)

        expected_by_page: dict[int, list[ImageReference]] = {}
        for ref in expected:
            expected_by_page.setdefault(ref.page, []).append(ref)

        pdf_output_dir = output_dir / pdf_path.stem
        pdf_output_dir.mkdir(parents=True, exist_ok=True)

        saved: list[SavedImage] = []
        pdfium_doc = None

        for page_number, refs in expected_by_page.items():
            refs = sorted(refs, key=lambda r: r.order)
            raster_images = raster_by_page.get(page_number, [])

            if len(raster_images) == len(refs):
                for ref, image in zip(refs, raster_images, strict=False):
                    out_path = pdf_output_dir / f"img_{ref.order:03d}.png"
                    image.image.convert("RGB").save(out_path)
                    saved.append(SavedImage(ref.order, page_number, out_path))
                continue

            if pdfium_doc is None:
                pdfium_doc = pdfium.PdfDocument(pdf_path)
            pdfium_page = pdfium_doc[page_number - 1]
            page_size = pdfium_page.get_size()
            region = _region_bbox(_visual_objects(pdfium_page), page_size)

            if region is None or len(refs) > 1:
                rendered = pdfium_page.render(scale=FALLBACK_RENDER_SCALE).to_pil()
                for ref in refs:
                    out_path = pdf_output_dir / f"img_{ref.order:03d}.png"
                    rendered.convert("RGB").save(out_path)
                    saved.append(SavedImage(ref.order, page_number, out_path))
                continue

            contained = _contained_images(
                page_number, region, pdfium_page, reader, min_dimension
            )
            ref = refs[0]
            out_path = pdf_output_dir / f"img_{ref.order:03d}.png"
            if len(contained) == 1:
                contained[0].image.convert("RGB").save(out_path)
            else:
                _render_region(pdfium_page, region, page_size).save(out_path)
            saved.append(SavedImage(ref.order, page_number, out_path))

    except Exception as exc:
        return ImageExtractionOutcome.failure(pdf_path, exc, retryable=False)
    print("--------")
    return ImageExtractionOutcome.ok(pdf_path, saved)


async def extract_images(
    pdf_path: Path,
    output_dir: Path,
    expected: list[ImageReference],
    min_dimension: int = DEFAULT_MIN_DIMENSION,
) -> ImageExtractionOutcome:
    return await asyncio.to_thread(
        _extract_images_sync, pdf_path, output_dir, expected, min_dimension
    )
