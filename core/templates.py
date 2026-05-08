import sublime
from string import Template

from .constants import SHA_DISPLAY_SHORT, SHA_DISPLAY_LONG


_BLAME_PHANTOM = Template(
    '<body id="inline-git-blame">'
    "<style>"
    "  a { color: color(var(--foreground) alpha(0.4)); font-style: italic;"
    " font-size: 0.9em; text-decoration: none; }"
    "  a:hover { text-decoration: underline; }"
    "</style>"
    "${spacing}"
    '<a href="details:${sha}">'
    "${author}, ${date_str} "
    "(${sha_short})"
    " \u2014 ${summary}"
    "</a>"
    "</body>"
)


_DETAILS_POPUP = Template(
    '<body id="inline-git-blame-popup">'
    "<style>"
    "  body { padding: 8px; font-size: 0.9em; }"
    "  h3 { margin: 0 0 4px 0; }"
    "  .meta { color: color(var(--foreground) alpha(0.7)); margin: 2px 0; }"
    "  .sha { font-family: monospace; }"
    "  .actions { margin-top: 8px; }"
    "  .actions a { margin-right: 12px; }"
    "</style>"
    "<h3>${subject}</h3>"
    '<p class="meta"><span class="sha">${sha_display}</span></p>'
    '<p class="meta">${author} &lt;${email}&gt;</p>'
    '<p class="meta">${date}</p>'
    "${body_html}"
    '<div class="actions">${copy_link} ${open_link}</div>'
    "</body>"
)


def render_blame_phantom(author, date_str, sha, summary, spacing_html):
    return _BLAME_PHANTOM.substitute(
        spacing=spacing_html,
        author=author,
        date_str=date_str,
        sha=sha,
        sha_short=sha[:SHA_DISPLAY_SHORT],
        summary=sublime.html.escape(summary),
    )


def render_details_popup(subject, sha, author, email, date, body, remote_url):
    copy_link = f'<a href="copy:{sha}">Copy SHA</a>'

    open_link = ""
    if remote_url:
        commit_url = f"{remote_url}/commit/{sha}"
        open_link = f'<a href="open:{commit_url}">Open in browser</a>'

    body_html = ""
    if body:
        body_html = (
            '<p style="margin-top: 8px; white-space: pre-wrap;">'
            f"{sublime.html.escape(body)}</p>"
        )

    return _DETAILS_POPUP.substitute(
        subject=sublime.html.escape(subject),
        sha_display=sha[:SHA_DISPLAY_LONG],
        author=sublime.html.escape(author),
        email=sublime.html.escape(email),
        date=sublime.html.escape(date),
        body_html=body_html,
        copy_link=copy_link,
        open_link=open_link,
    )
