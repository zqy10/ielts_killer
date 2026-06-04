#!/usr/bin/env python3
"""Fetch English text from YouTube/TED (subtitles) or news articles."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VIDEO_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com",
    "ted.com",
    "www.ted.com",
}

ARTICLE_HINTS = {
    "bbc.com",
    "www.bbc.com",
    "bbc.co.uk",
    "www.bbc.co.uk",
    "reuters.com",
    "www.reuters.com",
    "theguardian.com",
    "www.theguardian.com",
    "nytimes.com",
    "www.nytimes.com",
    "economist.com",
    "www.economist.com",
    "apnews.com",
    "www.apnews.com",
}

# Subset of AWL lemmas for candidate boosting (see reference.md)
AWL_BOOST = frozenset(
    """
    analysis approach area assessment assume authority available benefit concept
    consistent constitutional context contract create data definition derived
    distribution economic environment established estimate evidence export factors
    financial formula function identified income indicate individual interpretation
    involved issues labour legal legislation major method occur percent period policy
    principle procedure process required research response role section sector
    significant similar source specific structure theory variables
    """.split()
)

# Shared exclude list (see reference.md)
COMMON_STOP = frozenset(
    """
    that this with from have been were they their there would could should about which when
    what your will just more some than them then also into only other because before after
    being these those through where while during after before very much many most such same
    """.split()
)

NEWS_BAN = frozenset(
    """
    attack strike kill injure official country deal leader person time news report claim deny
    target fire launch meet tell like early later foreign national regional military iranian
    indian communist american british state government party president minister spokesman
    said says told ask asked week month year day today yesterday tomorrow
    """.split()
)


def detect_source_type(url: str, forced: str | None) -> str:
    if forced and forced != "auto":
        return forced
    host_full = urlparse(url).netloc.lower()
    host = host_full[4:] if host_full.startswith("www.") else host_full
    if any(h in host_full for h in ("youtube", "youtu.be", "ted.com")):
        return "video"
    if host in ARTICLE_HINTS or host_full in ARTICLE_HINTS:
        return "article"
    # Default: try video for known video paths, else article
    if "watch" in url or "youtu.be" in url:
        return "video"
    return "article"


def vtt_to_text(vtt_content: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in vtt_content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if re.match(r"^\d+$", line):
            continue
        if re.match(r"^\d{2}:\d{2}", line) or "-->" in line:
            continue
        if line.startswith("STYLE") or line.startswith("Kind:"):
            continue
        # Strip VTT tags
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{[^}]+\}", "", line)
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return " ".join(lines)


def srt_to_text(srt_content: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in srt_content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^\d+$", line):
            continue
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return " ".join(lines)


def youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if "youtu.be" in host:
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid or None
    if "youtube" in host:
        qs = parse_qs(parsed.query)
        return (qs.get("v") or [None])[0]
    return None


def _video_metadata(url: str) -> tuple[str, str, str]:
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "--print",
        "%(title)s",
        "--print",
        "%(upload_date)s",
        "--print",
        "%(webpage_url)s",
        "--no-warnings",
        url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        return "unknown", "unknown", url
    if proc.returncode != 0:
        return "unknown", "unknown", url
    prints = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    title = prints[0] if prints else "unknown"
    upload_date = prints[1] if len(prints) > 1 else "unknown"
    webpage_url = prints[2] if len(prints) > 2 else url
    return title, upload_date, webpage_url


def fetch_transcript_api(url: str) -> tuple[str, list[str]]:
    """Fetch English transcript via youtube-transcript-api (works when yt-dlp subs need PO token)."""
    warnings: list[str] = []
    vid = youtube_video_id(url)
    if not vid:
        return "", ["youtube_transcript_api: could not parse video id"]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return "", ["youtube-transcript-api not installed"]

    try:
        fetched = YouTubeTranscriptApi().fetch(vid, languages=["en", "en-US", "en-GB"])
        snippets = getattr(fetched, "snippets", fetched)
        parts = []
        for item in snippets:
            text = getattr(item, "text", None) or (item.get("text") if isinstance(item, dict) else str(item))
            if text:
                parts.append(text.replace("\n", " ").strip())
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if text:
            warnings.append("transcript_source:youtube-transcript-api")
        return text, warnings
    except Exception as exc:
        return "", [f"youtube_transcript_api_failed: {exc}"]


def fetch_video(url: str) -> dict:
    warnings: list[str] = []
    title, upload_date, webpage_url = _video_metadata(url)

    text, api_warnings = fetch_transcript_api(url)
    warnings.extend(api_warnings)
    if text and len(text) >= 50:
        return {
            "title": title,
            "url": webpage_url,
            "date": _format_date(upload_date),
            "source_type": "video",
            "text": text,
            **build_candidate_pools(text),
            "warnings": warnings,
        }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        out_tpl = str(tmp_path / "sub")
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--skip-download",
            "--write-sub",
            "--write-auto-sub",
            "--sub-lang",
            "en.*,en",
            "--convert-subs",
            "vtt",
            "--sub-format",
            "vtt/best",
            "-o",
            out_tpl,
            "--print",
            "%(title)s",
            "--print",
            "%(upload_date)s",
            "--print",
            "%(webpage_url)s",
            "--no-warnings",
            url,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _error("yt-dlp timed out after 120s")

        if proc.returncode != 0:
            warnings.append(f"yt-dlp_subs_failed: {(proc.stderr or '')[:200]}")
            vtt_files = []
        else:
            vtt_files = list(tmp_path.glob("*.vtt")) + list(tmp_path.glob("*.en*.vtt"))

        if not vtt_files:
            warnings.append("no_english_subtitles_vtt: used transcript API or paste .vtt via clean_text.py")
            return {
                "title": title,
                "url": webpage_url,
                "date": _format_date(upload_date),
                "source_type": "video",
                "text": text,
                **build_candidate_pools(text),
                "warnings": warnings,
            }

        vtt_files.sort(key=lambda p: ("en" not in p.name.lower(), len(p.name)))
        text = vtt_to_text(vtt_files[0].read_text(encoding="utf-8", errors="replace"))
        if len(text) < 50:
            warnings.append("subtitle_text_very_short")

        return {
            "title": title,
            "url": webpage_url,
            "date": _format_date(upload_date),
            "source_type": "video",
            "text": text,
            **build_candidate_pools(text),
            "warnings": warnings,
        }


def _fetch_html_fallback(url: str) -> str | None:
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; IELTS-Vocab-Miner/1.0; +https://cursor.com)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch_article(url: str) -> dict:
    warnings: list[str] = []
    try:
        import trafilatura
    except ImportError:
        return _error("trafilatura not installed; run: pip install -r requirements.txt")

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        downloaded = _fetch_html_fallback(url)
        if downloaded:
            warnings.append("trafilatura_fetch_used_urllib_fallback")
        else:
            warnings.append("trafilatura_fetch_failed: try WebFetch fallback per SKILL.md")
        return {
            "title": "unknown",
            "url": url,
            "date": "unknown",
            "source_type": "article",
            "text": "",
            "candidates_ielts": [],
            "candidates_advanced": [],
            "candidates": [],
            "warnings": warnings,
        }

    meta = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        output_format="json",
        with_metadata=True,
        url=url,
    )
    text = ""
    title = "unknown"
    date = "unknown"
    if meta:
        try:
            data = json.loads(meta)
            text = (data.get("text") or "").strip()
            title = (data.get("title") or title).strip()
            date = _format_date(data.get("date") or data.get("sitename") or "unknown")
        except json.JSONDecodeError:
            text = trafilatura.extract(downloaded, url=url) or ""
    else:
        text = trafilatura.extract(downloaded, url=url) or ""

    if not text:
        warnings.append("article_extract_empty")
    if date == "unknown":
        # Try bare extract metadata
        bare = trafilatura.bare_extraction(downloaded, url=url)
        if bare and getattr(bare, "date", None):
            date = _format_date(str(bare.date))

    return {
        "title": title,
        "url": url,
        "date": date,
        "source_type": "article",
        "text": text,
        **build_candidate_pools(text),
        "warnings": warnings,
    }


def _lemma_is_excluded(lemma: str) -> bool:
    if lemma in COMMON_STOP or lemma in NEWS_BAN:
        return True
    if len(lemma) < 4:
        return True
    return False


def _collect_token_stats(text: str) -> list[dict]:
    """Return list of {lemma, pos, count, sample} from text."""
    if not text or len(text) < 20:
        return []
    try:
        import spacy

        nlp = spacy.load("en_core_web_sm")
    except Exception:
        return _collect_token_stats_fallback(text)

    doc = nlp(text[:500000])
    counts: dict[tuple[str, str], int] = {}
    samples: dict[tuple[str, str], str] = {}

    for sent in doc.sents:
        sent_text = sent.text.strip()
        for token in sent:
            if token.is_stop or token.is_punct or token.is_space:
                continue
            if not token.is_alpha:
                continue
            lemma = token.lemma_.lower()
            if _lemma_is_excluded(lemma):
                continue
            if token.pos_ not in ("NOUN", "VERB", "ADJ", "ADV"):
                continue
            key = (lemma, token.pos_)
            counts[key] = counts.get(key, 0) + 1
            if key not in samples and len(sent_text) <= 200:
                samples[key] = sent_text

    rows: list[dict] = []
    for (lemma, pos), count in counts.items():
        rows.append(
            {
                "lemma": lemma,
                "pos": pos,
                "count": count,
                "sample": (samples.get((lemma, pos)) or "")[:200],
            }
        )
    return rows


def _collect_token_stats_fallback(text: str) -> list[dict]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text.lower())
    counts: dict[str, int] = {}
    for w in words:
        w = w.strip("'")
        if _lemma_is_excluded(w):
            continue
        counts[w] = counts.get(w, 0) + 1
    return [
        {"lemma": lemma, "pos": "UNK", "count": count, "sample": ""}
        for lemma, count in counts.items()
    ]


_LEARNER_WEIGHTS: dict | None = None


def _get_learner_weights() -> dict:
    global _LEARNER_WEIGHTS
    if _LEARNER_WEIGHTS is None:
        try:
            from learner import load_learner_weights

            _LEARNER_WEIGHTS = load_learner_weights()
        except Exception:
            _LEARNER_WEIGHTS = {
                "lemma_boost": {},
                "lemma_penalty": {},
                "reject_lemmas": set(),
                "min_length_preference": 7,
                "pos_boost": {},
            }
    return _LEARNER_WEIGHTS


def _apply_learner(score: float, row: dict) -> float:
    try:
        from learner import apply_learner_score_adjustment

        return apply_learner_score_adjustment(
            score, row["lemma"], row.get("pos", "UNK"), _get_learner_weights()
        )
    except Exception:
        return score


def _score_ielts(row: dict) -> float:
    lemma, count = row["lemma"], row["count"]
    score = float(count)
    if lemma in AWL_BOOST:
        score += 3.0
    if count >= 2:
        score += 1.0
    if len(lemma) >= 7:
        score += 0.5
    if lemma in NEWS_BAN:
        score -= 5.0
    # Band 8.5+: down-rank over-frequent mid-tier news lexis
    if lemma in {"missile", "drone", "airport", "ceasefire", "significant", "important"}:
        score -= 2.0
    return _apply_learner(score, row)


def _score_advanced(row: dict) -> float:
    lemma, count = row["lemma"], row["count"]
    score = 0.0
    if lemma in NEWS_BAN or lemma in COMMON_STOP:
        return -10.0
    if len(lemma) >= 10:
        score += 3.0
    elif len(lemma) >= 8:
        score += 2.0
    elif len(lemma) >= 6:
        score += 0.5
    else:
        score -= 1.0
    if count == 1:
        score += 1.5
    elif count == 2:
        score += 0.5
    if lemma in AWL_BOOST and count >= 3:
        score -= 2.0
    if "-" in lemma or " " in lemma:
        score += 1.0
    return _apply_learner(score, row)


def _rank_pool(rows: list[dict], scorer, limit: int = 40) -> list[dict]:
    ranked: list[tuple[float, dict]] = []
    for row in rows:
        s = scorer(row)
        if s <= 0:
            continue
        ranked.append((s, {**row, "score": round(s, 2)}))
    ranked.sort(key=lambda x: (-x[0], x[1]["lemma"]))
    return [item for _, item in ranked[:limit]]


def build_candidate_pools(text: str) -> dict:
    rows = _collect_token_stats(text)
    ielts = _rank_pool(rows, _score_ielts, 40)
    advanced = _rank_pool(rows, _score_advanced, 40)
    seen: set[str] = set()
    merged: list[dict] = []
    for pool in (ielts, advanced):
        for item in pool:
            if item["lemma"] in seen:
                continue
            seen.add(item["lemma"])
            merged.append(item)
    merged.sort(key=lambda x: (-x.get("score", 0), x["lemma"]))
    return {
        "candidates_ielts": ielts,
        "candidates_advanced": advanced,
        "candidates": merged[:80],
    }


def extract_candidates(text: str, limit: int = 80) -> list[dict]:
    """Backward-compatible: merged candidate list."""
    return build_candidate_pools(text)["candidates"][:limit]


def _format_date(raw: str) -> str:
    if not raw or raw == "unknown":
        return "unknown"
    digits = re.sub(r"\D", "", str(raw))[:8]
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return "unknown"


def _error(msg: str) -> dict:
    return {
        "title": "unknown",
        "url": "",
        "date": "unknown",
        "source_type": "error",
        "text": "",
        "candidates_ielts": [],
        "candidates_advanced": [],
        "candidates": [],
        "warnings": [msg],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch English content for IELTS vocab mining")
    parser.add_argument("--url", required=True, help="Video or article URL")
    parser.add_argument("--type", default="auto", choices=["auto", "video", "article"])
    parser.add_argument("--out", help="Write JSON to this path (also prints to stdout)")
    args = parser.parse_args()

    source_type = detect_source_type(args.url, args.type)
    if source_type == "video":
        result = fetch_video(args.url)
    else:
        result = fetch_article(args.url)

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)

    if not result.get("text") and result.get("warnings"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
