"""ATS Lookup Service — discover job board URL for a company by trying slug+ATS combinations."""

import asyncio
import logging
import re

import aiohttp

logger = logging.getLogger(__name__)

# ATS API endpoints — {slug} is replaced with the candidate slug
ATS_APIS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "lever": "https://api.lever.co/v0/postings/{slug}",
}

ATS_JOB_URLS = {
    "greenhouse": "https://boards.greenhouse.io/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
}


def generate_slugs(company_name: str) -> list[str]:
    """Generate all plausible job board slugs from a company name."""
    name = company_name.strip()
    if not name:
        return []

    slugs: set[str] = set()
    lower = name.lower()

    # Clean special suffixes like .io, .ai, .com, etc.
    suffix_match = re.search(r'\.(io|ai|com|co|dev|app|xyz|tech|so|gg|sh|ly|me)$', lower)
    without_suffix = re.sub(r'\.(io|ai|com|co|dev|app|xyz|tech|so|gg|sh|ly|me)$', '', lower) if suffix_match else None

    # Handle & -> "and"
    has_ampersand = '&' in lower
    with_and = lower.replace('&', 'and').replace('  ', ' ')
    without_and = re.sub(r'\s*&\s*', '', lower)

    bases = [lower]
    if has_ampersand:
        bases.append(with_and)
        bases.append(without_and)
    if without_suffix:
        bases.append(without_suffix)
        joined_suffix = re.sub(r'\.', '', lower)
        bases.append(joined_suffix)

    for base in bases:
        base = re.sub(r'\s*\([^)]*\)', '', base).strip()
        words = re.findall(r'[a-z0-9]+', base)
        if words:
            slugs.add('-'.join(words))
            slugs.add(''.join(words))

            if len(words) > 1:
                filtered = [w for w in words if w not in ('the', 'inc', 'ltd', 'llc', 'corp', 'corporation')]
                if filtered and filtered != words:
                    slugs.add('-'.join(filtered))
                    slugs.add(''.join(filtered))

                if len(words) >= 3:
                    initials = ''.join(w[0] for w in words if w not in ('the', 'and', 'of', 'for'))
                    if len(initials) >= 2:
                        slugs.add(initials)

            if len(words) > 1:
                slugs.add(words[0])

    slugs.discard('')
    return sorted(slugs)


async def check_ats(session: aiohttp.ClientSession, slug: str, ats_name: str) -> str | None:
    """Check if a slug is valid on a given ATS. Returns the job board URL if found."""
    url = ATS_APIS[ats_name].format(slug=slug)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.text()
                if data and len(data) > 10:
                    return ATS_JOB_URLS[ats_name].format(slug=slug)
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    return None


async def lookup_ats(
    company_name: str,
    ats_type: str | None = None,
    board_token: str | None = None,
) -> dict | None:
    """Discover ATS platform and board token for a company.

    Args:
        company_name: Required company name.
        ats_type: Optional ATS type constraint ("greenhouse", "ashby", "lever").
        board_token: Optional board token/slug constraint.

    Returns:
        dict with {"ats_type": str, "board_token": str} or None if not found.
    """
    async with aiohttp.ClientSession() as session:
        # Case 1: Both provided — just verify
        if ats_type and board_token:
            result = await check_ats(session, board_token, ats_type)
            if result:
                return {"ats_type": ats_type, "board_token": board_token}
            return None

        # Case 2: ATS set, no board token — try generated slugs on that ATS only
        if ats_type and not board_token:
            slugs = generate_slugs(company_name)
            tasks = [check_ats(session, slug, ats_type) for slug in slugs]
            task_slugs = slugs
            results = await asyncio.gather(*tasks)
            for i, result in enumerate(results):
                if result:
                    return {"ats_type": ats_type, "board_token": task_slugs[i]}
            return None

        # Case 3: Board token set, no ATS — try token on all ATS systems
        if board_token and not ats_type:
            ats_names = list(ATS_APIS.keys())
            tasks = [check_ats(session, board_token, ats) for ats in ats_names]
            results = await asyncio.gather(*tasks)
            for i, result in enumerate(results):
                if result:
                    return {"ats_type": ats_names[i], "board_token": board_token}
            return None

        # Case 4: Neither set — full discovery (all slugs × all ATS)
        slugs = generate_slugs(company_name)
        tasks = []
        task_info = []
        for slug in slugs:
            for ats_name in ATS_APIS:
                tasks.append(check_ats(session, slug, ats_name))
                task_info.append((ats_name, slug))

        results = await asyncio.gather(*tasks)
        for i, result in enumerate(results):
            if result:
                ats_name, slug = task_info[i]
                logger.info(f"Discovered {company_name}: {ats_name} / {slug}")
                return {"ats_type": ats_name, "board_token": slug}

        return None
