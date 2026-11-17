from __future__ import annotations

import re

from openani_dl.models import Fansub


def extract_cdn_link(html: str) -> str | None:
    """Return the CDN base URL used for the direct MP4 files."""
    match = re.search(r'CDN_LINK\s*:\s*"([^"]+)"', html)
    if match:
        return match.group(1)

    match = re.search(r'random_cdn_host\s*:\s*"([^"]+)"', html)
    if match:
        return match.group(1).rstrip("/") + "/animes/"
    return None


def extract_fansubs(html: str) -> list[Fansub]:
    """Extract the fansub list embedded in the episode page."""
    block = re.search(
        r"\bfansubs\s*:\s*\[(.*?)\]\s*,\s*seasons\s*:",
        html,
        re.DOTALL,
    )
    if not block:
        return []

    fansubs: list[Fansub] = []
    for item in re.findall(r"\{[^{}]*\}", block.group(1)):
        id_match = re.search(r'\bid\s*:\s*"([^"]+)"', item)
        name_match = re.search(r'\bname\s*:\s*"([^"]+)"', item)
        secure_match = re.search(r'\bsecureName\s*:\s*"([^"]+)"', item)
        if not (id_match and name_match and secure_match):
            continue

        is_4k_match = re.search(r"\bis4K\s*:\s*(true|false)", item)
        fansubs.append(
            Fansub(
                id=id_match.group(1),
                name=name_match.group(1),
                secure_name=secure_match.group(1),
                is_4k=bool(is_4k_match and is_4k_match.group(1) == "true"),
            )
        )

    return fansubs
