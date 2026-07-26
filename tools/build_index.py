#!/usr/bin/env python3
"""Generate docs/index.html (the subscribe page) from the CITIES preset table.

Run after adding or changing a preset so the landing page never drifts from
rahu_kalam_ics.CITIES. CI runs this alongside feed regeneration. The GitHub owner
and repository are read from the GITHUB_REPOSITORY environment variable when
present (set automatically in GitHub Actions), so a fork produces its own URLs;
otherwise the canonical defaults below are used.
"""

import html
import os
import sys

# Import the single-file core from the repo root regardless of where this runs.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rahu_kalam_ics as rk


def _owner_repo():
    """Return (owner, repo) from GITHUB_REPOSITORY if set, else canonical defaults."""

    slug = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in slug:
        owner, repo = slug.split("/", 1)
        return owner, repo
    return "archulan", "rahu-kalam-ics"


def _card(slug, city, owner, repo):
    url = "https://{0}.github.io/{1}/{2}.ics".format(owner, repo, slug)
    webcal = "webcal://{0}.github.io/{1}/{2}.ics".format(owner, repo, slug)
    return (
        '      <div class="card">\n'
        '        <div class="city">{name}</div>\n'
        '        <code class="url">{url}</code>\n'
        '        <div class="actions">\n'
        '          <button class="copy" data-url="{url}">Copy URL</button>\n'
        '          <a class="add" href="{webcal}">Add</a>\n'
        '        </div>\n'
        '      </div>\n'
    ).format(name=html.escape(city.name), url=html.escape(url), webcal=html.escape(webcal))


def _grid(rows, owner, repo):
    return '    <div class="grid">\n' + "".join(_card(s, c, owner, repo) for s, c in rows) + '    </div>\n'


def render():
    """Return the full index.html document as a string."""

    owner, repo = _owner_repo()

    # Group by home region via timezone: Sri Lanka (Asia/Colombo) and India
    # (Asia/Kolkata) get their own sections; everything else is diaspora.
    sri_lanka = [(s, c) for s, c in rk.CITIES.items() if c.tz == "Asia/Colombo"]
    india = [(s, c) for s, c in rk.CITIES.items() if c.tz == "Asia/Kolkata"]
    diaspora = [(s, c) for s, c in rk.CITIES.items() if c.tz not in ("Asia/Colombo", "Asia/Kolkata")]

    disclaimer = html.escape(
        "Different panchang traditions define sunrise differently (upper limb with "
        "refraction vs centre of disk), which produces legitimate variations of a few "
        "minutes between sources. This project publishes astronomically computed "
        "timings, states its convention (civil sunrise, zenith 90.833 degrees), and "
        "takes no position on religious interpretation. It is not a substitute for a "
        "full panchang."
    )

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rahu Kalam calendar feeds</title>
<style>
  :root {{
    --bg: #ffffff; --fg: #1a1a1a; --muted: #5a5a5a; --card: #f5f5f7;
    --border: #e2e2e6; --accent: #7a3ea8; --accent-fg: #ffffff;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #14141a; --fg: #ececf0; --muted: #a0a0aa; --card: #1e1e26;
      --border: #2c2c38; --accent: #b98bdd; --accent-fg: #14141a;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--fg);
    font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }}
  main {{ max-width: 860px; margin: 0 auto; padding: 2rem 1.1rem 4rem; }}
  h1 {{ font-size: 1.8rem; margin: 0 0 .3rem; }}
  h2 {{ font-size: 1.15rem; margin: 2rem 0 .8rem; }}
  .lead {{ color: var(--muted); margin: 0 0 1.5rem; }}
  ol {{ padding-left: 1.2rem; }}
  .note {{ color: var(--muted); font-size: .92rem; }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: .7rem;
  }}
  .card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: .8rem .9rem; display: flex; flex-direction: column; gap: .5rem;
  }}
  .city {{ font-weight: 600; }}
  .url {{
    font-size: .72rem; color: var(--muted); word-break: break-all;
    background: transparent;
  }}
  .actions {{ display: flex; gap: .5rem; align-items: center; margin-top: auto; }}
  button.copy, a.add {{
    font: inherit; font-size: .82rem; border-radius: 7px; cursor: pointer;
    padding: .35rem .7rem; border: 1px solid var(--border); text-decoration: none;
  }}
  button.copy {{ background: var(--accent); color: var(--accent-fg); border-color: transparent; }}
  a.add {{ background: transparent; color: var(--fg); }}
  .disclaimer {{
    margin-top: 2.5rem; padding: 1rem 1.1rem; border-left: 3px solid var(--accent);
    background: var(--card); border-radius: 0 8px 8px 0; color: var(--muted);
    font-size: .92rem;
  }}
  footer {{ margin-top: 2.5rem; color: var(--muted); font-size: .88rem; }}
  a {{ color: var(--accent); }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
</style>
</head>
<body>
<main>
  <h1>Rahu Kalam calendar feeds</h1>
  <p class="lead">Free, auto-updating Rahu Kalam feeds for your calendar. Timings
  are computed from local sunrise and sunset, so they stay accurate every day of
  the year. No app, no account, no tracking.</p>

  <section>
    <h2>How to subscribe</h2>
    <ol>
      <li>Copy your city's feed URL below.</li>
      <li>In Google Calendar, open <strong>Other calendars &rarr; + &rarr; From URL</strong>,
      paste the link, and choose <strong>Add calendar</strong>. (On Apple
      Calendar, use <strong>Add</strong> to subscribe by URL.)</li>
      <li>Done. The feed refreshes itself. You never re-import.</li>
    </ol>
    <p class="note">Subscribing keeps the calendar in sync as new days are added.
    Downloading and importing a file is a one-time copy that will not update.</p>
  </section>

  <section>
    <h2>Sri Lanka</h2>
{sri_lanka}
    <h2>India</h2>
{india}
    <h2>Diaspora</h2>
{diaspora}
  </section>

  <div class="disclaimer">{disclaimer}</div>

  <footer>
    Open source (<a href="https://github.com/{owner}/{repo}">GitHub</a>), MIT
    licensed. Your city missing? Add it with a small pull request.
  </footer>
</main>
<script>
  for (const btn of document.querySelectorAll("button.copy")) {{
    btn.addEventListener("click", async () => {{
      try {{
        await navigator.clipboard.writeText(btn.dataset.url);
        const original = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => {{ btn.textContent = original; }}, 1400);
      }} catch (e) {{ /* clipboard unavailable; the URL is visible to copy manually */ }}
    }});
  }}
</script>
</body>
</html>
""".format(
        sri_lanka=_grid(sri_lanka, owner, repo),
        india=_grid(india, owner, repo),
        diaspora=_grid(diaspora, owner, repo),
        disclaimer=disclaimer,
        owner=owner,
        repo=repo,
    )


def main():
    """Write docs/index.html next to the generated feeds."""

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(render())
    print("Wrote {0}".format(path))


if __name__ == "__main__":
    main()
