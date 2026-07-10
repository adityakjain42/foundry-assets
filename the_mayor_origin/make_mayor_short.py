from __future__ import annotations

import math
import subprocess
import textwrap
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE = Path(__file__).resolve().parent
IMAGES = BASE / "images"
CLIPS = BASE / "clips"
FINAL = BASE / "final"
WIDTH = 1080
HEIGHT = 1920
FPS = 24
FFMPEG = Path("/tmp/foundry_video_deps/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1")

SCENES = [
    {
        "id": 1,
        "duration": 8,
        "caption": "I learned power in a room where no one raised their voice.",
        "motion": (0.18, -0.10),
    },
    {
        "id": 2,
        "duration": 8,
        "caption": "The Empire did not fall from war. It fell from paperwork, hunger, and late ships.",
        "motion": (-0.12, 0.16),
    },
    {
        "id": 3,
        "duration": 8,
        "caption": "Traders bought the routes. Scholars priced the rumors. Intuits moved through the fold and left softer thoughts behind.",
        "motion": (0.10, 0.10),
    },
    {
        "id": 4,
        "duration": 7,
        "caption": "My first treason was only a theorem: a stipend for silence costs less than cavalry.",
        "motion": (-0.14, -0.08),
    },
    {
        "id": 5,
        "duration": 8,
        "caption": "Then the jump reports arrived. Ships missing. Voices returning wrong. The Palace called it safe.",
        "motion": (0.08, 0.18),
    },
    {
        "id": 6,
        "duration": 8,
        "caption": "So I made a scandal useful. Panic became policy. Policy became a ballot.",
        "motion": (-0.12, 0.10),
    },
    {
        "id": 7,
        "duration": 8,
        "caption": "I detest politics. Truly. But the people had already made up their minds.",
        "motion": (0.12, -0.12),
    },
    {
        "id": 8,
        "duration": 9,
        "caption": "Violence is the last refuge of the incompetent, Empress. The Era Frontier needs a hand on the ledger, not a fist on the throat. And I, though I detest power, am to be its Mayor.",
        "motion": (-0.10, -0.04),
    },
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/NewYork.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    if bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
            "/System/Library/Fonts/SFNS.ttf",
        ] + candidates
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


CAPTION_FONT = load_font(54)
SMALL_FONT = load_font(32, bold=True)


def fit_cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((math.ceil(src_w * scale), math.ceil(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def make_vignette() -> np.ndarray:
    y, x = np.ogrid[-1:1:HEIGHT * 1j, -1:1:WIDTH * 1j]
    dist = np.sqrt((x * 0.92) ** 2 + (y * 1.15) ** 2)
    mask = np.clip((dist - 0.25) / 0.95, 0, 1)
    alpha = (mask ** 1.9) * 0.34
    return alpha[..., None]


VIGNETTE = make_vignette()


def add_finish(frame: Image.Image, caption: str | None, scene_id: int) -> np.ndarray:
    arr = np.asarray(frame).astype(np.float32)
    arr = arr * (1 - VIGNETTE)

    # Very light grain keeps generated stills from feeling frozen after motion.
    rng = np.random.default_rng(scene_id * 1000 + int(arr[0, 0, 0]))
    grain = rng.normal(0, 2.0, arr.shape)
    arr = np.clip(arr + grain, 0, 255).astype(np.uint8)
    out = Image.fromarray(arr, "RGB")

    if caption:
        overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        lines = wrap_text(draw, caption, CAPTION_FONT, WIDTH - 160)
        line_h = 66
        box_h = 92 + line_h * len(lines)
        y0 = HEIGHT - box_h - 95
        for y in range(y0, HEIGHT):
            opacity = int(205 * min(1, max(0, (y - y0) / 150)))
            draw.line((0, y, WIDTH, y), fill=(6, 5, 10, opacity))
        draw.text((78, y0 + 24), "THE FIRST MAYOR", font=SMALL_FONT, fill=(224, 188, 109, 235))
        y = y0 + 74
        for line in lines:
            draw.text((80, y), line, font=CAPTION_FONT, fill=(0, 0, 0, 185), stroke_width=4, stroke_fill=(0, 0, 0, 185))
            draw.text((80, y), line, font=CAPTION_FONT, fill=(246, 242, 230, 255))
            y += line_h
        out = Image.alpha_composite(out.convert("RGBA"), overlay).convert("RGB")
    return np.asarray(out)


def render_scene(scene: dict, captioned: bool) -> Path:
    scene_id = scene["id"]
    source = IMAGES / f"scene_{scene_id:02d}_source.png"
    normalized = IMAGES / f"scene_{scene_id:02d}_1080x1920.png"
    img = Image.open(source).convert("RGB")
    base = fit_cover(img, (WIDTH, HEIGHT))
    if not normalized.exists():
        base.save(normalized, quality=96)

    suffix = "captioned" if captioned else "clean"
    out_path = CLIPS / f"scene_{scene_id:02d}_{suffix}.mp4"
    frame_count = int(scene["duration"] * FPS)
    dx, dy = scene["motion"]
    caption = scene["caption"] if captioned else None

    writer = imageio.get_writer(
        out_path,
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-preset", "medium", "-crf", "18"],
    )
    try:
        for i in range(frame_count):
            t = i / max(1, frame_count - 1)
            ease = t * t * (3 - 2 * t)
            zoom = 1.055 + 0.055 * ease
            sw = int(WIDTH * zoom)
            sh = int(HEIGHT * zoom)
            scaled = base.resize((sw, sh), Image.Resampling.LANCZOS)
            max_x = sw - WIDTH
            max_y = sh - HEIGHT
            cx = max_x / 2 + dx * max_x * (ease - 0.5)
            cy = max_y / 2 + dy * max_y * (ease - 0.5)
            crop = scaled.crop((int(cx), int(cy), int(cx) + WIDTH, int(cy) + HEIGHT))
            # A subtle sharpen after zooming preserves the painted detail.
            crop = crop.filter(ImageFilter.UnsharpMask(radius=0.55, percent=60, threshold=4))
            writer.append_data(add_finish(crop, caption, scene_id))
    finally:
        writer.close()
    return out_path


def timestamp(seconds: float, srt: bool = False) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    sep = "," if srt else "."
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def write_script_files() -> None:
    lines = [scene["caption"] for scene in SCENES]
    (BASE / "voiceover_script.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cursor = 0.0
    srt_blocks = []
    for idx, scene in enumerate(SCENES, 1):
        start = cursor
        end = cursor + scene["duration"]
        srt_blocks.append(f"{idx}\n{timestamp(start, True)} --> {timestamp(end, True)}\n{textwrap.fill(scene['caption'], 44)}")
        cursor = end
    (FINAL / "the_mayor_origin_captions.srt").write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")


def concat(kind: str, paths: list[Path]) -> Path:
    list_path = CLIPS / f"concat_{kind}.txt"
    list_path.write_text("".join(f"file '{p.resolve()}'\n" for p in paths), encoding="utf-8")
    out = FINAL / f"the_mayor_origin_{kind}.mp4"
    subprocess.run(
        [
            str(FFMPEG),
            "-hide_banner",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(out),
        ],
        check=True,
    )
    return out


def main() -> None:
    for path in (IMAGES, CLIPS, FINAL):
        path.mkdir(parents=True, exist_ok=True)

    write_script_files()

    for captioned in (False, True):
        paths = []
        for scene in SCENES:
            paths.append(render_scene(scene, captioned=captioned))
        kind = "captioned" if captioned else "clean"
        final = concat(kind, paths)
        print(final)


if __name__ == "__main__":
    main()
