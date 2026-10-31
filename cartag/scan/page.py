from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from cartag.scan.i18n import STRINGS, Language

# Autoescape is on for every .html template, so any text an owner typed is escaped by default.
_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_scan_page(tag: dict[str, Any], lang: Language, code: str) -> tuple[int, str]:
    """Returns (status code, HTML) for what a finder sees after scanning.

    The owner's phone numbers are only used inside the Call and WhatsApp links. They are never
    printed as text on the page.
    """
    s = STRINGS[lang]
    state = tag["state"]
    titles = {
        "not_found": s.not_found_title,
        "not_active": s.not_active_title,
        "turned_off": s.turned_off_title,
        "retired": s.retired_title,
        "active": s.active_title,
    }
    context: dict[str, Any] = {
        "s": s,
        "state": state,
        "title": titles[state],
        # An unknown code is not echoed back in the language switch, so the generic page leaks nothing.
        "switch_href": f"?lang={s.switch_to}" if state == "not_found" else f"/t/{code}?lang={s.switch_to}",
    }

    if state == "not_active":
        context["code"] = tag["code"]
    if state == "active":
        emergency = tag["emergency"]
        context.update(
            owner=tag["owner"],
            emergency=emergency,
            emergency_contact_line=s.relation(emergency["contactName"], emergency["relationship"]) if emergency else "",
        )

    html = _env.get_template("scan.html").render(**context)
    return (404 if state == "not_found" else 200), html
