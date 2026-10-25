"""Render the LinkedIn images and the Part 2 carousel into portfolio/linkedin/ from existing portfolio assets.

Run from the repo root:  make linkedin      (or ./venv/bin/python scripts/make_linkedin_assets.py)

Sources are the figures and dashboard screenshots already in portfolio/images/ (this script never captures new
screenshots). Every number drawn here is read from a report, CSV, workflow or doc file, so the images cannot drift
from the README. Palette and fonts are the dashboard's (imported from make_portfolio_figures.py; Geist and
Instrument Serif from scripts/fonts/).

Output:
  project media (1200x1200)  01_dashboard_overview.png, 02_architecture.png, 03_baselines_by_horizon.png,
                             04_train_serve_skew.png, 05_model_health.png
  carousel (1080x1350)       carousel_part2.pdf and carousel_part2_01.png .. carousel_part2_06.png
"""

import re
from functools import cache
from pathlib import Path

import pandas as pd
from fontTools.ttLib import TTFont
from make_portfolio_figures import (
    BASELINE,
    HIGHLIGHT,
    INK,
    LINE,
    MODEL,
    MUTED,
    PAGE,
    SURFACE,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
IMAGES = REPO_ROOT / "portfolio" / "images"
OUT_DIR = REPO_ROOT / "portfolio" / "linkedin"
REPORTS = REPO_ROOT / "reports"
FONTS = REPO_ROOT / "scripts" / "fonts"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

SS = 2  # supersampling: draw at 2x, downscale once at the end

# The dashboard screenshots are full-page captures; these are the y (px, source scale) where a card row ends,
# so the crop keeps whole cards and stays legible at LinkedIn sizes.
OVERVIEW_CROP_BOTTOM = 1372  # through "Stations now" / "Forecast by station"
MODEL_HEALTH_CROP_BOTTOM = 1005  # through the six model cards and the source-lag row

FONT_FILES = {
    "sans": "Geist-Regular.ttf",
    "medium": "Geist-Medium.ttf",
    "semibold": "Geist-SemiBold.ttf",
    "serif": "InstrumentSerif-Regular.ttf",
}
FALLBACK = "sans"  # Instrument Serif has no arrow or superscript two


# --------------------------------------------------------------------------------------- numbers from the repo


def sgn(x: float, nd: int = 2) -> str:
    return f"{x:+.{nd}f}".replace("-", "−")


def cron_parts(workflow: str) -> tuple[int, str]:
    cron = re.search(r'cron:\s*"([^"]+)"', (WORKFLOWS / workflow).read_text()).group(1)
    minute, hour = cron.split()[:2]
    return int(minute), hour


def load_numbers() -> dict:
    live = pd.read_csv(REPORTS / "modeling" / "live_retrain" / "live_retrain_metrics.csv")
    live = live[live.split == "test"]
    frozen = live[live.model.str.contains("frozen")].set_index("horizon").skill_mae
    retrain = live[(~live.model.str.contains("frozen")) & (live.inputs == "live-masked")].set_index("horizon").skill_mae

    wu = pd.read_csv(REPORTS / "modeling" / "live_retrain" / "window_update_baseline.csv")
    wu = wu[wu.split == "test"].set_index("horizon")

    replay = pd.read_csv(next((REPORTS / "live").glob("replay_*.csv")))
    replay_aqi6 = replay[(replay.target == "aqi") & (replay.horizon == 6)].iloc[0]

    # R2 of 1h persistence as printed in the headline table (the CSV rounds before the README does).
    rows = [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in (REPORTS / "metrics" / "headline_metrics.md").read_text().splitlines()
        if line.startswith("|")
    ]
    r2_col = next(i for i, c in enumerate(rows[0]) if c in ("R\u00b2", "R2"))
    persistence_r2 = next(r[r2_col] for r in rows if r[0] == "1h" and "persistence" in r[1].lower())

    old_r2 = re.search(
        r"1h RMSE [\d.]+ / R² (0\.\d+)", (REPO_ROOT / "docs" / "history" / "IMPROVEMENT_PLAN.md").read_text()
    ).group(1)

    ingest_min, _ = cron_parts("ingest.yml")
    forecast_min, _ = cron_parts("forecast.yml")
    score_min, score_hour = cron_parts("score.yml")

    name = re.search(r"Copyright \(c\) \d{4} (.+)", (REPO_ROOT / "LICENSE").read_text()).group(1).strip()

    return {
        "frozen": frozen,
        "retrain": retrain,
        "wu": wu,
        "replay_days": int(replay_aqi6.days),
        "replay_skill6": float(replay_aqi6.skill_vs_persistence),
        "persistence_r2": persistence_r2,
        "old_r2": old_r2,
        "ingest": f":{ingest_min:02d}",
        "forecast": f":{forecast_min:02d}",
        "score": f"{int(score_hour):02d}:{score_min:02d} UTC",
        "author": name,
    }


# ------------------------------------------------------------------------------------------------- drawing


@cache
def font(family: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / FONT_FILES[family]), round(size * SS))


@cache
def glyphs(family: str) -> frozenset[int]:
    return frozenset(TTFont(FONTS / FONT_FILES[family]).getBestCmap())


def runs(text: str, family: str) -> list[tuple[str, str]]:
    """Split text into (font family, run) pieces, switching to the fallback for glyphs the font lacks."""
    out: list[tuple[str, str]] = []
    have = glyphs(family)
    for ch in text:
        fam = family if ord(ch) in have or ch == " " else FALLBACK
        if out and out[-1][0] == fam:
            out[-1] = (fam, out[-1][1] + ch)
        else:
            out.append((fam, ch))
    return out


def text_width(text: str, family: str, size: int) -> float:
    return sum(font(f, size).getlength(t) for f, t in runs(text, family)) / SS


def wrap(text: str, family: str, size: int, max_w: float) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split(" "):  # plain spaces only, so a no-break space keeps words together
        trial = f"{cur} {word}".strip()
        if cur and text_width(trial, family, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return [*lines, cur]


def fit_size(text: str, family: str, max_size: int, min_size: int, max_w: float) -> int:
    for size in range(max_size, min_size - 1, -1):
        if text_width(text, family, size) <= max_w:
            return size
    raise ValueError(f"{text!r} does not fit in {max_w}px at {min_size}px")


class Canvas:
    def __init__(self, w: int, h: int, bg: str):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * SS, h * SS), bg)
        self.d = ImageDraw.Draw(self.img)

    def text(self, x, baseline, text, family, size, fill, anchor="l"):
        width = text_width(text, family, size)
        x = x - width / 2 if anchor == "c" else x - width if anchor == "r" else x
        for fam, run in runs(text, family):
            f = font(fam, size)
            self.d.text((x * SS, baseline * SS), run, font=f, fill=fill, anchor="ls")
            x += f.getlength(run) / SS

    def paragraph(self, x, baseline, text, family, size, fill, max_w, leading, anchor="l") -> float:
        """Draw wrapped text; returns the baseline of the last line."""
        for line in wrap(text, family, size, max_w):
            self.text(x, baseline, line, family, size, fill, anchor)
            baseline += leading
        return baseline - leading

    def rect(self, box, fill=None, outline=None, width=1, radius=0):
        x0, y0, x1, y1 = (v * SS for v in box)
        self.d.rounded_rectangle((x0, y0, x1, y1), radius=radius * SS, fill=fill, outline=outline, width=width * SS)

    def ellipse(self, cx, cy, r, fill):
        self.d.ellipse(((cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS), fill=fill)

    def shadow(self, box, radius, blur=14, dy=6, alpha=34):
        x0, y0, x1, y1 = box
        mask = Image.new("L", self.img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (x0 * SS, (y0 + dy) * SS, x1 * SS, (y1 + dy) * SS), radius=radius * SS, fill=alpha
        )
        mask = mask.filter(ImageFilter.GaussianBlur(blur * SS))
        self.img.paste(Image.new("RGB", self.img.size, INK), mask=mask)

    def place(self, path: Path, box, crop_bottom: int | None = None, radius: int = 14, framed: bool = True):
        """Fit the image inside box (never stretched), centred; returns the placed (x0, y0, x1, y1)."""
        src = Image.open(path).convert("RGB")
        if crop_bottom:
            src = src.crop((0, 0, src.width, crop_bottom))
        bx0, by0, bx1, by1 = box
        scale = min((bx1 - bx0) / src.width, (by1 - by0) / src.height)
        w, h = round(src.width * scale), round(src.height * scale)
        x0, y0 = bx0 + ((bx1 - bx0) - w) / 2, by0 + ((by1 - by0) - h) / 2
        placed = (x0, y0, x0 + w, y0 + h)
        if framed:
            self.shadow(placed, radius)
        scaled = src.resize((w * SS, h * SS), Image.LANCZOS)
        mask = Image.new("L", scaled.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *scaled.size), radius=radius * SS, fill=255)
        self.img.paste(scaled, (round(x0 * SS), round(y0 * SS)), mask)
        if framed:
            self.rect(placed, outline=LINE, width=1, radius=radius)
        return placed

    def finish(self) -> Image.Image:
        return self.img.resize((self.w, self.h), Image.LANCZOS)


# ------------------------------------------------------------------------------------------ project media


def project_image(title: str, caption: str, asset: Path, crop_bottom: int | None = None) -> Image.Image:
    size, margin, title_band, caption_band = 1200, 60, 190, 110
    c = Canvas(size, size, PAGE)

    c.rect((0, 0, size, title_band), fill=SURFACE)
    c.rect((0, title_band - 1, size, title_band), fill=LINE)
    c.rect((margin, 52, margin + 70, 56), fill=HIGHLIGHT)
    t_size = fit_size(title, "serif", 66, 40, size - 2 * margin)
    c.text(margin, 140, title, "serif", t_size, INK)

    c.rect((0, size - caption_band, size, size), fill=SURFACE)
    c.rect((0, size - caption_band, size, size - caption_band + 1), fill=LINE)
    c_size = fit_size(caption, "sans", 30, 22, size - 2 * margin)
    c.text(margin, size - caption_band / 2 + c_size * 0.35, caption, "sans", c_size, MUTED)

    c.place(
        asset,
        (margin, title_band + 30, size - margin, size - caption_band - 30),
        crop_bottom=crop_bottom,
    )
    return c.finish()


def build_project_images(n: dict) -> dict[str, Image.Image]:
    wu, frozen, retrain = n["wu"], n["frozen"], n["retrain"]
    return {
        "01_dashboard_overview.png": project_image(
            "Live Delhi AQI forecast dashboard",
            f"Hourly Delhi forecasts; the 1h rule cuts AQI error {wu.loc['1h', 'wu_vs_persistence']:.0%} vs persistence.",
            IMAGES / "dashboard_overview_desktop.png",
            OVERVIEW_CROP_BOTTOM,
        ),
        "02_architecture.png": project_image(
            "From government sensors to a live forecast",
            f"Ingest at {n['ingest']}, forecast at {n['forecast']}, scoring nightly at {n['score']}, one database.",
            IMAGES / "10_architecture.png",
        ),
        "03_baselines_by_horizon.png": project_image(
            "A simple rule wins at 1h, ML wins at 6h",
            "Skill vs persistence: "
            f"1h rule {sgn(wu.loc['1h', 'wu_vs_persistence'])} vs model {sgn(wu.loc['1h', 'model_vs_persistence'])}; "
            f"6h {sgn(wu.loc['6h', 'wu_vs_persistence'])} vs {sgn(wu.loc['6h', 'model_vs_persistence'])}.",
            IMAGES / "61_baselines_by_horizon.png",
        ),
        "04_train_serve_skew.png": project_image(
            f"Fixing train/serve skew: 6h skill {sgn(frozen['6h'])} → {sgn(retrain['6h'])}",
            f"Frozen models lost to persistence on live inputs; 1h skill {sgn(frozen['1h'])} → {sgn(retrain['1h'])}.",
            IMAGES / "60_train_serve_skew.png",
        ),
        "05_model_health.png": project_image(
            "The system scores itself every night",
            f"Nightly scoring at {n['score']}; a {n['replay_days']}-day replay gave 6h AQI skill "
            f"{sgn(n['replay_skill6'])}.",
            IMAGES / "dashboard_model_health_desktop.png",
            MODEL_HEALTH_CROP_BOTTOM,
        ),
    }


# ----------------------------------------------------------------------------------------------- carousel

CW, CH, CM = 1080, 1350, 80  # page size and side margin
BODY = 40  # px; the brief asks for at least 36
N_PAGES = 6


def dots(c: Canvas, current: int, dark: bool = False) -> None:
    gap, y = 34, CH - 56
    x0 = CW / 2 - gap * (N_PAGES - 1) / 2
    for i in range(N_PAGES):
        on = i == current
        c.ellipse(x0 + gap * i, y, 8 if on else 6, HIGHLIGHT if on else (BASELINE if dark else LINE))


def page_cover(n: dict) -> Image.Image:
    c = Canvas(CW, CH, INK)
    c.rect((CM, 150, CM + 90, 156), fill=HIGHLIGHT)
    last = c.paragraph(
        CM, 330, "Part 2: I audited my own ML project, then took it live", "serif", 124, PAGE, CW - 2 * CM, 132
    )
    c.text(CM, CH - 250, n["author"], "semibold", 46, PAGE)
    c.text(CM, CH - 190, "Delhi Air Quality Forecasting", "sans", 40, BASELINE)
    assert last < CH - 330
    dots(c, 0, dark=True)
    return c.finish()


def page_changes(n: dict) -> Image.Image:
    c = Canvas(CW, CH, PAGE)
    c.rect((CM, 100, CM + 70, 104), fill=HIGHLIGHT)
    c.text(CM, 190, "Part 1 vs Part 2: what changed", "serif", 76, INK)

    rows = [
        (f"1h R² {n['old_r2']}", f"Reported vs persistence (R² {n['persistence_r2']})"),
        ("Threshold tuned on test", "Threshold chosen on validation"),
        ("Diwali “ban effect”", "Methods lesson"),
        ("Streamlit app", "Live system on Azure + Vercel"),
    ]
    pad, arrow_w = 32, 70
    inner = CW - 2 * CM - 2 * pad
    col_w = (inner - arrow_w) / 2
    lead = 56
    left_x, right_x = CM + pad, CM + pad + col_w + arrow_w

    c.text(left_x, 276, "PART 1", "semibold", 32, BASELINE)
    c.text(right_x, 276, "PART 2", "semibold", 32, MODEL)

    y = 310
    for before, after in rows:
        lb, la = wrap(before, "sans", BODY, col_w), wrap(after, "medium", BODY, col_w)
        h = max(len(lb), len(la)) * lead + 2 * 38
        c.shadow((CM, y, CW - CM, y + h), 16, blur=10, dy=4, alpha=22)
        c.rect((CM, y, CW - CM, y + h), fill=SURFACE, outline=LINE, radius=16)
        mid = y + h / 2
        # first baseline of a block of n lines, vertically centred on the row
        top_left, top_right = (mid - n * lead / 2 + lead * 0.74 for n in (len(lb), len(la)))

        c.paragraph(left_x, top_left, before, "sans", BODY, MUTED, col_w, lead)
        c.text(CM + pad + col_w + arrow_w / 2, mid + 14, "→", "semibold", 44, HIGHLIGHT, anchor="c")
        c.paragraph(right_x, top_right, after, "medium", BODY, INK, col_w, lead)
        y += h + 28
    assert y < CH - 130, y
    dots(c, 1)
    return c.finish()


def page_figure(index: int, headline: str, figure: Path, takeaway: str) -> Image.Image:
    c = Canvas(CW, CH, PAGE)
    c.rect((CM, 100, CM + 70, 104), fill=HIGHLIGHT)
    top = c.paragraph(CM, 190, headline, "serif", 78, INK, CW - 2 * CM, 84)

    # Takeaway sits above the dots; the figure is centred in the space between.
    lines = wrap(takeaway, "sans", BODY, CW - 2 * CM)
    lead = 52
    first = CH - 130 - lead * (len(lines) - 1)
    c.paragraph(CM, first, takeaway, "sans", BODY, MUTED, CW - 2 * CM, lead)

    space = (top + 40, first - BODY - 30)
    c.place(figure, (36, space[0], CW - 36, space[1]), radius=12)
    dots(c, index)
    return c.finish()


def page_dashboard() -> Image.Image:
    c = Canvas(CW, CH, PAGE)
    c.rect((CM, 100, CM + 70, 104), fill=HIGHLIGHT)
    c.text(CM, 190, "Live dashboard", "serif", 78, INK)
    placed = c.place(
        IMAGES / "dashboard_overview_desktop.png", (CM, 240, CW - CM, 1100), OVERVIEW_CROP_BOTTOM, radius=14
    )
    last = c.paragraph(CM, placed[3] + 104, "Code & live link in the comments", "serif", 76, INK, CW - 2 * CM, 84)
    assert last < CH - 110, last
    dots(c, 5)
    return c.finish()


def build_carousel(n: dict) -> list[Image.Image]:
    wu, frozen, retrain = n["wu"], n["frozen"], n["retrain"]
    return [
        page_cover(n),
        page_changes(n),
        page_figure(
            2,
            "From government sensors to a live forecast",
            IMAGES / "10_architecture.png",
            f"Ingest at {n['ingest']}, forecast at {n['forecast']}, scoring nightly at {n['score']}. "
            "One database; the API and dashboard only read.",
        ),
        page_figure(
            3,
            f"Fixing train/serve skew: 6h skill {sgn(frozen['6h'])} → {sgn(retrain['6h'])}",
            IMAGES / "60_train_serve_skew.png",
            f"Trained on official AQI, the frozen 6h model lost to persistence ({sgn(frozen['6h'])}). "
            f"Retrained on what the live feed can compute: {sgn(retrain['6h'])}.",
        ),
        page_figure(
            4,
            "A simple rule wins at 1h, ML wins at 6h",
            IMAGES / "61_baselines_by_horizon.png",
            f"1h: the rule cuts error {wu.loc['1h', 'wu_vs_persistence']:.0%} vs persistence, "
            f"the model {wu.loc['1h', 'model_vs_persistence']:.0%}. "
            f"6h: the model {wu.loc['6h', 'model_vs_persistence']:.0%}, the rule {wu.loc['6h', 'wu_vs_persistence']:.0%}.",
        ),
        page_dashboard(),
    ]


# ----------------------------------------------------------------------------------------------------- main


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    numbers = load_numbers()

    for name, img in build_project_images(numbers).items():
        img.save(OUT_DIR / name)
        print(f"wrote {(OUT_DIR / name).relative_to(REPO_ROOT)}")

    pages = build_carousel(numbers)
    for i, page in enumerate(pages, 1):
        path = OUT_DIR / f"carousel_part2_{i:02d}.png"
        page.save(path)
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    pdf = OUT_DIR / "carousel_part2.pdf"
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=72.0)
    print(f"wrote {pdf.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
