# Art Direction — What We Learn From the References

AI Animator is a general-purpose studio. These references set the **first quality
bar** (expressive horror / FNF-mod illustration), not the limits of the app.
Each project can load its own references and assign each one a role.

> **Originality rule.** Several references show existing characters or fan art of
> them (Pokémon-derived horror fan characters, FNF mod casts), and two are signed
> by their artists. We study *technique* (line, value, light, palette, texture).
> We do **not** reproduce those characters, their signature motifs (pendulum
> hypnotist creature, specific hats/outfits) or the artists' signatures. The
> files are kept in `style_references/` for study only and are git-ignored so
> they are never redistributed.

## Reference by reference

| # | What it is | What to learn |
|---|---|---|
| 1 | Painterly creature reaching toward the viewer | Strong **foreshortening** (the hand comes at the camera). **Cast shadow across half the face** gives menace. Hair drawn as **tapered clumps**, not single strands. Warm tan skin against cool grey mane. Lines are dark brown, not pure black. |
| 2 | Girl in night grass, glowing hand | **Motivated light source**: the glow in her hand lights her from below (classic horror under-lighting). **Huge dark negative space**. Foreground grass silhouettes frame the figure. VHS grain / soft blur makes it feel like found footage. A cheerful pose against a creepy mood is what makes it unsettling. |
| 3 | Same creature, spiral eye in the background | **Near-monochrome maroon palette**, heavy vignette, CRT scanlines. Graphic motif (spiral) used as composition, not decoration. |
| 4 | Sketchy portrait covered in red eyes | **Rough, confident linework** left visible. **Limited palette**: black, white, greys + one saturated red. A repeated motif (eyeballs) breaking out of the frame. Horizontal colour bands as a bold background. |
| 5 | Poster: girl with camera flash, monsters behind | **Depth staging**: one lit hero in front, threats layered behind in red rim light. The **camera flash is the focal point** (brightest value + lens flare). Clean cel shading with 2–3 tones plus soft gradients. Glowing red eyes in shadow. |
| 6 | Figure covering eyes with bloody hands | Painterly **warm red monochrome** on black. **Texture as storytelling** (grime and stains on the arms). Face hidden but eyes glowing through fingers — suggestion is scarier than showing. Hair dissolves into the background (lost edges). |
| 7 | Grayscale sketch, spiral eyes, drill curls | **Construction and sketch lines left in**, varied pressure. Big readable shapes (drill curls, oversized jacket) and a cute-but-off face (spiral pupils). Good model for our *rough sketch* stage. |
| 8 | Large FNF horror collage poster | **Thick, wobbly outlines**, saturated neon accents on black, **chromatic aberration and glitch blocks**, extreme mouths and teeth, many characters packed with clear overlaps. Pure FNF-mod energy: high contrast, high readability at small size. |
| 9 | Zombie kid, grayscale + blood red | **Grayscale with one accent colour** (blood). Ragged clothing edges, sunken black eye sockets, slumped posture. Transparent background — basically a **sprite-ready** pose. |

## The shared "rules" of this style family

1. **Value first.** Every piece reads in black-and-white. Lots of dark, one bright focal area.
2. **One accent colour.** Usually red/crimson against greys, blacks or desaturated warm tones.
3. **Motivated lighting.** Light comes from something in the scene (flash, glowing hand, screen), often from below.
4. **Lines with character.** Coloured or varied-weight lines, visible sketchiness where it adds energy, wobbly thick outlines for FNF.
5. **Uncanny faces.** Too-wide smiles, hidden or hollow eyes, glowing pupils, spirals — normal features pushed slightly wrong.
6. **Repetition as horror.** Many eyes, many teeth, many figures.
7. **Imperfection on purpose.** Grain, scanlines, glitch, smudges, stains, ragged edges. This is what keeps it from looking like generic AI art.
8. **Contrast of tone.** Cute/cheerful elements paired with dread.

These become a reusable **style profile** ("Expressive Horror") in Phase 3, alongside
other profiles the user can create from any references (anime, watercolor, pixel art, vector, …).

## Can we "train the AI" on these?

Honest answer, because it matters for the plan:

* **Claude is not trained by us.** It *reads* the references every time (vision) and
  writes precise art briefs and critiques from them. That already works in Phase 1:
  attach the images in Studio Chat and ask it to analyze them.
* **Image models can be fine-tuned** (a "LoRA") to learn a style. That is the real
  "training" option, in Phase 3, and it needs a GPU or a paid service.
* **Only train on art you have the rights to**: your own drawings, commissioned work, or
  art whose creators gave permission. Training a model on other artists' work (several of
  these references are signed) without permission is a real legal and ethical problem,
  and it would also make your results look like copies of them. The better route is to
  draw or commission ~20–40 pieces in this direction and train on those.
* Without training, we can still steer hard with **style references** (IP-Adapter /
  reference-guided generation), **structure guides** (pose/lineart ControlNet), and
  **post-processing passes** (grain, scanlines, chromatic aberration, limited palettes).
