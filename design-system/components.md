# Design System Components — Reconciled to MASTER.md

**Authority:** This spec is RECONCILED to `MASTER.md` — does NOT override. All components resolve to MASTER.md semantic tokens.

**Coverage:** Card, tag, button, input, tab, trade-row, pulse, position-side-spine.

---

## 1. Card Component

### 1.1 Base Card (KPI, Fleet, Position)

```css
.card {
  background: var(--surface-card);     /* #15100B */
  border-radius: var(--radius-md);     /* 8px */
  padding: var(--spacing-4);           /* 16px */
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);  /* brown-tinted shadow per MASTER */
  transition: box-shadow 0.2s ease;
}

.card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

/* Glow hover version (extends theme-glow.css) */
.card.glow-hover {
  box-shadow: 0 0 16px var(--glow-profit-weak);
}
```

### 1.2 Card Variants

```css
.card-surface {
  background: var(--surface-card);
}

.card-surface-elevated {
  background: var(--surface-card-elevated);   /* #1A1410 if defined in MASTER */
}

.card-alert {
  border-left: 4px solid var(--color-loss);   /* #FB7185 */
}

.card-success {
  border-left: 4px solid var(--color-profit); /* #34D399 */
}

.card-brand {
  border-left: 4px solid var(--color-brand);  /* #06D6A0 */
}
```

### 1.3 Card Fields

```css
.card-title {
  font-family: var(--font-display);           /* Space Grotesk */
  font-size: var(--text-lg);                  /* 18px */
  font-weight: 700;
  color: var(--text-primary);                 /* #F5F1ED */
  margin-bottom: var(--spacing-2);            /* 8px */
}

.card-subtitle {
  font-family: var(--font-body);              /* Inter */
  font-size: var(--text-sm);                  /* 14px */
  color: var(--text-secondary);               /* #A8A29A */
  margin-bottom: var(--spacing-3);            /* 12px */
}

.card-stat {
  font-family: var(--font-mono);              /* JetBrains Mono */
  font-size: var(--text-xl);                  /* 24px */
  font-weight: 600;
  color: var(--text-primary);
}

.card-stat-label {
  font-size: var(--text-xs);                  /* 12px */
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
```

### 1.4 Card Structure

```html
<div class="card card-brand">
  <div class="card-title">Total PnL</div>
  <div class="card-stat">+ $0.13</div>
  <div class="card-subtitle">Live — Last 24h</div>
</div>
```

---

## 2. Tag Component

```css
.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);            /* 4px */
  font-size: var(--text-xs);                  /* 12px */
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.tag-profit {
  background: var(--color-profit);
  color: var(--surface-card);
}

.tag-loss {
  background: var(--color-loss);
  color: var(--surface-card);
}

.tag-brand {
  background: var(--color-brand);
  color: var(--surface-card);
}

.tag-neutral {
  background: var(--text-secondary);
  color: var(--surface-card);
}

.tag-running {
  background: var(--color-brand);
  color: var(--surface-card);
}

.tag-stopped {
  background: var(--text-secondary);
  color: var(--surface-card);
}
```

### HTML Structure

```html
<span class="tag tag-profit">LONG</span>
<span class="tag tag-running">ONLINE</span>
<span class="tag tag-loss">-3.03%</span>
```

---

## 3. Button Component

### 3.1 Base Button

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  border-radius: var(--radius-md);           /* 8px */
  font-size: var(--text-sm);                 /* 14px */
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  outline: none;
  min-height: 44px;                          /* 44px touch target */
}

.btn:focus-visible {
  outline: 2px solid var(--color-brand);
  outline-offset: 2px;
}
```

### 3.2 Button Variants

```css
.btn-cta {
  background: var(--color-brand);
  color: var(--surface-card);
}

.btn-cta:hover {
  background: var(--color-brand);
  box-shadow: 0 0 16px var(--glow-cta-hover);
  transform: translateY(-1px);
}

.btn-secondary {
  background: transparent;
  border: 1px solid var(--text-secondary);
  color: var(--text-primary);
}

.btn-secondary:hover {
  background: rgba(168, 162, 154, 0.1);
}

.btn-loss {
  background: var(--color-loss);
  color: var(--surface-card);
}

.btn-loss:hover {
  background: var(--color-loss);
  box-shadow: 0 0 16px var(--glow-loss-med);
}

.btn-success {
  background: var(--color-profit);
  color: var(--surface-card);
}
```

---

## 4. Input Component

```css
.input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--text-secondary);
  border-radius: var(--radius-md);           /* 8px */
  font-size: var(--text-base);               /* 16px */
  font-family: var(--font-body);             /* Inter */
  color: var(--text-primary);
  background: var(--surface-card);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.input::placeholder {
  color: var(--text-tertiary);
}

.input:focus {
  border-color: var(--color-brand);
  box-shadow: 0 0 0 3px var(--glow-brand-weak);
  outline: none;
}

.input.error {
  border-color: var(--color-loss);
}

.input.error:focus {
  box-shadow: 0 0 0 3px var(--glow-loss-weak);
}
```

---

## 5. Tab Component

```css
.tab-nav {
  display: flex;
  gap: var(--spacing-2);                     /* 8px */
  border-bottom: 1px solid var(--text-secondary);
}

.tab {
  padding: 10px 16px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--text-primary);
  border-bottom-color: var(--color-brand);
}

.tab-panel {
  padding: var(--spacing-4);
}
```

---

## 6. Trade Row Component

### 6.1 Base Structure

```css
.trade-row {
  display: grid;
  grid-template-columns: auto 1fr auto auto auto auto;
  gap: var(--spacing-3);                     /* 12px */
  padding: var(--spacing-3);
  border-bottom: 1px solid var(--text-tertiary);
  align-items: center;
}

.trade-row:last-child {
  border-bottom: none;
}

.trade-row:nth-child(even) {
  background: rgba(168, 162, 154, 0.03);    /* subtle even-row tint */
}
```

### 6.2 Trade Fields

```css
.trade-symbol {
  font-weight: 600;
  color: var(--text-primary);
}

.trade-side {
  font-size: var(--text-xs);
  font-weight: 700;
  text-transform: uppercase;
}

.trade-side-long {
  color: var(--color-profit);
}

.trade-side-short {
  color: var(--color-loss);
}

.trade-pnl {
  font-family: var(--font-mono);
  font-weight: 600;
}

.trade-pnl-positive {
  color: var(--color-profit);
}

.trade-pnl-negative {
  color: var(--color-loss);
}

.trade-time {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.trade-action {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.trade-action:hover {
  color: var(--color-brand);
}
```

### 6.3 Trade Row HTML

```html
<div class="trade-row">
  <span class="trade-symbol">FARTCOIN</span>
  <span class="trade-side trade-side-long">LONG</span>
  <span class="trade-time">18:35:42</span>
  <span class="trade-pnl trade-pnl-negative">−$15.26</span>
  <span class="trade-action">View</span>
  <span class="trade-action">Close</span>
</div>
```

---

## 7. Pulse Graph Component

### 7.1 Container

```css
.pulse-graph {
  position: relative;
  width: 100%;
  height: 200px;
  background: var(--surface-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-4);
}

.pulse-canvas {
  width: 100%;
  height: 100%;
}
```

### 7.2 SVG Path (with glow)

```html
<svg class="pulse-graph">
  <g id="pulse-glow-layer">
    <path id="pulse-path-glow" stroke="var(--glow-brand-med)" stroke-width="6" filter="blur(4px)" opacity="0.5" />
  </g>
  <path id="pulse-path" stroke="var(--color-brand)" stroke-width="2" class="pulse-glow-path" />
</svg>
```

### 7.3 Hover Tooltip

```css
.pulse-tooltip {
  position: absolute;
  background: var(--surface-card);
  border: 1px solid var(--text-secondary);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: var(--text-xs);
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}
```

---

## 8. Position Side-Spine Component

### 8.1 Card Container

```css
.pos-card {
  position: relative;
  background: var(--surface-card);
  border-radius: var(--radius-md);
  overflow: hidden;
  padding: var(--spacing-3);
}

.pos-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 5px;
  background: var(--pos-side-spine-long);
}

.pos-card[data-side="short"]::before {
  background: var(--pos-side-spine-short);
}
```

### 8.2 Side Badge

```css
.pos-side-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  margin-right: var(--spacing-2);
}

.pos-side-badge.long {
  background: var(--color-profit);
  color: var(--surface-card);
}

.pos-side-badge.short {
  background: var(--color-loss);
  color: var(--surface-card);
}
```

### 8.3 Symbol + Size (Colored)

```css
.pos-symbol-size {
  font-weight: 600;
}

.pos-card[data-side="long"] .pos-symbol-size {
  color: var(--color-profit);
}

.pos-card[data-side="short"] .pos-symbol-size {
  color: var(--color-loss);
}
```

### 8.4 Field Grid

```css
.pos-fields {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-3);
  margin-top: var(--spacing-3);
}

.pos-field-item {
  display: flex;
  flex-direction: column;
}

.pos-field-label {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 2px;
}

.pos-field-value {
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--text-primary);
}

.pos-field-value.pnl-positive {
  color: var(--color-profit);
}

.pos-field-value.pnl-negative {
  color: var(--color-loss);
}
```

### 8.5 Position Card HTML

```html
<div class="pos-card" data-side="long">
  <div class="pos-header">
    <span class="pos-side-badge long">LONG</span>
    <span class="pos-symbol-size">369.8 FARTCOIN</span>
  </div>
  <div class="pos-fields">
    <div class="pos-field-item">
      <span class="pos-field-label">Entry</span>
      <span class="pos-field-value">$0.12898</span>
    </div>
    <div class="pos-field-item">
      <span class="pos-field-label">Mark</span>
      <span class="pos-field-value">$0.12816</span>
    </div>
    <div class="pos-field-item">
      <span class="pos-field-label">PnL</span>
      <span class="pos-field-value pnl-negative">−$0.15 (−3.03%)</span>
    </div>
    <!-- More fields: Size, Value, Liq, Margin, Funding, Close -->
  </div>
  <button class="btn btn-loss pos-close-btn">Close</button>
</div>
```

---

## 9. Responsive Breakpoints

```css
/* Desktop (>1024px) */
.trade-row {
  grid-template-columns: auto 1fr auto auto auto auto;
}

.pos-fields {
  grid-template-columns: repeat(3, 1fr);
}

/* Tablet (768-1024px) */
@media (max-width: 1024px) {
  .trade-row {
    grid-template-columns: auto 1fr auto auto;
  }
  
  .pos-fields {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* Mobile (<768px) */
@media (max-width: 768px) {
  .trade-row {
    grid-template-columns: 1fr auto;
    gap: 8px;
  }
  
  .pos-fields {
    grid-template-columns: 1fr;
  }
  
  .pos-card {
    padding: var(--spacing-3);
  }
  
  .btn, .input {
    min-height: 44px;
  }
}
```

---

## 10. Implementation Checklist (Z4.3)

- [ ] Apply `card` component to dashboard KPIs
- [ ] Apply `tag` to position side badges (LONG/SHORT)
- [ ] Apply `btn-cta` style to action buttons (Close, Deploy, Start)
- [ ] Apply `input` to settings forms (leverage, risk, etc.)
- [ ] Apply `tab` to strategy detail tabs
- [ ] Apply `trade-row` to trades page (add paper/live badge)
- [ ] Apply `pulse-graph` to dashboard (verify glow)
- [ ] Apply `pos-card` pattern (spine + fields) to dashboard & engine detail
- [ ] Verify responsive breakpoints (tablet + mobile)
- [ ] Verify MASTER.md token resolution (no hardcoded colors)

---

## 11. Notes

- **Brown-tinted shadows** per MASTER.md: Use `rgba(0, 0, 0, 0.3)` instead of pure black
- **Monospace numerics**: Entry, Mark, Liq, PnL use `font-family: var(--font-mono)` for alignment
- **44px touch target**: All buttons, inputs, close actions on mobile must be ≥44px
- **Semantic colors**: Profit/loss/brand map to MASTER tokens (no hardcoded hex)
- **Glow integration**: Apply `theme-glow.css` classes where appropriate (hover states, pulse graph)

---

**Next:** Z5 (position-card.js implementation) or Z1-Z7 code execution.
