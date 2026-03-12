"""PDF Compilation Cache — content-hash LRU caching for compiled PDFs.

Implements: TASK-030 M8 — Avoids recompiling identical LaTeX content.
Same entry IDs + template + config = same tex content = cache hit.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum cached PDFs before LRU eviction
MAX_CACHE_SIZE = 200


def _get_cache_dir() -> Path:
    """Return the PDF cache directory, creating it if needed."""
    cache_dir = Path.home() / ".autoapply" / "cache" / "pdf"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def content_hash(tex_content: str) -> str:
    """Compute a short SHA256 hash of LaTeX content for cache key."""
    return hashlib.sha256(tex_content.encode("utf-8")).hexdigest()[:16]


def get_cached(tex_content: str) -> bytes | None:
    """Return cached PDF bytes if a cache hit exists, else None."""
    key = content_hash(tex_content)
    cached_path = _get_cache_dir() / f"{key}.pdf"

    if cached_path.exists():
        logger.debug("PDF cache hit: %s", key)
        # Touch file to update access time for LRU
        cached_path.touch()
        return cached_path.read_bytes()

    logger.debug("PDF cache miss: %s", key)
    return None


def store(tex_content: str, pdf_bytes: bytes) -> None:
    """Store compiled PDF in cache."""
    key = content_hash(tex_content)
    cached_path = _get_cache_dir() / f"{key}.pdf"
    cached_path.write_bytes(pdf_bytes)
    logger.debug("PDF cached: %s (%d bytes)", key, len(pdf_bytes))


def evict_lru() -> int:
    """Evict oldest cached PDFs when cache exceeds MAX_CACHE_SIZE.

    Returns:
        Number of files evicted.
    """
    cache_dir = _get_cache_dir()
    pdf_files = sorted(cache_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime)

    if len(pdf_files) <= MAX_CACHE_SIZE:
        return 0

    to_evict = len(pdf_files) - MAX_CACHE_SIZE
    evicted = 0

    for pdf_file in pdf_files[:to_evict]:
        try:
            pdf_file.unlink()
            evicted += 1
        except OSError:
            logger.debug("Could not evict cached PDF: %s", pdf_file.name)

    if evicted:
        logger.info("PDF cache eviction: removed %d files (max %d)", evicted, MAX_CACHE_SIZE)

    return evicted


def clear_cache() -> int:
    """Clear all cached PDFs. Returns count of files removed."""
    cache_dir = _get_cache_dir()
    count = 0
    for pdf_file in cache_dir.glob("*.pdf"):
        try:
            pdf_file.unlink()
            count += 1
        except OSError:
            pass
    logger.info("PDF cache cleared: %d files removed", count)
    return count


def cache_stats() -> dict:
    """Return cache statistics."""
    cache_dir = _get_cache_dir()
    pdf_files = list(cache_dir.glob("*.pdf"))
    total_size = sum(f.stat().st_size for f in pdf_files)
    return {
        "count": len(pdf_files),
        "size_bytes": total_size,
        "size_mb": round(total_size / (1024 * 1024), 2),
        "max_size": MAX_CACHE_SIZE,
        "cache_dir": str(cache_dir),
    }
