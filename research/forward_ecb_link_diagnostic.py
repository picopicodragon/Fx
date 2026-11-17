"""Read-only forensic summary of a locally saved ECB news RSS XML.

No network, no journal writes, no URL allowlist changes, no orders or AI.
A hostname printed here is evidence to REVIEW, not automatically a trusted host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

from research import forward_multi_official_news_snapshot as news
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_ecb_saved_xml_link_diagnostic_v1"
ECBF = "ecb_press"
_HOST = news.SOURCE_HOSTS[ECBF]
_MASKED = "UNREVIEWED_NON_EUROPA_HOST"


def _reason(uri: str) -> tuple[str, str, str]:
    """Host and reason are display-only, never used to grant access."""
    if not isinstance(uri, str) or len(uri) > 1400 or any(c.isspace() for c in uri):
        return "(invalid)", "(invalid)", "INVALID_URL"
    try:
        parts = urlsplit(uri)
        scheme = parts.scheme.lower()
        host = (parts.hostname or "").lower()
        if parts.port not in (None, 443) or parts.username is not None or (
                parts.password is not None):
            reason = "PORT_OR_CREDENTIALS_REJECTED"
        elif parts.fragment:
            reason = "FRAGMENT_REJECTED"
        elif scheme != "https":
            reason = "NON_HTTPS_REJECTED"
        elif host != _HOST:
            reason = "OFF_HOST_REJECTED"
        elif not parts.path:
            reason = "EMPTY_URL_PATH"
        elif parts.path.startswith("//") and news._ecb_legacy_double_slash_path(
                parts.path):
            reason = "ECB_LEGACY_PATH_PRESERVED_METADATA_ONLY"
        elif parts.path.startswith("//"):
            reason = "DOUBLE_SLASH_URL_PATH"
        elif not parts.path.startswith("/"):
            reason = "URL_PATH_NOT_ABSOLUTE"
        else:
            reason = "ALLOWLIST_MATCHED"
        if not re.fullmatch(r"[a-z0-9.-]{1,253}", host):
            host_label = "(invalid)"
        elif host == "ecb.europa.eu" or host.endswith(".europa.eu"):
            host_label = host
        elif host == _HOST:
            host_label = host
        else:
            host_label = _MASKED
        return scheme or "(none)", host_label, reason
    except ValueError:
        return "(invalid)", "(invalid)", "MALFORMED_URL"


def inspect_file(original: Path) -> dict:
    if (not original.is_file() or original.is_symlink()
            or any(p.is_symlink() for p in original.parents)
            or not 0 < original.stat().st_size <= news.MAX_XML):
        raise InputError("unsafe original XML file")
    raw = original.read_bytes()
    if (not 0 < len(raw) <= news.MAX_XML or
            b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper()):
        raise InputError("unsafe XML structure")
    root = ET.fromstring(raw)
    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise InputError("missing RSS channel")
        items = [(el.findtext("link") or "").strip()
                 for el in channel.findall("item")]
    elif root.tag == news.ATOM + "feed":
        items = []
        for entry in root.findall(news.ATOM + "entry"):
            links = [el.get("href") or "" for el in entry.findall(news.ATOM + "link")
                     if el.get("rel", "alternate") == "alternate"]
            # Preserve malformed link cardinality as a separate reject.
            items.append(links[0] if len(links) == 1 else "")
    else:
        raise InputError("unsupported XML feed root")
    if len(items) > news.MAX_ENTRIES:
        raise InputError("too many RSS items")
    grouped: dict[tuple[str, str, str], int] = {}
    rejected = 0
    for link in items:
        category = _reason(link)
        grouped[category] = grouped.get(category, 0) + 1
        rejected += int(category[2] not in (
            "ALLOWLIST_MATCHED", "ECB_LEGACY_PATH_PRESERVED_METADATA_ONLY"))
    return {
        "schema": SCHEMA,
        "status": "ECB_SAVED_XML_LINK_DIAGNOSTIC_NO_GO",
        "original_bytes": len(raw),
        "original_sha256_local_only": hashlib.sha256(raw).hexdigest(),
        "item_count": len(items),
        "distinct_link_count": len(set(items)),
        "items_not_matching_existing_allowlist": rejected,
        "link_groups": [
            {"scheme": scheme, "hostname_unverified": host,
             "validation_reason": reason, "count": count}
            for (scheme, host, reason), count in sorted(grouped.items())
        ],
        "hostnames_are_not_authenticated_or_approved": True,
        "network_calls_this_run": 0,
        "journal_writes_this_run": 0,
        "ai_inference_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline-only ECB XML link analysis")
    p.add_argument("--xml-file", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        report = inspect_file(args.xml_file)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (InputError, ET.ParseError, OSError, ValueError, TypeError,
            UnicodeError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "ECB_SAVED_XML_DIAGNOSTIC_FAIL_CLOSED_NO_GO",
            "reason": "INVALID_LOCAL_XML",
            "network_calls_this_run": 0,
            "journal_writes_this_run": 0,
            "orders_sent_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
