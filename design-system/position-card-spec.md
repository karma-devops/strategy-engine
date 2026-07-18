# Position Card Specification — HyperLiquid Pattern Replication

**Authority:** This spec extends `MASTER.md` — does NOT override. All tokens resolve to MASTER.md semantic layer.

**Source:** Visually verified via HLS screenshot (2026-07-18 session, gemini-3.1-flash-lite vision analysis).

---

## 1. Visual Pattern (HL Reference)

| Element | HL Implementation | Our Mapping |
|---------|------------------|-------------|
| **Side Indicator** | Dual: (1) left-edge vertical spine (4-6px width, full row height) + (2) symbol+size text colored same | Spine via `::before` pseudo-element; symbol+size via `--pos-side-color` |
| **Long Color** | `#00C08B` (teal/mint) — applied to spine, symbol, size, funding | `--color-profit` (`#34D399`) per MASTER.md |
| **Short Color** | `#FF4D4D` (red/pink) — same positions | `--color-loss` (`#FB7185`) per MASTER.md |
| **Row Background** | None (no fill) — only spine + key text colored | `--surface-card` (`#15100B`) base, no side-tint |
| **PnL Color** | Dynamic green/red semantic | `--color-profit` / `--color-loss` |
| **Typography** | Monospaced numerics (Entry, Mark, Liq) for alignment | `--font-mono` (JetBrains Mono) |

---

## 2. Token Mapping (MASTER.md Authority)

```css
/* Semantic tokens — resolve to MASTER.md */
--pos-side-spine-long: var(--color-profit);    /* #34D399 */
--pos-side-spine-short: var(--color-loss);     /* #FB7185 */
--pos-surface: var(--surface-card);            /* #15100B */
--pos-text-primary: var(--text-primary);       /* #F5F1ED */
--pos-text-secondary: var(--text-secondary);   /* #A8A29A */
--pos-text-mono: var(--font-mono);             /* JetBrains Mono */
--pos-border-radius: var(--radius-md);         /* 8px */
--pos-spacing: var(--spacing-3);               /* 12px */
```

---

## 3. Field Set (Per Position Card)

| Field | Source | Format | Notes |
|-------|--------|--------|-------|
| **Market + Leverage** | Instance.token + Instance.leverage | `FARTCOIN · 1x` | Bold, neutral color |
| **Side Badge** | Instance.position_side | `LONG` / `SHORT` (badge) | Uppercase, colored background |
| **Size** | Instance.position_size | `369.8 FARTCOIN` | Colored by side |
| **Position Value** | Computed (size × mark) | `$47.70` | USD, neutral |
| **Entry Price** | Instance.entry_price | `$0.12898` | Mono, neutral |
| **Mark Price** | Instance.mark_price (live HL) | `$0.12816` | Mono, updates real-time |
| **PnL (ROE %)** | Instance.unrealized_pnl + computed % | `−$0.15 (−3.03%)` | Semantic color (green/red) |
| **Liq. Price** | Instance.liquidation_price | `$0.00` | Mono, red if near |
| **Margin** | Instance.leverage + mode | `Cross 1x` | Neutral |
| **Funding** | HL position.funding (if available) | `$0.00` | Colored by side (like HL) |
| **Close Button** | Action | `Close` | Calls `/api/v2/instances/{slug}/close` |
| **TP/SL** | Instance.take_profit / stop_loss | `$X.XX / $Y.YY` | Null-tolerant |

---

## 4. Component Structure (HTML/CSS)

### 4.1 Card Container
```html
<div class="pos-card" data-side="long|short">
  <div class="pos-spine"></div>
  <div class="pos-content">
    <!-- field rows -->
  </div>
</div>
```

### 4.2 Spine (Left-Edge Accent)
```css
.pos-card {
  position: relative;
  background: var(--pos-surface);
  border-radius: var(--pos-border-radius);
  overflow: hidden; /* spine stays inside card */
}

.pos-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 5px;
  background: var(--pos-side-spine-long); /* or --pos-side-spine-short */
}

.pos-card[data-side="short"]::before {
  background: var(--pos-side-spine-short);
}
```

### 4.3 Side Badge + Symbol+Size (Colored)
```css
.pos-side-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  background: var(--pos-side-spine-long);
  color: var(--pos-surface);
}

.pos-symbol-size {
  color: var(--pos-side-spine-long);
  font-weight: 600;
}

.pos-card[data-side="short"] .pos-side-badge,
.pos-card[data-side="short"] .pos-symbol-size {
  color: var(--pos-side-spine-short);
  background: var(--pos-side-spine-short);
}
```

### 4.4 Field Row (Grid Layout)
```css
.pos-field-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr); /* 3 columns, responsive */
  gap: var(--pos-spacing);
  padding: var(--pos-spacing);
}

.pos-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pos-field-label {
  font-size: 11px;
  color: var(--pos-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.pos-field-value {
  font-size: 14px;
  color: var(--pos-text-primary);
  font-family: var(--pos-text-mono);
}

.pos-field-value.pnl-positive { color: var(--color-profit); }
.pos-field-value.pnl-negative { color: var(--color-loss); }
```

### 4.5 Close Button (Action)
```css
.pos-close-btn {
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: 1px solid var(--color-loss);
  color: var(--color-loss);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pos-close-btn:hover {
  background: var(--color-loss);
  color: var(--pos-surface);
}
```

---

## 5. Empty State (No Position)

```html
<div class="pos-empty">
  <svg><!-- placeholder icon --></svg>
  <p>No open positions</p>
</div>
```

```css
.pos-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  color: var(--pos-text-secondary);
  text-align: center;
}

.pos-empty svg {
  width: 48px;
  height: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}
```

---

## 6. Responsive Breakpoints

| Breakpoint | Layout |
|------------|--------|
| **Desktop (>1024px)** | 3-column grid |
| **Tablet (768-1024px)** | 2-column grid |
| **Mobile (<768px)** | 1-column stack, 44px touch targets |

```css
@media (max-width: 1024px) {
  .pos-field-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .pos-field-row {
    grid-template-columns: 1fr;
  }
  
  .pos-close-btn {
    min-height: 44px; /* touch target */
    width: 100%;
  }
}
```

---

## 7. Implementation Checklist (Z5)

- [ ] Create `app/static/position-card.js` — renders cards into `#pos-grid` + `#pos-card`
- [ ] Wire `refresh()` polling loop to call render function
- [ ] Add SSE `position` event listener (Z6)
- [ ] Spine color dynamic (long/short switch)
- [ ] PnL color semantic (positive/negative)
- [ ] Close button calls `/api/v2/instances/{slug}/close`
- [ ] Empty state shows when no positions
- [ ] Mobile breakpoint tested (44px targets)
- [ ] MASTER.md tokens validated (no hardcoded colors)

---

## 8. Notes

- **Spine width:** 5px (HL uses ~4-6px)
- **No row fill:** Keep base surface (`#15100B`) — HL doesn't tint the row background
- **Symbol+Size colored:** Same as spine (key HL pattern differentiator)
- **Funding field:** Colored same as side (HL pattern) — only if data available
- **PnL %:** Computed as `(mark - entry) / entry * 100 * side_multiplier` (A4 enrichment)
- **Liq. Price:** Show red warning if within 5% of mark (future enhancement)
