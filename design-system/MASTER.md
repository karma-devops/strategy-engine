# PULS-R Design System — MASTER

**Version:** 1.0.0
**Date:** 2026-07-12
**Token file:** `app/static/tokens.css`

---

## 1. Design Philosophy

**Trust + Precision.** A trading engine dashboard for HyperLiquid perpetuals. The UI must convey institutional reliability while feeling modern and fast. Every pixel earns its place.

**Emotional profile** (from Gestalt emotional matrix): Low-energy — Trust, Safety, Precision. Muted earth tones, clear negative space, high legibility, geometric typography.

**Differentiator:** Warm dark brown palette (not cold black, not green-tinted). The sienna warmth signals "crafted tool" not "generic SaaS template." Space Grotesk headings give technical edge without sterility.

---

## 2. Token Architecture

Three-layer system (Primitive → Semantic → Component):

```
tokens.css
├── Layer 1: Primitives (raw hex, px, ms values)
├── Layer 2: Semantic (purpose aliases — surface, text, border, color)
└── Layer 3: Component (specific elements — card, tab, tag, input)
```

**Rule:** Components NEVER reference primitives. Always go through semantic or component tokens. This enables theme switching (dark/light) by changing only semantic values.

### Dark Mode (default)

| Token | Value | Purpose |
|-------|-------|---------|
| `--surface-page` | `#0F0A07` | Page background |
| `--surface-card` | `#15100B` | Card background |
| `--surface-raised` | `#221A13` | Elevated elements |
| `--text-primary` | `#F5EDDE` | Primary text |
| `--text-secondary` | `#C4B498` | Secondary text |
| `--text-muted` | `#8A7A64` | Labels, hints |
| `--color-profit` | `#34D399` | Emerald — profit, success |
| `--color-loss` | `#FB7185` | Coral — loss, danger |
| `--color-info` | `#6BA4D5` | Sky — info, neutral |
| `--color-warn` | `#F0B90B` | Amber — warning |

### Light Mode (PWA landing pages)

| Token | Value | Purpose |
|-------|-------|---------|
| `--surface-page` | `#F5F0EB` | Warm cream |
| `--surface-card` | `#FFFFFF` | White card |
| `--text-primary` | `#1A1410` | Near-black |

---

## 3. Typography Scale

**Fonts:**
- **Display/Headings:** Space Grotesk (600-700) — distinctive, technical, geometric
- **Body/UI:** Inter (400-600) — clean, readable, functional
- **Data/Mono:** JetBrains Mono (400-500) — tabular numbers, code, logs

**Type Scale (1.250 — Major Third ratio):**

| Token | Size | Usage |
|-------|------|-------|
| `--text-xs` | 10px | Labels, tags, micro-text |
| `--text-sm` | 12px | Secondary text, table cells |
| `--text-base` | 13px | Body text (compact UI) |
| `--text-md` | 14px | Card headings, buttons |
| `--text-lg` | 16px | Section headings |
| `--text-xl` | 20px | Stat values, page titles |
| `--text-2xl` | 25px | Landing hero |
| `--text-3xl` | 31px | Landing display |
| `--text-4xl` | 39px | Landing hero headline |

**Line heights:** 1.25 (tight/headings), 1.5 (body), 1.75 (relaxed/long text)

**Gestalt rule:** Body text 45-75 characters per line. Use `max-width` on text containers.

---

## 4. Spacing Scale (4pt base)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight gaps (icon to text) |
| `--space-2` | 8px | Component internal padding |
| `--space-3` | 12px | Small gaps between elements |
| `--space-4` | 16px | Card padding, standard gap |
| `--space-5` | 20px | Section internal gap |
| `--space-6` | 24px | Between sections |
| `--space-8` | 32px | Large section gap |
| `--space-10` | 40px | Page section padding |
| `--space-12` | 48px | Hero spacing |
| `--space-16` | 64px | Landing section spacing |

**Gestalt proximity rule:** Spacing BETWEEN groups (Sb) must be >= 2.5 * spacing WITHIN groups (Si). Example: card padding 16px (Si), gap between cards 40px (Sb).

---

## 5. Component Specs

### 5.1 Button

| Variant | Background | Text | Border | Hover | Min Height | Padding |
|---------|-----------|------|--------|-------|------------|---------|
| Primary | `--btn-primary-bg` | `--btn-primary-text` | none | `--btn-primary-hover` | 36px | 8px 16px |
| Secondary | `--btn-secondary-bg` | `--btn-secondary-text` | `--border-default` | `--btn-secondary-hover` | 36px | 8px 16px |
| Danger | `--btn-danger-bg` | `--btn-danger-text` | `--color-loss-border` | fills coral | 36px | 8px 16px |
| Icon | `--surface-raised` | `--text-secondary` | `--border-default` | `--surface-hover` | 36px (square) | 0 |
| Small | `--surface-raised` | `--text-secondary` | `--border-default` | `--surface-hover` | 28px | 4px 10px |

**States:** All buttons have focus ring (2px solid `--input-focus`), disabled (opacity 0.4, cursor not-allowed), active (scale 0.98).

**Touch target:** Minimum 44x44px on mobile (use padding to expand hit area).

### 5.2 Card

| Property | Value |
|----------|-------|
| Background | `--card-bg` |
| Border | 1px solid `--card-border` |
| Radius | `--card-radius` (14px) |
| Padding | `--card-padding` (16px) |
| Shadow | `--card-shadow` |
| Header border | 1px solid `--card-head-border` |

**Gestalt common region:** Card border creates clear enclosure. Never let content overflow card boundaries. Header separated by border-bottom.

### 5.3 Tag / Badge

| Variant | Background | Text | Border | Radius |
|---------|-----------|------|--------|--------|
| Neutral | `--tag-neutral-bg` | `--tag-neutral-text` | none | 4px |
| Running | `--tag-running-bg` | `--tag-running-text` | 1px `--tag-running-border` | 4px |
| Stopped | `--tag-stopped-bg` | `--tag-stopped-text` | 1px `--tag-stopped-border` | 4px |
| Long | `--color-profit-bg` | `--color-profit` | 1px `--color-profit-border` | 3px |
| Short | `--color-loss-bg` | `--color-loss` | 1px `--color-loss-border` | 3px |

Font: `--text-xs` (10px), `--weight-bold`, `--tracking-wide`.

### 5.4 Input

| Property | Value |
|----------|-------|
| Background | `--input-bg` |
| Border | 1px solid `--input-border` |
| Text | `--input-text` |
| Focus border | `--input-focus` |
| Placeholder | `--input-placeholder` |
| Radius | `--radius-sm` (6px) |
| Padding | 8px 10px |
| Height | 36px (all inputs, all pages) |
| Label | Above input, left-aligned, `--text-xs` uppercase |

### 5.5 Tab

| State | Color | Border |
|-------|-------|--------|
| Inactive | `--tab-color` | none |
| Hover | `--text-secondary` | none |
| Active | `--tab-active-color` | 2px bottom `--tab-active-border` |

Font: `--text-sm`, `--weight-semibold`. Padding: 10px 16px.

### 5.6 Trade Row

| Property | Value |
|----------|-------|
| Background | `--trade-row-bg` |
| Hover | `--trade-row-hover` |
| Border | 1px solid `--trade-row-border` |
| Radius | `--radius-sm` |
| Padding | 8px 10px |
| Layout | flex row: time / symbol / side badge / pnl (right-aligned) |

### 5.7 Stat (metrics grid item)

| Property | Value |
|----------|-------|
| Background | `--surface-raised` |
| Border | 1px solid `--border-subtle` |
| Radius | `--radius-md` |
| Padding | 12px |
| Label | `--text-xs`, `--text-muted`, uppercase, `--tracking-wide` |
| Value | `--text-md` (16px), `--weight-bold`, tabular-nums |

---

## 6. Layout System

### Breakpoints (mobile-first)

| Name | Min-width | Target |
|------|-----------|--------|
| base | 0 | Mobile portrait (375px) |
| sm | 375px | Mobile landscape |
| md | 768px | Tablet |
| lg | 1024px | Desktop |
| xl | 1440px | Large desktop |

### Grid

- **Dashboard:** `grid-template-columns: 1.4fr 1fr` on desktop, `1fr` on mobile
- **Landing:** Single column, `max-width: 768px` for text, `1280px` for sections
- **Fleet grid:** `repeat(auto-fill, minmax(240px, 1fr))`
- **Metrics grid:** `repeat(auto-fit, minmax(100px, 1fr))`

### Content Width

- **Dashboard:** Full width, 16px padding
- **Landing:** `max-width: 1280px`, centered, `--space-6` horizontal padding
- **Text blocks:** `max-width: 768px` (65-75 chars at 16px)

---

## 7. Navigation Patterns

### Dashboard (logged in)

- **Desktop (lg+):** Two-column layout. Left: graph + fleet + trades. Right: engine detail + activity log.
- **Tablet (md):** Single column, stacked. Fleet grid becomes 2 columns.
- **Mobile (base):** Single column. Bottom nav bar with 4 icons (Dashboard, Fleet, Backtest, Settings). Fleet grid 1 column. Cards full-width.

### PWA Landing (public)

- **Nav:** Top bar with logo left, links right. Mobile: hamburger → slide-in panel from right.
- **Footer:** Always visible. Logo, copyright, social links.
- **Pages:** SPA hash router — `#/` (landing), `#/about`, `#/faq`, `#/login`, `#/dashboard`

---

## 8. Animation Guidelines

| Context | Duration | Easing | Property |
|---------|----------|--------|----------|
| Button hover | 120ms | `--ease-out` | background-color, border-color |
| Card hover | 200ms | `--ease-out` | border-color, box-shadow |
| Tab switch | 200ms | `--ease-out` | color, border-color |
| Fleet toggle | 350ms | `--ease-out` | max-height, opacity |
| Page transition | 350ms | `--ease-out` | opacity, transform |
| Modal open | 200ms | `--ease-out` | opacity, scale (0.96 → 1) |

**Gestalt common fate:** Grouped elements animate together (same duration, same direction). Never stagger related items.

**Reduced motion:** All animations respect `prefers-reduced-motion: reduce`.

---

## 9. Accessibility Checklist

- [ ] Text contrast >= 4.5:1 (WCAG AA) for body, >= 3:1 for large text
- [ ] Focus visible on all interactive elements (2px ring, `--input-focus` color)
- [ ] Touch targets >= 44x44px on mobile
- [ ] No color-only meaning (always add icon or text with color states)
- [ ] Heading hierarchy: h1 → h2 → h3, no level skip
- [ ] `prefers-reduced-motion` respected
- [ ] `aria-label` on icon-only buttons
- [ ] Form labels visible (not placeholder-only)
- [ ] Error messages near the field, include recovery path

---

## 10. Gestalt Audit Protocol

Before shipping any UI change, run the three defeasibility tests:

### 10.1 Blur Isolation (30px)
Apply Gaussian blur. Do interactive elements merge into unified visual blocks? If unrelated elements bleed together, proximity is broken.

### 10.2 Color Property Erasure (Grayscale)
Strip all color. Can you identify the primary CTA within 2 seconds? If not, hierarchy depends on color alone — add scale/weight differentiation.

### 10.3 Boundary Strike
Remove all borders and card backgrounds. Does the layout hold with whitespace alone? If text blocks merge, increase outer margins.

### Current Audit Issues (from Phase 1 assessment)

1. **Engine Detail empty state** — figure-ground ambiguity when no engine selected. Fix: show placeholder content with clear visual weight.
2. **Column height imbalance** — left column (graph+fleet+trades) is taller than right (detail+log). Fix: equalize with min-height or flexible layout.
3. **Card header controls misaligned** — Collapse button, 30D badge, trade count, Copy/Clear don't align vertically across cards. Fix: standardize card header height and action placement.
4. **Trade History dead space** — empty state creates visual dead end. Fix: add subtle illustration or "Start engine to generate trades" guidance.

---

## 11. PWA Configuration

### manifest.json
- **name:** PULS-R Strategy Engine
- **short_name:** PULS-R
- **theme_color:** `#0F0A07` (dark)
- **background_color:** `#0F0A07`
- **display:** standalone
- **icons:** 192px, 512px (SVG-based, sienna mark)
- **start_url:** `/`

### Service Worker
- Cache: app shell (HTML, CSS, JS, fonts)
- Network-first for API calls
- Offline fallback: cached dashboard shell with "offline" banner

### Pages

| Route | Page | Auth |
|-------|------|------|
| `#/` | Landing (splash, hero, features, CTA) | Public |
| `#/about` | About (what PULS-R is, how it works, team) | Public |
| `#/faq` | FAQ (common questions, troubleshooting) | Public |
| `#/login` | Login (username/password → dashboard) | Public |
| `#/dashboard` | Full trading dashboard | Required |

---

## 12. File Structure

```
app/
├── static/
│   ├── tokens.css          # Layer 1-3 tokens (import FIRST)
│   ├── style.css            # Component styles (import AFTER tokens)
│   ├── app.js               # Dashboard logic
│   ├── pages.js             # PWA router + landing/about/faq logic
│   ├── manifest.json         # PWA manifest
│   └── sw.js                 # Service worker
├── templates/
│   ├── dashboard.html       # Logged-in dashboard
│   ├── landing.html          # PWA shell (landing + about + faq + login)
│   └── ...
design-system/
└── MASTER.md                # This file
```