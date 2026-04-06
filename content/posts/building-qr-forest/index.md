---
title: "Building QR Forest — Hiding QR Codes Inside 3D Pixel Art Forests"
date: 2026-04-06T00:00:00+07:00
draft: false
images: ["og-image.png"]
---

## TL;DR

I built a web app that generates **scannable QR codes disguised as pixel art forests**. The trick: looking straight down through the tree canopy, the gaps between leaves form a valid QR pattern. Switch to 3D and it becomes a tiny voxel garden with trees, flowers, and seasonal particles. Built with Next.js 16, Three.js (React Three Fiber), and a lot of BoxGeometry.

**Try it:** [qr-forest.dinhnn.com](https://qr-forest.dinhnn.com)

---

## The Idea

It started with a 3D render I saw on Threads — someone had made a scene where you could switch the camera from a flat QR code view to a beautiful 3D garden. The transition was mesmerizing. I wanted to build that.

My first instinct was simple: put a single tree in the center and shape its canopy to form the QR pattern. I quickly realized this wouldn't work. A single tree canopy is one continuous blob — you can't carve reliable dark/light module boundaries into it. The QR would be unscannable.

Then I remembered something about real forests: **crown shyness**. It's a phenomenon where tree canopies naturally avoid touching each other, leaving distinct gaps between them. Seen from above, a forest with crown shyness looks like a puzzle — dark leaf clusters separated by bright channels of light.

That was the breakthrough. Not one tree — a *forest*. Each tree's canopy covers one or more QR modules. The crown shyness gaps between them create the light modules. The separation is built into the biology.

The concept clicked: render a pixel art forest where canopy coverage maps directly to QR modules. Dark modules = dense leaf clusters. Light modules = natural gaps showing the ground. From above, your phone scans it as a normal QR code. Rotate the camera and it's a 3D forest garden.

### "Dad, are you making Minecraft?"

While I was deep in the zone tweaking canopy layers, my son walked up, stared at the screen for a few seconds, and dropped that line. Fair point — it's all boxes. The voxel aesthetic is already there. I might actually try a Minecraft-style version next — full block world, dig into the terrain to reveal QR patterns, maybe even place torches that light up the modules.

---

## Phase 1: QR Foundation

### Matrix generation

The first thing I needed was a raw QR matrix — a 2D boolean array where `true` = dark module, `false` = light module. The `qrcode` npm package does the heavy lifting, but I needed the raw matrix, not a rendered image.

```typescript
// Error correction H = 30% damage tolerance
// Critical because artistic leaf placement will degrade the pattern
QRCode.create(data, { errorCorrectionLevel: "H" })
```

Level H is essential. The canopy rendering introduces slight variations in leaf cluster positioning, and H-level correction tolerates up to 30% module damage. Lower levels would make the QR unscannable after the artistic treatment.

### Module classification

Not all QR modules are equal. A QR code has three structural regions:

- **Finder patterns** (7x7 squares at three corners) — these are what scanners lock onto first
- **Timing patterns** (alternating modules along row and column 6) — help scanners determine module size
- **Data modules** (everything else) — the actual encoded payload

I classified each module so the canopy renderer could treat them differently. Finder patterns get taller, denser leaf domes. Timing patterns get thin connector strips. Data modules get the full range of artistic variation.

### Scanability validation

The scariest part: would the rendered canopy actually scan?

I integrated `jsQR` as a client-side validator. After the Three.js canvas renders, a quick capture-and-scan confirms the QR is readable. If not, the system could adjust contrast. In practice, with H-level error correction, it almost always works on the first pass.

---

## Phase 2: The 3D Scene

This is where things got fun. The scene is built in layers, bottom to top.

### Ground layer

A plane with a procedurally generated pixel art texture. I draw a 16x16 checkerboard pattern on a canvas element, apply `NearestFilter` (no smoothing — pixel art demands hard edges), and tile it across the ground.

Five grass styles change the palette: lush green, dry tan, snowy white, sandy beige, dark moss. Each season has its own ground feel.

### Garden layer

The mid-level decoration: a hero tree at the center, scattered flowers, bushes along the edges, and paths radiating outward. The hero tree is the scene's focal point in 3D — a large voxel tree built entirely from `BoxGeometry`.

I built five tree variants:

| Tree | Character |
|------|-----------|
| **Oak** | Thick canopy, 6 crown tiers, wide spread |
| **Pine** | Tall and narrow, 8 pyramidal tiers |
| **Cherry** | Curved trunk, pink-tinted crown |
| **Bamboo** | 7 parallel stalks with leaf tufts |
| **Dead** | Gnarled branches, sparse crown |

Every tree is 100% box geometry. No meshes, no imported models. The voxel constraint was intentional — it keeps the aesthetic consistent and means the entire scene is procedurally generated from config values.

### Canopy layer — the core trick

This is the layer that makes or breaks the concept. Each QR module maps to a position in the canopy grid. For dark modules, I stack 3-7 boxes vertically with slight random offsets to create organic-looking leaf clusters. For light modules: nothing. The gap *is* the encoding.

```
Dark module (true):        Light module (false):
  ┌─┐                       
  │█│ ← box layer 5         (empty — shows ground)
  ├─┤
  │█│ ← box layer 4
  ├─┤
  │█│ ← box layer 3
  └─┘
```

Finder patterns get special treatment — taller domes with more layers, ensuring they're visually distinct even in 3D. This helps scanners lock on.

Canopy density is configurable: dense (1.3x layers), normal (1.0x), sparse (0.7x). Sparse canopies look more ethereal but push closer to the scanability limit.

### Particle effects

Seasonal particles add life to the 3D view:

- **Spring:** Pink petals drifting slowly downward
- **Autumn:** Golden leaves with moderate tumble
- **Winter:** Snowflakes, very slow, dense
- **Night:** Yellow fireflies hovering
- **Rain:** Fast vertical blue streaks

All particles use `InstancedMesh` — one draw call per particle type regardless of count. Performance stays smooth even with 100 raindrops.

---

## Phase 3: The Camera System

The camera transition is what sells the concept. You need to seamlessly go from "this is a QR code" to "this is a garden" and back.

### Two-camera approach

I maintain two cameras simultaneously:

1. **OrthographicCamera** for QR view — positioned directly above, looking straight down. No perspective distortion. This is what makes the QR scannable.

2. **PerspectiveCamera** for 3D view — orbits at ~30 degrees elevation, FOV 50. Standard orbit controls with damping.

### The transition

When switching views, I animate the perspective camera between the two positions over 2 seconds with cubic easeout:

1. **QR → 3D:** Perspective camera starts at the orthographic position (directly above), then swoops down to orbit height while FOV widens from 14 to 50 degrees
2. **3D → QR:** Reverse — camera rises back to top-down while FOV narrows

The FOV animation is key. Starting with a very narrow FOV (14) at height approximates the orthographic view, making the transition feel continuous rather than jarring. At transition end, I swap to the actual orthographic camera for pixel-perfect QR scanning.

```
QR mode:        Transition:        3D mode:
  cam ●           cam               
  │                 ╲               cam ●╌╌╌╌╲
  │                  ╲                        ╲
  ▼                   ╲                        ▼
┌─────┐           ┌─────┐              ┌─────┐
│ QR  │           │     │              │     │
└─────┘           └─────┘              └─────┘
FOV: 14°                               FOV: 50°
```

---

## Phase 4: UI — From Sidebar to Studio Canvas

The first UI was a standard two-column layout: controls on the left, canvas on the right. It worked but felt cramped. The canvas — the whole point of the app — was fighting for space with dropdown menus.

### The redesign

I switched to a **full-screen canvas with floating controls**:

- **Logo** — top left, frosted glass pill
- **Export actions** — top right (PNG, SVG, Share)
- **Icon bar** — right center, vertical strip of icons
- **Floating panels** — slide out from the icon bar
- **View toggle** — bottom center, prominent segmented control

The view toggle got special attention. Switching to 3D is the "wow moment" — it needed to be obvious and inviting, not buried in a toolbar. A large segmented control with clear icons and a green active state does the job.

All floating UI uses `backdrop-filter: blur(16px)` with semi-transparent white backgrounds. The frosted glass effect lets the garden peek through while keeping controls readable.

### Visual pickers over dropdowns

Every dropdown was replaced with a visual picker:

- **Trees** → Thumbnail cards with colored backgrounds
- **Seasons** → Gradient swatches simulating sky colors
- **Flowers** → Color dot grid with ring selection
- **Grass/Density/Path** → Swatch rows in a 3-column panel

No dropdown communicates "cherry tree with pink blossoms" as well as a thumbnail showing it.

---

## Phase 5: Export and Sharing

### PNG capture

The canvas is full-viewport, but users want just the QR content. I crop to the center 65% of the canvas — enough to capture the garden without the surrounding empty space.

```typescript
const cropSize = Math.round(Math.min(canvas.width, canvas.height) * 0.65)
const offsetX = Math.round((canvas.width - cropSize) / 2)
const offsetY = Math.round((canvas.height - cropSize) / 2)
// Draw cropped region to temp canvas, export as PNG
```

### SVG export

For print-quality output, I generate an SVG directly from the QR matrix — no canvas involved. Each dark module becomes a `<rect>`, with a quiet zone border. Scales to any size without artifacts.

### Share links

Users can share their garden via a short link. The config is POSTed to a Next.js API route, stored in Cloudflare D1 (SQLite on the edge), and a 10-character `nanoid` becomes the URL slug. The viewer page server-renders the garden config, so shared links load instantly.

---

## What I Learned

**Error correction is your creative budget.** QR level H gives you 30% wiggle room. That's enough for artistic leaf placement but not for dramatic canopy gaps. Every visual choice is a negotiation with scanability.

**Voxel constraints simplify everything.** By committing to BoxGeometry-only, I avoided 3D modeling, UV mapping, and asset pipelines entirely. The entire scene generates from seven config values. The constraint became a feature.

**Camera transitions need FOV animation.** Position-only animation between orthographic and perspective views creates a jarring "pop." Animating FOV simultaneously creates the illusion of continuous motion. The narrow-FOV-at-height trick to approximate orthographic projection was the key insight.

**Full-screen canvas changes the UI equation.** When the canvas is the entire viewport, every control competes with it. Floating controls with glass morphism was the right call — present when needed, transparent when not.

---

## Stack Summary

| Concern | Choice | Why |
|---------|--------|-----|
| Framework | Next.js 16 | App Router + API routes + SSR for viewer |
| 3D | Three.js via R3F | Declarative scene graph in React |
| QR | qrcode + jsQR | Generate matrix + validate scanability |
| Style | Tailwind CSS 4 | Utility classes + CSS custom properties |
| DB | Cloudflare D1 | SQLite on the edge, zero-config |
| Hosting | Cloudflare Workers | Edge-deployed, global |
| Font | Fraunces + DM Sans | Serif display + clean sans body |

The whole thing is ~30 commits from scaffold to ship, deployed on Cloudflare Workers with D1 for persistence. No external 3D models, no image assets, no build-time generation. Every pixel is computed at runtime from a 7-field config object.

Sometimes the best rendering pipeline is just a lot of boxes.

---

