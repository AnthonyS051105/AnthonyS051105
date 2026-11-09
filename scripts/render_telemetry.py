"""Render Open Lab's contribution panel from the public GitHub profile calendar."""

import json
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

QUERY = """
query ($login: String!) {
  user(login: $login) {
    repositories(privacy: PUBLIC, ownerAffiliations: [OWNER]) { totalCount }
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays { date weekday contributionCount contributionLevel }
        }
      }
    }
  }
}
"""

LEVELS = {
    "NONE": "#352859",
    "FIRST_QUARTILE": "#554180",
    "SECOND_QUARTILE": "#886AC1",
    "THIRD_QUARTILE": "#C6B0FF",
    "FOURTH_QUARTILE": "#DFFF70",
}
DAYS = ("Sun", "", "Tue", "", "Thu", "", "Sat")


def fetch_profile(login, token):
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Open-Lab-Profile",
        },
    )
    with urlopen(request, timeout=25) as response:
        result = json.load(response)
    if result.get("errors"):
        messages = ", ".join(error["message"] for error in result["errors"])
        raise RuntimeError(f"GitHub GraphQL returned: {messages}")
    profile = result.get("data", {}).get("user")
    if not profile:
        raise RuntimeError("GitHub did not return a user profile")
    return profile


def render(profile):
    calendar = profile["contributionsCollection"]["contributionCalendar"]
    weeks = [week["contributionDays"] for week in calendar["weeks"]]
    days = [day for week in weeks for day in week]
    if not days or len(weeks) > 54 or not all(weeks):
        raise ValueError("Unexpected GitHub contribution calendar")

    dates = [date.fromisoformat(day["date"]) for day in days]
    active = sorted(
        date.fromisoformat(day["date"]) for day in days if day["contributionCount"] > 0
    )
    total = sum(day["contributionCount"] for day in days)
    previous = None
    streak = longest = 0
    for active_date in active:
        streak = streak + 1 if previous and active_date - previous == timedelta(days=1) else 1
        longest = max(longest, streak)
        previous = active_date

    metrics = (
        ("CONTRIBUTIONS", total),
        ("ACTIVE DAYS", len(active)),
        ("LONGEST STREAK", longest),
        ("PUBLIC REPOS", profile["repositories"]["totalCount"]),
    )
    description = (
        f"From {min(dates).isoformat()} to {max(dates).isoformat()}, the visible GitHub "
        f"calendar has {total} contributions on {len(active)} active days. "
        f"The longest streak is {longest} days."
    )

    elements = [f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 350" role="img" aria-labelledby="title desc">
  <title id="title">Open Lab GitHub telemetry</title>
  <desc id="desc">{description}</desc>
  <defs>
    <clipPath id="grid"><rect x="67" y="187" width="934" height="117" rx="3"/></clipPath>
  </defs>
  <style>
    @media (prefers-reduced-motion: no-preference) {{
      .sweep {{ animation: sweep 4.2s ease-out both; }}
    }}
    @keyframes sweep {{
      0% {{ transform: translateX(0); opacity: 0; }}
      14%, 78% {{ opacity: .68; }}
      100% {{ transform: translateX(934px); opacity: 0; }}
    }}
  </style>
  <rect x="1" y="1" width="1038" height="348" rx="21" fill="#211844" stroke="#8D79BB" stroke-width="2"/>
  <circle cx="30" cy="31" r="5" fill="#DFFF70"/>
  <text x="46" y="38" fill="#DFFF70" font-family="monospace" font-size="18" font-weight="700" letter-spacing="2">OPEN LAB / TELEMETRY</text>
  <text x="1008" y="38" fill="#C9BDF2" font-family="monospace" font-size="16" text-anchor="end">VISIBLE ACTIVITY · PAST YEAR</text>
  <g font-family="monospace" font-weight="700">"""]

    for index, (label, number) in enumerate(metrics):
        x = 29 + index * 248
        accent = "#DFFF70" if index == 0 else "#F2ECFF"
        elements.append(f"""    <rect x="{x}" y="59" width="237" height="88" rx="12" fill="#302253" stroke="#634F94"/>
    <text x="{x + 16}" y="85" fill="#C9BDF2" font-size="15" letter-spacing="1.4">{label}</text>
    <text x="{x + 16}" y="129" fill="{accent}" font-size="37">{number:,}</text>""")
    elements.append('  </g>')

    step = 934 / len(weeks)
    size = min(14, step - 2)
    for index, week in enumerate(weeks):
        x = 67 + index * step
        for day in week:
            y = 187 + day["weekday"] * 17
            color = LEVELS[day["contributionLevel"]]
            elements.append(f'  <rect x="{x:.2f}" y="{y}" width="{size:.2f}" height="14" rx="3" fill="{color}"/>')

    elements.append('  <g fill="#C9BDF2" font-family="monospace" font-size="13">')
    last_month = None
    last_label = -4
    for index, week in enumerate(weeks):
        first = date.fromisoformat(week[0]["date"])
        if first.month != last_month and index - last_label >= 3 and index < len(weeks) - 1:
            elements.append(f'    <text x="{67 + index * step:.2f}" y="175">{first:%b}</text>')
            last_month = first.month
            last_label = index
    for index, label in enumerate(DAYS):
        if label:
            elements.append(f'    <text x="31" y="{198 + index * 17}">{label}</text>')
    elements.append(f"""    <text x="31" y="331">GitHub calendar through {max(dates):%d %b %Y}</text>
    <text x="1004" y="331" text-anchor="end">LESS  ←  ACTIVITY  →  MORE</text>
  </g>
  <g clip-path="url(#grid)">
    <g class="sweep" opacity="0">
      <rect x="67" y="187" width="20" height="117" fill="#DFFF70" opacity=".28"/>
      <path d="M85 187V304" stroke="#DFFF70" stroke-width="2"/>
    </g>
  </g>
</svg>""")
    return "\n".join(elements) + "\n"


if __name__ == "__main__":
    profile = fetch_profile(os.environ["GITHUB_REPOSITORY_OWNER"], os.environ["GITHUB_TOKEN"])
    svg = render(profile)
    output = Path("assets/telemetry.svg")
    output.write_text(svg, encoding="utf-8")
    print(f"Wrote {output} from GitHub's contribution calendar")
