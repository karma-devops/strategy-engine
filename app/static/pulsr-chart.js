/* ════════════════════════════════════════════════════════════════════
   PULS-R Chart Component
   Wraps TradingView Lightweight Charts v5.2.0 (served locally).
   Used across: testing/paper, dashboard Pulse Graph, engine detail,
                per-fleet sparkline cards. No external dependencies.

   Exposes global `PulsRChart` with:
     - createEquityChart(container, options) → returns {chart, series, update(data), destroy()}
     - createSparkline(container, options)  → returns {chart, series, setValue(v), destroy()}

   Data shape expected: Array<{time: number|ISO, value: number}>
   ════════════════════════════════════════════════════════════════════ */
(function() {
    'use strict';

    // Resolve theme from the document's data-mode attribute.
    function getTheme() {
        const mode = (document.documentElement.getAttribute('data-mode') || 'dark').toLowerCase();
        return mode === 'light' ? lightTheme() : darkTheme();
    }

    function darkTheme() {
        // Read CSS custom properties (--brand, --text-*, --color-*) at runtime.
        const cs = getComputedStyle(document.documentElement);
        return {
            layout: {
                background: { type: 'solid', color: 'transparent' },
                textColor: cs.getPropertyValue('--text-primary').trim() || '#F5EDDE',
                fontFamily: (cs.getPropertyValue('--font-body') || 'Inter, sans-serif').replace(/['"]/g, '').trim(),
                attributionLogo: false,
            },
            grid: {
                vertLines: { color: 'rgba(255,255,255,0.04)' },
                horzLines: { color: 'rgba(255,255,255,0.04)' },
            },
            rightPriceScale: {
                borderColor: 'rgba(255,255,255,0.08)',
            },
            timeScale: {
                borderColor: 'rgba(255,255,255,0.08)',
                timeVisible: true,
                secondsVisible: false,
            },
            crosshair: {
                vertLine: { color: 'rgba(8,121,142,0.4)', width: 1, style: 3 },
                horzLine: { color: 'rgba(8,121,142,0.4)', width: 1, style: 3 },
            },
        };
    }

    function lightTheme() {
        const cs = getComputedStyle(document.documentElement);
        return {
            layout: {
                background: { type: 'solid', color: 'transparent' },
                textColor: cs.getPropertyValue('--text-primary').trim() || '#1A1410',
                fontFamily: (cs.getPropertyValue('--font-body') || 'Inter, sans-serif').replace(/['"]/g, '').trim(),
                attributionLogo: false,
            },
            grid: {
                vertLines: { color: 'rgba(0,0,0,0.05)' },
                horzLines: { color: 'rgba(0,0,0,0.05)' },
            },
            rightPriceScale: { borderColor: 'rgba(0,0,0,0.12)' },
            timeScale: { borderColor: 'rgba(0,0,0,0.12)', timeVisible: true, secondsVisible: false },
            crosshair: {
                vertLine: { color: 'rgba(8,121,142,0.5)', width: 1, style: 3 },
                horzLine: { color: 'rgba(8,121,142,0.5)', width: 1, style: 3 },
            },
        };
    }

    // Convert any time value to a Unix seconds (number) accepted by LWC.
    function toLwcTime(t) {
        if (typeof t === 'number') {
            // Already seconds if < 1e11, ms if larger.
            return t < 1e11 ? t : Math.floor(t / 1000);
        }
        if (typeof t === 'string') {
            // ISO string or timestamp string.
            const ms = Date.parse(t);
            return isNaN(ms) ? null : Math.floor(ms / 1000);
        }
        return null;
    }

    function normalizeSeries(data) {
        if (!Array.isArray(data)) return [];
        const out = [];
        for (const p of data) {
            if (!p) continue;
            const time = toLwcTime(p.time ?? p[0]);
            const value = typeof p.value === 'number' ? p.value : parseFloat(p.value ?? p.equity ?? p[1]);
            if (time != null && !isNaN(value)) out.push({ time, value });
        }
        // LWC requires strictly ascending time. Sort + dedup.
        out.sort((a, b) => a.time - b.time);
        const deduped = [];
        for (const p of out) {
            if (deduped.length === 0 || deduped[deduped.length - 1].time !== p.time) deduped.push(p);
        }
        return deduped;
    }

    // Compute line color based on sign of first→last change.
    function pickLineColor(values) {
        if (values.length < 2) return '#34D399';
        const first = values[0].value, last = values[values.length - 1].value;
        return last >= first ? '#34D399' : '#F87171';
    }

    // ═══ Public API ═══
    const PulsRChart = {
        /**
         * Create a full equity chart with area fill + price line.
         * @param {string|HTMLElement} container - container id or element
         * @param {Object} options
         *   - height: number (default 220)
         *   - type: 'area' (default) | 'line'
         *   - showTimeScale: bool (default true)
         *   - showRightPriceScale: bool (default true)
         *   - autosize: bool (default true)
         */
        createEquityChart(container, options) {
            const el = (typeof container === 'string') ? document.getElementById(container) : container;
            if (!el) return null;
            if (typeof LightweightCharts === 'undefined') {
                console.error('PulsRChart: LightweightCharts not loaded. Did you include the script tag?');
                return null;
            }
            const opts = Object.assign({
                height: 220,
                type: 'area',
                showTimeScale: true,
                showRightPriceScale: true,
                autosize: true,
            }, options || {});

            const chart = LightweightCharts.createChart(el, Object.assign(
                getTheme(),
                {
                    width: el.clientWidth || 600,
                    height: opts.height,
                    autoSize: opts.autosize,
                    handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
                    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true },
                }
            ));

            const series = chart.addAreaSeries({
                topColor: 'rgba(52,211,153,0.45)',
                bottomColor: 'rgba(52,211,153,0.04)',
                lineColor: '#34D399',
                lineWidth: 2,
                priceLineVisible: false,
                lastValueVisible: true,
            });

            // Set visibility of axes
            chart.timeScale().applyOptions({ visible: opts.showTimeScale });
            // v5+: rightPriceScale moved to chart options, set on creation via merge above.

            const handle = {
                chart,
                series,
                _data: [],
                _lineColor: '#34D399',
                setData(rawData) {
                    const norm = normalizeSeries(rawData);
                    this._data = norm;
                    if (norm.length > 0) {
                        this._lineColor = pickLineColor(norm);
                        this.series.applyOptions({ lineColor: this._lineColor });
                        try { this.series.setData(norm); } catch (e) { /* ignore time-order errors */ }
                        this.chart.timeScale().fitContent();
                    } else {
                        // Empty state
                        this.series.setData([]);
                    }
                },
                update(point) {
                    // Single-point append. Coalesces if time collides.
                    const t = toLwcTime(point.time);
                    const v = typeof point.value === 'number' ? point.value : parseFloat(point.value);
                    if (t == null || isNaN(v)) return;
                    if (this._data.length && this._data[this._data.length - 1].time === t) {
                        this._data[this._data.length - 1].value = v;
                    } else {
                        this._data.push({ time: t, value: v });
                    }
                    const newColor = pickLineColor(this._data);
                    if (newColor !== this._lineColor) {
                        this._lineColor = newColor;
                        this.series.applyOptions({ lineColor: this._lineColor });
                    }
                    try { this.series.setData(this._data); } catch (e) { /* ignore */ }
                    this.chart.timeScale().fitContent();
                },
                destroy() {
                    try { this.chart.remove(); } catch (e) { /* ignore */ }
                },
            };
            return handle;
        },

        /**
         * Create a tiny sparkline (no axes, no time scale).
         * @param {string|HTMLElement} container
         * @param {Object} options
         *   - height: number (default 28)
         *   - width: number (default container width or 100)
         */
        createSparkline(container, options) {
            const el = (typeof container === 'string') ? document.getElementById(container) : container;
            if (!el || typeof LightweightCharts === 'undefined') return null;
            const opts = Object.assign({
                height: 28,
                width: el.clientWidth || 100,
            }, options || {});

            const chart = LightweightCharts.createChart(el, Object.assign(
                getTheme(),
                {
                    width: opts.width,
                    height: opts.height,
                    autoSize: false,
                    handleScale: false,
                    handleScroll: false,
                    grid: { vertLines: { visible: false }, horzLines: { visible: false } },
                    timeScale: { visible: false },
                    rightPriceScale: { visible: false },
                    crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
                }
            ));

            const series = chart.addLineSeries({
                color: '#34D399',
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
            });

            return {
                chart,
                series,
                setData(rawData) {
                    const norm = normalizeSeries(rawData);
                    if (norm.length === 0) { series.setData([]); return; }
                    const color = pickLineColor(norm);
                    series.applyOptions({ color });
                    try { series.setData(norm); } catch (e) { /* ignore */ }
                    chart.timeScale().fitContent();
                },
                destroy() { try { chart.remove(); } catch (e) { /* ignore */ } },
            };
        },

        // Re-read theme after a data-mode change (operator toggles dark/light).
        // Charts using this must call refresh() and pass their handle in.
        themeVersion: 0,
        bumpTheme() { this.themeVersion += 1; },
    };

    // Expose globally.
    window.PulsRChart = PulsRChart;

    // Auto-bump theme version when data-mode changes.
    document.addEventListener('dataModeChanged', () => PulsRChart.bumpTheme());
    // The layout's applyAppMode() should dispatch this event; if not, observe attribute.
    const obs = new MutationObserver((muts) => {
        for (const m of muts) {
            if (m.attributeName === 'data-mode') PulsRChart.bumpTheme();
        }
    });
    if (document.documentElement) {
        obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-mode'] });
    }
})();
