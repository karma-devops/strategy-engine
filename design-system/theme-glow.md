# Theme Glow — Aura Spectrum Extension

**Authority:** This spec extends `MASTER.md` — does NOT override. Glow tokens resolve to MASTER.md semantic layer for base colors.

**Purpose:** Broadens MASTER palette with luminous aura effects for:
- Pulse graph path glow (equity curve)
- Status dot glow (engine running indicators)
- Position card halos (optional, subtle — HL doesn't have this, our enhancement)
- KPI border-top glow (focused state)
- Button/CTA hover glow (elevated states)

---

## 1. Glow Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Subtle, not neon** | Opacity 0.15–0.4, blur 8–24px |
| **Semantic, not decorative** | Profit/loss/surface map to MASTER tokens |
| **Performance-first** | CSS `filter: drop-shadow()` + `box-shadow`, not canvas/SVG filters |
| **Dark-mode optimized** | Glow visible on dark surfaces; light-mode reduces intensity 50% |
| **Motion-aware** | Glow pulse 2s rhythm (matches status-dot in MASTER) |

---

## 2. Token Architecture (3-Layer, extends MASTER)

### Layer 1: Primitive Glow Colors
```css
/* Resolve to MASTER.md base tokens */
--glow-profit-base: #34D399;     /* from --color-profit */
--glow-loss-base: #FB7185;       /* from --color-loss */
--glow-brand-base: #06D6A0;      /* from --color-brand */
--glow-surface-base: #15100B;    /* from --surface-card */
```

### Layer 2: Semantic Glow Tokens
```css
/* Opacity + blur applied */
--glow-profit-weak: rgba(52, 211, 153, 0.15);   /* 15% opacity, subtle */
--glow-profit-med: rgba(52, 211, 153, 0.3);     /* 30% opacity, standard */
--glow-profit-strong: rgba(52, 211, 153, 0.4);  /* 40% opacity, focused */

--glow-loss-weak: rgba(251, 113, 133, 0.15);
--glow-loss-med: rgba(251, 113, 133, 0.3);
--glow-loss-strong: rgba(251, 113, 133, 0.4);

--glow-brand-weak: rgba(6, 214, 160, 0.15);
--glow-brand-med: rgba(6, 214, 160, 0.3);
--glow-brand-strong: rgba(6, 214, 160, 0.4);
```

### Layer 3: Component Application Tokens
```css
/* Ready-to-use on components */
--glow-pulse-path: var(--glow-brand-med);      /* equity curve SVG path */
--glow-status-dot: var(--glow-brand-weak);     /* running engine dot */
--glow-pos-card-hover: var(--glow-profit-weak);/* position card hover halo */
--glow-kpi-focused: var(--glow-brand-med);     /* KPI border-top when focused */
--glow-cta-hover: var(--glow-brand-strong);    /* CTA button hover glow */
```

---

## 3. Glow Application Patterns

### 3.1 Pulse Graph Path Glow (SVG)
```css
#pulse-path {
  stroke: var(--color-brand);           /* solid teal line */
  stroke-width: 2;
  filter: drop-shadow(0 0 8px var(--glow-pulse-path));
  /* Optional: SVG duplicate-layer technique for stronger glow */
}

/* SVG duplicate-layer technique (stronger glow, more perf cost) */
#pulse-glow-layer {
  stroke: var(--glow-brand-med);
  stroke-width: 6;
  filter: blur(4px);
  opacity: 0.5;
}
```

### 3.2 Status Dot Glow (Engine Running Indicator)
```css
.status-dot.running {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-brand);
  box-shadow: 0 0 12px var(--glow-status-dot);
  animation: status-dot-pulse 2s ease-in-out infinite;
}

@keyframes status-dot-pulse {
  0%, 100% {
    opacity: 1;
    box-shadow: 0 0 12px var(--glow-status-dot);
  }
  50% {
    opacity: 0.7;
    box-shadow: 0 0 18px var(--glow-status-dot), 0 0 24px var(--glow-brand-weak);
  }
}
```

### 3.3 Position Card Hover Halo
```css
.pos-card {
  transition: box-shadow 0.2s ease;
}

.pos-card:hover {
  box-shadow: 0 0 16px var(--glow-pos-card-hover), inset 0 0 8px var(--glow-profit-weak);
}

.pos-card[data-side="short"]:hover {
  box-shadow: 0 0 16px var(--glow-loss-weak), inset 0 0 8px var(--glow-loss-weak);
}
```

### 3.4 KPI Border-Top Glow (Focused State)
```css
.kpi-card.focused {
  border-top: 3px solid var(--color-brand);
  box-shadow: 0 -4px 12px var(--glow-kpi-focused);
}
```

### 3.5 CTA Button Hover Glow
```css
.btn-cta {
  background: var(--color-brand);
  color: var(--surface-card);
  transition: all 0.2s ease;
}

.btn-cta:hover {
  background: var(--color-brand);
  box-shadow: 0 0 16px var(--glow-cta-hover);
  transform: translateY(-1px);
}
```

---

## 4. Responsive / Reduced Motion

### 4.1 Light Mode Adjustment
```css
@media (prefers-color-scheme: light) {
  :root {
    --glow-profit-weak: rgba(52, 211, 153, 0.08);   /* 50% reduction */
    --glow-profit-med: rgba(52, 211, 153, 0.15);
    --glow-profit-strong: rgba(52, 211, 153, 0.2);
    /* Repeat for loss/brand tokens */
  }
}
```

### 4.2 Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  .status-dot.running {
    animation: none;
    box-shadow: 0 0 12px var(--glow-status-dot);
  }
  
  .pos-card:hover {
    transition: none;
  }
}
```

---

## 5. Performance Budget

| Glow Type | Cost | Recommendation |
|-----------|------|----------------|
| `box-shadow` | Low | Safe for all components |
| `filter: drop-shadow()` | Medium | Use on SVG/small elements |
| `filter: blur()` | Medium-High | Limit to ≤3 elements per view |
| SVG duplicate-layer | High | Use only for hero elements (pulse graph) |
| Canvas glow | Very High | Avoid — CSS-only approach |

**Budget:** Max 8 glowing elements per viewport on mobile, 15 on desktop.

---

## 6. Accessibility

| Concern | Mitigation |
|---------|------------|
| **Epilepsy / Photosensitivity** | No rapid flash (>3Hz). Pulse rhythm 2s (0.5Hz) — safe. |
| **Visual Overload** | Weak glow default (15% opacity). Strong glow only on focus/hover. |
| **Contrast** | Glow never reduces text contrast — always behind/around content, never over text. |
| **Reduced Motion** | `prefers-reduced-motion` disables pulse animation, keeps static glow. |

---

## 7. Implementation Checklist (Z4.2)

- [ ] Create `theme-glow.css` with all token definitions
- [ ] Apply glow to pulse graph path (dashboard.html)
- [ ] Apply glow to status-dot (layout.html KPI cards)
- [ ] Apply glow to position card hover (after Z5)
- [ ] Verify light-mode reduction (50% opacity)
- [ ] Verify reduced-motion respect
- [ ] Performance test: ≤8 glowing elements on mobile

---

## 8. Design Rationale

**Why glow, not just brighter colors?**
- Glow creates **depth hierarchy** without heavy shadows (brown-tinted shadows per MASTER can muddy dark surfaces)
- Glow is **directional light illusion** — feels like elements emit light, not just reflect it
- Glow scales **perceptually logarithmic** (Weber-Fechner) — 15%/30%/40% opacity feels like even steps, not linear
- Glow is **performance-cheap** in CSS (`box-shadow` composited) vs. complex gradients/shadows

**Why not HL's flat approach?**
- HL prioritizes **information density** over depth (trader terminal aesthetic)
- Our spec (MASTER + glow) targets **premium polish** + emotional resonance (sanctuary aesthetic)
- Glow is **optional enhancement** — flat colors remain semantic baseline; glow adds lift, not replacement

---

## 9. Token Reference Table

| Token | Value | Usage |
|-------|-------|-------|
| `--glow-profit-weak` | `rgba(52, 211, 153, 0.15)` | Subtle profit halos |
| `--glow-profit-med` | `rgba(52, 211, 153, 0.3)` | Standard profit glow |
| `--glow-profit-strong` | `rgba(52, 211, 153, 0.4)` | Focused profit states |
| `--glow-loss-weak` | `rgba(251, 113, 133, 0.15)` | Subtle loss halos |
| `--glow-loss-med` | `rgba(251, 113, 133, 0.3)` | Standard loss glow |
| `--glow-loss-strong` | `rgba(251, 113, 133, 0.4)` | Focused loss states |
| `--glow-brand-weak` | `rgba(6, 214, 160, 0.15)` | Subtle brand halos |
| `--glow-brand-med` | `rgba(6, 214, 160, 0.3)` | Standard brand glow |
| `--glow-brand-strong` | `rgba(6, 214, 160, 0.4)` | Focused brand states |
| `--glow-pulse-path` | `var(--glow-brand-med)` | Equity curve SVG |
| `--glow-status-dot` | `var(--glow-brand-weak)` | Running engine indicator |
| `--glow-pos-card-hover` | `var(--glow-profit-weak)` | Position card hover |
| `--glow-kpi-focused` | `var(--glow-brand-med)` | KPI focus border |
| `--glow-cta-hover` | `var(--glow-brand-strong)` | CTA button hover |

---

**Next:** `theme-glow.css` (Z4.2 part 2) — CSS implementation of all tokens + application classes.
