"""Emby brand asset generation via OpenAI gpt-image-1-mini.

Phase A: logo mark + mascot hero.
Phase B: mascot poses, generated with the hero as a visual reference (images.edit)
         so the character stays consistent.
Phase C: 3D feature icons.

Usage:  OPENAI_API_KEY=... python scripts/gen_brand.py [a|b|c|all]
"""
import base64
import os
import sys
import pathlib
import concurrent.futures as cf

from openai import OpenAI

ROOT = pathlib.Path(__file__).resolve().parent.parent
BRAND = ROOT / "public" / "brand"
MASCOT = BRAND / "mascot"
ICONS = BRAND / "icons"
for _p in (BRAND, MASCOT, ICONS):
    _p.mkdir(parents=True, exist_ok=True)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=300.0)
MODEL = "gpt-image-1-mini"

# ---------------------------------------------------------------- style anchors
# Emby palette: indigo-violet #6D4AFF primary, axolotl coral #FF7E9D accent,
# emerald #2BD9A4 mastery, amber #FFBF4D review, ink #16162B.
CHAR = (
    "Axo, the Emby mascot: a friendly cartoon axolotl doctor. Soft rounded body in warm "
    "blush-coral pink (#FFB3C4) with a slightly deeper coral belly, six feathery external "
    "gill fronds fanning from the sides of the head in vivid coral pink (#FF7E9D), a wide "
    "gentle closed-mouth smile, big glossy dark eyes each with a single bright highlight, "
    "tiny four-fingered hands. Wears a crisp white medical coat with rounded lapels and "
    "indigo-violet (#6D4AFF) trim, and an indigo-violet stethoscope around the neck."
)
STYLE = (
    "Style: premium 3D character render, soft matte clay and vinyl-toy finish, smooth "
    "rounded geometry, no hard edges. Soft studio three-point lighting from the upper left, "
    "gentle ambient occlusion, subtle soft contact shadow. Clean, cute, modern, high-end "
    "app-mascot quality, like a polished mobile game character. Not a flat sticker and not "
    "photorealistic. Fully centered, the entire character inside the frame with a small "
    "margin. Completely transparent background. No text, no letters, no words, no watermark, "
    "no ground plane."
)

PHASE_A = {
    "logo-mark.png": (
        "A modern app logo mark for a medical study platform called Emby. "
        "A single bold geometric symbol: a rounded-square badge with a soft indigo-violet "
        "(#6D4AFF) to deep violet (#4A2FD9) gradient, and centered inside it a negative-space "
        "letter E whose three horizontal strokes morph into an ECG heartbeat pulse line that "
        "spikes sharply through the middle stroke. The pulse line glows in coral pink "
        "(#FF7E9D). Style: premium 3D render, soft matte clay finish, gently beveled rounded "
        "edges, soft studio lighting, subtle inner glow. Extremely clean and legible at small "
        "sizes. Perfectly centered, square composition, transparent background. No text, no "
        "letters other than the single stylised E, no watermark."
    ),
    "mascot/axo-hero.png": (
        f"{CHAR} Pose: standing upright facing the viewer at a friendly three-quarter angle, "
        f"one hand raised in a warm welcoming wave, the other resting at the side, cheerful "
        f"and confident. Full body visible from head to feet. {STYLE}"
    ),
}

# Phase B: (filename, pose instruction) rendered as edits of the hero for consistency.
PHASE_B = [
    ("axo-thinking.png", "thinking hard: floating upright, one hand raised to the chin, eyes looking up and to the side, curious and pondering. Three small soft indigo-violet dots orbit above the head suggesting thought."),
    ("axo-celebrate.png", "celebrating a win: both arms thrown up high in triumph, eyes happily closed in curved arcs, big open joyful smile, body leaning back slightly, gills flaring upward with excitement."),
    ("axo-sleeping.png", "fast asleep: curled up comfortably on its side into a soft ball, eyes closed as gentle curves, peaceful smile, tail wrapped around the body, one small soft coral letter Z floating above the head."),
    ("axo-teaching.png", "teaching: standing and turned slightly to the side, holding a slim indigo-violet pointer stick angled up and to the right as if presenting to a board, other hand on hip, encouraging confident expression."),
    ("axo-magnifier.png", "investigating: holding a large magnifying glass with an indigo-violet handle up in front of one eye, that eye comically enlarged through the glass lens, leaning forward, focused and curious."),
    ("axo-microscope.png", "at work: leaning forward over a small indigo-violet and white laboratory microscope, both hands on the microscope, one eye pressed to the eyepiece, absorbed in concentration."),
    ("axo-clipboard.png", "taking notes: holding a white clipboard with an indigo-violet clip in one arm against the chest and a coral pink pen in the other hand, poised mid-note, attentive and organised."),
    ("axo-oops.png", "sheepish mistake: shoulders hunched, one hand rubbing the back of the head, an awkward apologetic half-smile, eyes glancing away, a single small blue sweat drop near the temple."),
    ("axo-trophy.png", "victorious: hoisting a shiny golden trophy cup overhead with both hands, beaming proudly, body squared to the viewer, gills fanned wide."),
    ("axo-books.png", "studying: carrying a neat stack of three closed books coloured indigo-violet, coral pink and emerald green, balanced in both arms in front of the chest, peeking cheerfully over the top of the stack."),
    ("axo-flashcards.png", "revising: holding a fanned spread of four blank white flashcards in one hand like playing cards, the other hand tapping one card thoughtfully, bright engaged expression."),
    ("axo-rocket.png", "blasting off: riding a small stylised coral pink and white rocket, gripping the nose cone, body streaming back, a soft indigo-violet flame plume trailing below, exhilarated open-mouthed grin."),
    ("axo-peek.png", "peeking: only the head, gills, and two small hands visible, gripping the top edge of an invisible ledge and peering upward over it with wide curious eyes, the rest of the body hidden below the crop."),
    ("axo-timer.png", "racing the clock: leaning forward in a hurry, hugging a large round white stopwatch with a coral pink rim against the chest, wide urgent eyes, gills swept back with motion."),
    ("axo-heart.png", "caring: standing gently, cradling a soft glossy coral pink stylised heart in both hands close to the chest, eyes warm and half-closed, tender reassuring smile."),
    ("axo-empty.png", "nothing here yet: standing beside an empty open cardboard-style box tipped slightly toward the viewer, one hand gesturing at it, shoulders shrugged, a friendly nothing-here-yet expression."),
]

ICON_STYLE = (
    "Style: premium 3D icon, soft matte clay and vinyl finish, smooth rounded geometry, "
    "chunky friendly proportions, soft studio lighting from the upper left, gentle ambient "
    "occlusion and a soft contact shadow. Palette strictly limited to indigo-violet "
    "(#6D4AFF), deep violet (#4A2FD9), coral pink (#FF7E9D), emerald (#2BD9A4), amber "
    "(#FFBF4D) and white. Single object, perfectly centered, square composition, generous "
    "even margin, transparent background. No text, no letters, no numbers, no watermark, "
    "no background plane."
)
PHASE_C = [
    ("dashboard.png", "a 3D rounded dashboard panel: a floating indigo-violet rounded-square card with two smaller white tiles and a small coral bar chart resting on its face"),
    ("read.png", "a 3D open book lying open with softly curved indigo-violet pages and a coral pink ribbon bookmark trailing from the spine"),
    ("quiz.png", "a 3D rounded checklist card in white with an indigo-violet border, bearing one large emerald green checkmark and two smaller grey list lines"),
    ("flashcards.png", "a 3D fanned stack of three rounded flashcards, the front one white, the ones behind indigo-violet and coral pink, slightly rotated"),
    ("steeplechase.png", "a 3D map location pin in coral pink standing upright on a small indigo-violet rounded disc, with a subtle white circular target ring on the disc"),
    ("histology.png", "a 3D laboratory microscope in white and indigo-violet with a coral pink eyepiece, chunky rounded toy-like proportions"),
    ("battle.png", "two 3D rounded lightning bolts, one indigo-violet and one coral pink, crossed in an X against each other"),
    ("analytics.png", "a 3D bar chart of three rounded columns of ascending height in indigo-violet, coral pink and emerald, with a small emerald arrow curving upward above them"),
    ("planner.png", "a 3D rounded wall calendar in white with an indigo-violet header bar, one date square highlighted in coral pink, and a small emerald checkmark"),
    ("premium.png", "a 3D rounded crown with three soft points in warm amber gold, set with one small coral pink gem in the centre band"),
    ("streak.png", "a 3D rounded flame with a coral pink outer body and a warm amber inner core, soft and friendly rather than sharp"),
    ("xp.png", "a 3D faceted gemstone in indigo-violet with a bright white highlight facet, floating and gently glowing"),
    ("credits.png", "a 3D rounded coin standing on edge, indigo-violet rim with a coral pink face, a small white four-pointed spark shape embossed on the face"),
    ("notification.png", "a 3D rounded bell in amber gold with a white clapper and a small coral pink dot badge at the upper right"),
    ("upload.png", "a 3D rounded cloud in white with a thick indigo-violet upward arrow rising out of the top of it"),
    ("community.png", "three 3D rounded people figures standing together, coloured indigo-violet, coral pink and emerald, the middle one slightly taller and forward"),
    ("brain.png", "a 3D soft rounded brain in coral pink with gentle smooth folds, one hemisphere subtly tinted indigo-violet"),
    ("target.png", "a 3D concentric target with an indigo-violet outer ring, white middle ring and coral pink bullseye, with a small emerald dart stuck in the centre"),
    ("resource.png", "a 3D stack of two rounded document pages in white with indigo-violet text lines, the top page lifting and curling at one corner"),
    ("profile.png", "a 3D rounded user avatar badge: a white circular head and shoulders silhouette inside an indigo-violet rounded-square frame"),
]


def save(path: pathlib.Path, b64: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(b64))
    print(f"  wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)", flush=True)


def gen(name: str, prompt: str, out_root: pathlib.Path = BRAND, quality: str = "medium"):
    try:
        r = client.images.generate(
            model=MODEL, prompt=prompt, size="1024x1024",
            quality=quality, background="transparent", output_format="png", n=1,
        )
        save(out_root / name, r.data[0].b64_json)
        return name, True
    except Exception as e:  # noqa: BLE001
        print(f"  FAILED {name}: {e}", flush=True)
        return name, False


def edit_from_hero(name: str, pose: str):
    """Generate a pose using the hero render as a character reference."""
    prompt = (
        "Redraw the exact same axolotl doctor character shown in the reference image, with "
        "identical body shape, identical blush-coral colour, identical coral gill fronds, "
        "identical white medical coat with indigo-violet trim and indigo-violet stethoscope, "
        "and an identical face, but in a completely new pose.\n\n"
        f"New pose: {pose}\n\n{STYLE}"
    )
    try:
        with open(MASCOT / "axo-hero.png", "rb") as f:
            r = client.images.edit(
                model=MODEL, image=[f], prompt=prompt, size="1024x1024",
                quality="medium", background="transparent",
                n=1,
            )
        save(MASCOT / name, r.data[0].b64_json)
        return name, True
    except Exception as e:  # noqa: BLE001
        print(f"  FAILED {name}: {e}", flush=True)
        return name, False


def run(fn, items, workers=5):
    ok, bad = [], []
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for name, good in ex.map(lambda a: fn(*a), items):
            (ok if good else bad).append(name)
    print(f"  -> {len(ok)} ok, {len(bad)} failed {bad}", flush=True)
    return bad


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    if phase in ("all", "a"):
        print("PHASE A: logo + mascot hero", flush=True)
        run(gen, list(PHASE_A.items()), workers=2)
    if phase in ("all", "b"):
        print("PHASE B: mascot poses (hero-referenced)", flush=True)
        run(edit_from_hero, PHASE_B, workers=4)
    if phase in ("all", "c"):
        print("PHASE C: 3D icons", flush=True)
        run(lambda n, p: gen(n, f"{p}. {ICON_STYLE}", ICONS), PHASE_C, workers=5)
    print("DONE", flush=True)
