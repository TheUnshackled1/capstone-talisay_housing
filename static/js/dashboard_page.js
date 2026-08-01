/* ============================================================
   dashboard_page.js
   Chart rendering and dashboard interactivity for the main
   IHSMS dashboard. Extracted from dashboard.html inline script.

   Django data is passed via data-* attributes on <body>:
     data-blacklist-count  → blacklist_count context variable
   ============================================================ */

// ── Time-of-day greeting ────────────────────────────────────
(function () {
    var el = document.getElementById('welcomeGreeting');
    if (!el) return;
    var h = new Date().getHours();
    el.textContent = h < 12 ? 'Good morning,' : h < 17 ? 'Good afternoon,' : 'Good evening,';
})();

// ── Analytics Charts ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    var el = document.getElementById('tha-analytics-charts');
    if (!el || typeof Chart === 'undefined') return;
    var D;
    try { D = JSON.parse(el.textContent); } catch (e) { return; }
    if (!D) return;

    // Read Django context values passed via data-* on <body>
    var bodyEl = document.body;
    var blacklistCount = parseInt(bodyEl.getAttribute('data-blacklist-count') || '0', 10);

    var PALETTE = [
        '#2F6FD6', // Blue
        '#D4AF37', // Gold
        '#14B8A6', // Teal
        '#22C55E', // Green
        '#64748B', // Slate
        '#8B5CF6', '#F43F5E', '#0EA5E9', '#F59E0B', '#10B981'
    ];

    function hexToRgba(hex, alpha) {
        hex = hex.replace('#', '');
        var r = parseInt(hex.substring(0, 2), 16);
        var g = parseInt(hex.substring(2, 4), 16);
        var b = parseInt(hex.substring(4, 6), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function sum(arr) {
        return arr.reduce(function (s, n) { return s + (Number(n) || 0); }, 0);
    }

    function getSingleSeriesDataset(key) {
        var spec = D[key];
        if (!spec || !spec.labels || !spec.values || !spec.labels.length) return null;
        return {
            type: 'single',
            labels: spec.labels.map(function (l) {
                var s = String(l);
                if (s === s.toUpperCase() && s.length > 1) {
                    s = s.replace(/\w\S*/g, function (w) {
                        return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
                    });
                }
                return s;
            }),
            values: spec.values.map(function (v) { return Number(v) || 0; })
        };
    }

    function getStandardizedDataset(canvasId) {
        switch (canvasId) {
            case 'chartTrend':
                if (!D.trend || !D.trend.labels) return null;
                return {
                    type: 'multi',
                    labels: D.trend.labels,
                    datasets: [
                        { label: 'New applicants', values: D.trend.registrations || [], color: '#2F6FD6', fillOpacity: 0.12 },
                        { label: 'Vault uploads',  values: D.trend.vaultUploads  || [], color: '#14B8A6', fillOpacity: 0.14 }
                    ]
                };
            case 'chartApplicants':    return getSingleSeriesDataset('applicantsByStatus');
            case 'chartChannels':      return getSingleSeriesDataset('channels');
            case 'chartBarangays':     return getSingleSeriesDataset('topBarangays');
            case 'chartApplications':  return getSingleSeriesDataset('applicationsByStatus');
            case 'chartHousing':       return getSingleSeriesDataset('housingByStatus');
            case 'chartISFPopulation': return getSingleSeriesDataset('isfPopulation');
            case 'chartISFOverall':    return getSingleSeriesDataset('isfOverall');
            case 'chartBlacklist':
                return {
                    type: 'single',
                    labels: ['Unit Repossessed', 'Other Violations'],
                    values: [blacklistCount, 0]
                };
            case 'chartFunnel':      return getSingleSeriesDataset('workflowFunnel');
            case 'chartCaseAging':   return getSingleSeriesDataset('caseAging');
            case 'chartRequirements':return getSingleSeriesDataset('requirementsByStatus');
            case 'chartCasesStatus': return getSingleSeriesDataset('casesByStatus');
            case 'chartCasesType':   return getSingleSeriesDataset('casesByType');
            default: return null;
        }
    }

    function getDefaultMode(canvasId) {
        switch (canvasId) {
            case 'chartTrend': return 'line';
            case 'chartApplicants':
            case 'chartChannels':
            case 'chartApplications':
            case 'chartHousing':
            case 'chartISFPopulation':
            case 'chartISFOverall':
            case 'chartBlacklist':
            case 'chartRequirements':
            case 'chartCasesStatus':
            case 'chartCasesType':
                return 'donut';
            case 'chartBarangays':
            case 'chartFunnel':
            case 'chartCaseAging':
                return 'bar';
            default: return 'bar';
        }
    }

    var chartInstances = {};

    function switchChartMode(canvasId, mode) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return;
        var card = canvas.closest('.rep-card');
        if (!card) return;

        card.querySelectorAll('.rep-switch-btn').forEach(function (btn) {
            if (btn.getAttribute('data-mode') === mode) {
                btn.classList.add('is-active');
            } else {
                btn.classList.remove('is-active');
            }
        });

        if (chartInstances[canvasId]) {
            chartInstances[canvasId].destroy();
            chartInstances[canvasId] = null;
        }

        var canvasWrap = canvas.parentNode;
        var htmlContainer = card.querySelector('.rep-dynamic-container');
        var dataset = getStandardizedDataset(canvasId);

        if (!dataset) return;

        var htmlModes = [];
        if (htmlModes.indexOf(mode) >= 0) {
            canvasWrap.style.display = 'none';
            htmlContainer.style.display = '';
            renderHtmlFallback(htmlContainer, dataset, mode, canvasId);
        } else {
            htmlContainer.style.display = 'none';
            canvasWrap.style.display = '';
            canvas.style.display = '';
            renderChartJS(canvas, dataset, mode, canvasId);
        }
    }

    function renderChartJS(canvas, dataset, mode, canvasId) {
        var config = {
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        align: 'center',
                        labels: {
                            boxWidth: 10,
                            boxHeight: 10,
                            padding: 10,
                            font: { size: 12, family: 'Inter, sans-serif' },
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: '#0f172a',
                        padding: 10,
                        cornerRadius: 6
                    }
                }
            }
        };

        if (canvasId === 'chartTrend') {
            config.options.maintainAspectRatio = false;
            config.options.interaction = { mode: 'index', intersect: false };
        }

        if (dataset.type === 'single') {
            var total = sum(dataset.values);
            if (mode === 'line' || mode === 'area') {
                config.type = 'line';
                config.data = {
                    labels: dataset.labels,
                    datasets: [{
                        label: 'Count',
                        data: dataset.values,
                        borderColor: '#2F6FD6',
                        backgroundColor: mode === 'area' ? 'rgba(47, 111, 214, 0.15)' : 'transparent',
                        tension: 0.35,
                        fill: mode === 'area',
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        borderWidth: 2.5
                    }]
                };
                config.options.plugins.legend.display = false;
                config.options.scales = {
                    y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } },
                    x: { grid: { display: false } }
                };
            } else if (mode === 'bar') {
                var isHorizontal = ['chartBarangays', 'chartFunnel'].indexOf(canvasId) >= 0;
                config.type = 'bar';
                config.data = {
                    labels: dataset.labels,
                    datasets: [{
                        label: 'Count',
                        data: dataset.values,
                        backgroundColor: isHorizontal ? '#14B8A6' : dataset.labels.map(function (_, i) { return PALETTE[i % PALETTE.length]; }),
                        borderRadius: 4,
                        barThickness: dataset.labels.length > 8 ? 'flex' : 18
                    }]
                };
                config.options.indexAxis = isHorizontal ? 'y' : 'x';
                config.options.plugins.legend.display = false;
                config.options.scales = isHorizontal ? {
                    x: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } },
                    y: { grid: { display: false } }
                } : {
                    y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } },
                    x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 45 } }
                };
            } else if (mode === 'stacked') {
                config.type = 'bar';
                var isHorizontal = ['chartBarangays', 'chartFunnel'].indexOf(canvasId) >= 0;
                config.data = {
                    labels: isHorizontal ? ['Total Distribution'] : dataset.labels,
                    datasets: isHorizontal ? dataset.labels.map(function (lbl, i) {
                        return { label: lbl, data: [dataset.values[i]], backgroundColor: PALETTE[i % PALETTE.length] };
                    }) : [{
                        label: 'Value',
                        data: dataset.values,
                        backgroundColor: dataset.labels.map(function (_, i) { return PALETTE[i % PALETTE.length]; }),
                        borderRadius: 4
                    }]
                };
                config.options.indexAxis = isHorizontal ? 'y' : 'x';
                config.options.plugins.legend.display = isHorizontal;
                config.options.scales = {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } }
                };
            } else if (mode === 'pie' || mode === 'donut') {
                config.type = mode === 'pie' ? 'pie' : 'doughnut';
                config.data = {
                    labels: dataset.labels,
                    datasets: [{
                        data: dataset.values,
                        backgroundColor: dataset.labels.map(function (_, i) { return PALETTE[i % PALETTE.length]; }),
                        borderWidth: 2,
                        borderColor: '#ffffff',
                        hoverOffset: 6
                    }]
                };
                if (mode === 'donut') { config.options.cutout = '62%'; }
                config.options.maintainAspectRatio = true;
                config.options.aspectRatio = 1;
                config.options.plugins.legend.display = false;
                config.options.plugins.tooltip.callbacks = {
                    footer: function (items) {
                        var i = items[0] && items[0].dataIndex;
                        if (i == null || !total) return '';
                        var pct = Math.round((dataset.values[i] / total) * 1000) / 10;
                        return pct + '% of total';
                    }
                };
            }
        } else if (dataset.type === 'multi') {
            var total1 = sum(dataset.datasets[0].values);
            var total2 = sum(dataset.datasets[1].values);

            if (mode === 'line' || mode === 'area') {
                config.type = 'line';
                config.data = {
                    labels: dataset.labels,
                    datasets: dataset.datasets.map(function (ds, idx) {
                        return {
                            label: ds.label,
                            data: ds.values,
                            borderColor: ds.color,
                            backgroundColor: mode === 'area' ? hexToRgba(ds.color, ds.fillOpacity) : 'transparent',
                            yAxisID: idx === 0 ? 'y' : 'y1',
                            tension: 0.3,
                            fill: mode === 'area',
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            borderWidth: 2.5
                        };
                    })
                };
                config.options.scales = {
                    y:  { type: 'linear', position: 'left',  beginAtZero: true, title: { display: true, text: 'Applicants', font: { size: 10 } }, grid: { color: '#f1f5f9' }, ticks: { precision: 0 } },
                    y1: { type: 'linear', position: 'right', beginAtZero: true, title: { display: true, text: 'Uploads',    font: { size: 10 } }, grid: { drawOnChartArea: false }, ticks: { precision: 0 } },
                    x:  { grid: { color: '#f8fafc' } }
                };
            } else if (mode === 'bar') {
                config.type = 'bar';
                config.data = {
                    labels: dataset.labels,
                    datasets: dataset.datasets.map(function (ds) {
                        return { label: ds.label, data: ds.values, backgroundColor: ds.color, borderRadius: 4 };
                    })
                };
                config.options.scales = {
                    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#f1f5f9' } },
                    x: { grid: { display: false } }
                };
            } else if (mode === 'stacked') {
                config.type = 'bar';
                config.data = {
                    labels: dataset.labels,
                    datasets: dataset.datasets.map(function (ds) {
                        return { label: ds.label, data: ds.values, backgroundColor: ds.color };
                    })
                };
                config.options.scales = {
                    x: { stacked: true, grid: { display: false } },
                    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#f1f5f9' } }
                };
            } else if (mode === 'pie' || mode === 'donut') {
                config.type = mode === 'pie' ? 'pie' : 'doughnut';
                config.data = {
                    labels: dataset.labels,
                    datasets: dataset.datasets.map(function (ds) {
                        return {
                            label: ds.label,
                            data: ds.values,
                            backgroundColor: dataset.labels.map(function (_, i) {
                                return hexToRgba(ds.color, 0.4 + 0.6 * (i / dataset.labels.length));
                            }),
                            borderWidth: 2,
                            borderColor: '#ffffff',
                            hoverOffset: 6
                        };
                    })
                };
                if (mode === 'donut') { config.options.cutout = '45%'; }
                config.options.maintainAspectRatio = true;
                config.options.aspectRatio = 1;
            }
        }

        Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
        Chart.defaults.color = '#475569';

        var canvasWrapForLegend = canvas.parentNode;
        var stale = canvasWrapForLegend.querySelector('.custom-html-legend');
        if (stale) stale.remove();

        if ((mode === 'pie' || mode === 'donut') && dataset.type === 'single') {
            canvasWrapForLegend.style.display = 'flex';
            canvasWrapForLegend.style.alignItems = 'center';
            canvasWrapForLegend.style.justifyContent = 'center';
            canvasWrapForLegend.style.overflow = 'visible';
            canvas.style.flex = '0 0 auto';
            canvas.style.maxWidth = '55%';
            canvas.style.maxHeight = '100%';
            canvas.style.minWidth = '0';
        } else {
            canvasWrapForLegend.style.display = '';
            canvasWrapForLegend.style.alignItems = '';
            canvasWrapForLegend.style.justifyContent = '';
            canvasWrapForLegend.style.overflow = '';
            canvas.style.flex = '';
            canvas.style.maxWidth = '';
            canvas.style.maxHeight = '';
            canvas.style.minWidth = '';
        }

        chartInstances[canvasId] = new Chart(canvas, config);

        if (mode === 'pie' || mode === 'donut') {
            chartInstances[canvasId].resize();
        }

        if ((mode === 'pie' || mode === 'donut') && dataset.type === 'single') {
            var labels = dataset.labels;
            var legendEl = document.createElement('div');
            legendEl.className = 'custom-html-legend';
            legendEl.style.cssText = [
                'flex:1', 'min-width:0', 'display:flex', 'flex-direction:column',
                'gap:0.4rem', 'padding-left:0.6rem', 'overflow-y:auto',
                'max-height:240px', 'align-self:center'
            ].join(';') + ';';

            labels.forEach(function (lbl, i) {
                var row = document.createElement('div');
                row.style.cssText = 'display:flex;align-items:flex-start;gap:0.4rem;';

                var dot = document.createElement('div');
                dot.style.cssText = [
                    'width:9px', 'height:9px', 'border-radius:50%',
                    'flex-shrink:0', 'margin-top:0.18rem',
                    'background:' + PALETTE[i % PALETTE.length]
                ].join(';') + ';';

                var txt = document.createElement('span');
                var displayLbl = String(lbl || '');
                if (displayLbl.indexOf(' — ') !== -1) {
                    displayLbl = displayLbl.split(' — ')[0].trim();
                } else if (displayLbl.indexOf(' - ') !== -1 && /^option\s+[a-d]/i.test(displayLbl)) {
                    displayLbl = displayLbl.split(' - ')[0].trim();
                }

                var acronyms = ['CDRRMO', 'ISF', 'COMELEC', 'GK', 'ID', 'PHP', 'SMS', 'M2', 'M1', 'M4', 'CDRRM'];
                displayLbl = displayLbl.split(' ').map(function (word) {
                    var cleanWord = word.replace(/[^a-zA-Z0-9]/g, '');
                    if (acronyms.indexOf(cleanWord.toUpperCase()) >= 0) {
                        return word.replace(cleanWord, cleanWord.toUpperCase());
                    }
                    if (word === word.toUpperCase() && word.length > 1) {
                        return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
                    }
                    if (word.length > 0) {
                        return word.charAt(0).toUpperCase() + word.slice(1);
                    }
                    return word;
                }).join(' ');

                txt.textContent = displayLbl;
                txt.style.cssText = [
                    'font-size:0.7rem', 'color:#475569', 'line-height:1.35',
                    'white-space:normal', 'word-break:normal', 'overflow-wrap:break-word'
                ].join(';') + ';';

                row.appendChild(dot);
                row.appendChild(txt);
                legendEl.appendChild(row);
            });
            canvasWrapForLegend.appendChild(legendEl);
        }
    }

    function renderHtmlFallback(container, dataset, mode, canvasId) {
        container.innerHTML = '';
        var hasData = false;
        if (dataset.type === 'single') {
            hasData = dataset.values && dataset.values.length && sum(dataset.values) > 0;
        } else if (dataset.type === 'multi') {
            hasData = dataset.datasets && dataset.datasets.length &&
                (sum(dataset.datasets[0].values) > 0 || sum(dataset.datasets[1].values) > 0);
        }
        if (!hasData) {
            var emptyDiv = document.createElement('div');
            emptyDiv.className = 'chart-placeholder';
            emptyDiv.textContent = 'No records recorded to display';
            container.appendChild(emptyDiv);
            return;
        }

        if (mode === 'kpi') {
            var grid = document.createElement('div');
            grid.className = 'rep-kpi-card-grid';
            if (dataset.type === 'single') {
                var total = sum(dataset.values);
                dataset.labels.forEach(function (label, idx) {
                    var val = dataset.values[idx];
                    var pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
                    var card = document.createElement('div');
                    card.className = 'rep-kpi-card';
                    var rail = document.createElement('div');
                    rail.className = 'rep-kpi-card-rail';
                    rail.style.backgroundColor = PALETTE[idx % PALETTE.length];
                    card.appendChild(rail);
                    var labelP = document.createElement('p');
                    labelP.className = 'rep-kpi-card-label';
                    labelP.textContent = label;
                    card.appendChild(labelP);
                    var valP = document.createElement('p');
                    valP.className = 'rep-kpi-card-value';
                    valP.textContent = val;
                    card.appendChild(valP);
                    var pctSpan = document.createElement('span');
                    pctSpan.className = 'rep-kpi-card-percentage';
                    pctSpan.textContent = pct + '%';
                    card.appendChild(pctSpan);
                    grid.appendChild(card);
                });
            } else if (dataset.type === 'multi') {
                dataset.datasets.forEach(function (ds) {
                    var total = sum(ds.values);
                    var avg = (total / ds.values.length).toFixed(1);
                    var card = document.createElement('div');
                    card.className = 'rep-kpi-card';
                    var rail = document.createElement('div');
                    rail.className = 'rep-kpi-card-rail';
                    rail.style.backgroundColor = ds.color;
                    card.appendChild(rail);
                    var labelP = document.createElement('p');
                    labelP.className = 'rep-kpi-card-label';
                    labelP.textContent = ds.label + ' (Total)';
                    card.appendChild(labelP);
                    var valP = document.createElement('p');
                    valP.className = 'rep-kpi-card-value';
                    valP.textContent = total;
                    card.appendChild(valP);
                    var pctSpan = document.createElement('span');
                    pctSpan.className = 'rep-kpi-card-percentage';
                    pctSpan.textContent = 'Avg: ' + avg + '/mo';
                    card.appendChild(pctSpan);
                    grid.appendChild(card);
                });
                dataset.labels.forEach(function (month, mIdx) {
                    var val1 = dataset.datasets[0].values[mIdx] || 0;
                    var val2 = dataset.datasets[1].values[mIdx] || 0;
                    var card = document.createElement('div');
                    card.className = 'rep-kpi-card';
                    var rail = document.createElement('div');
                    rail.className = 'rep-kpi-card-rail';
                    rail.style.backgroundColor = '#64748b';
                    card.appendChild(rail);
                    var labelP = document.createElement('p');
                    labelP.className = 'rep-kpi-card-label';
                    labelP.textContent = month + ' Activity';
                    card.appendChild(labelP);
                    var valP = document.createElement('p');
                    valP.className = 'rep-kpi-card-value';
                    valP.style.fontSize = '1rem';
                    valP.innerHTML = '\uD83D\uDC64 ' + val1 + ' \u00A0\uD83D\uDCC2 ' + val2;
                    card.appendChild(valP);
                    var pctSpan = document.createElement('span');
                    pctSpan.className = 'rep-kpi-card-percentage';
                    pctSpan.textContent = 'Ratio: ' + (val1 > 0 ? (val2 / val1).toFixed(1) : val2) + ' doc/app';
                    card.appendChild(pctSpan);
                    grid.appendChild(card);
                });
            }
            container.appendChild(grid);
        } else if (mode === 'heatmap') {
            var grid = document.createElement('div');
            grid.className = 'rep-heatmap-grid';
            if (dataset.type === 'single') {
                var total = sum(dataset.values);
                var maxVal = Math.max.apply(null, dataset.values);
                dataset.labels.forEach(function (label, idx) {
                    var val = dataset.values[idx];
                    var pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
                    var cell = document.createElement('div');
                    cell.className = 'rep-heatmap-cell';
                    var baseHex = PALETTE[idx % PALETTE.length];
                    var weight = maxVal > 0 ? val / maxVal : 0;
                    cell.style.backgroundColor = hexToRgba(baseHex, 0.08 + 0.92 * weight);
                    cell.style.color = weight > 0.45 ? '#ffffff' : '#0f172a';
                    var labelDiv = document.createElement('div');
                    labelDiv.className = 'rep-heatmap-cell-label';
                    labelDiv.textContent = label;
                    cell.appendChild(labelDiv);
                    var metaDiv = document.createElement('div');
                    metaDiv.className = 'rep-heatmap-cell-meta';
                    var valDiv = document.createElement('span');
                    valDiv.className = 'rep-heatmap-cell-value';
                    valDiv.textContent = val;
                    metaDiv.appendChild(valDiv);
                    var pctDiv = document.createElement('span');
                    pctDiv.className = 'rep-heatmap-cell-pct';
                    pctDiv.textContent = pct + '%';
                    metaDiv.appendChild(pctDiv);
                    cell.appendChild(metaDiv);
                    grid.appendChild(cell);
                });
            } else if (dataset.type === 'multi') {
                var allValues = dataset.datasets[0].values.concat(dataset.datasets[1].values);
                var maxVal = Math.max.apply(null, allValues);
                dataset.labels.forEach(function (month, mIdx) {
                    dataset.datasets.forEach(function (ds) {
                        var val = ds.values[mIdx] || 0;
                        var weight = maxVal > 0 ? val / maxVal : 0;
                        var cell = document.createElement('div');
                        cell.className = 'rep-heatmap-cell';
                        cell.style.backgroundColor = hexToRgba(ds.color, 0.08 + 0.92 * weight);
                        cell.style.color = weight > 0.45 ? '#ffffff' : '#0f172a';
                        var labelDiv = document.createElement('div');
                        labelDiv.className = 'rep-heatmap-cell-label';
                        labelDiv.textContent = month + ' · ' + ds.label;
                        cell.appendChild(labelDiv);
                        var metaDiv = document.createElement('div');
                        metaDiv.className = 'rep-heatmap-cell-meta';
                        var valDiv = document.createElement('span');
                        valDiv.className = 'rep-heatmap-cell-value';
                        valDiv.textContent = val;
                        metaDiv.appendChild(valDiv);
                        cell.appendChild(metaDiv);
                        grid.appendChild(cell);
                    });
                });
            }
            container.appendChild(grid);
        } else if (mode === 'timeline') {
            var timeline = document.createElement('div');
            timeline.className = 'rep-timeline-layout';
            if (dataset.type === 'single') {
                var items = [];
                dataset.labels.forEach(function (lbl, i) {
                    items.push({ label: lbl, value: dataset.values[i], originalIndex: i });
                });
                var sequentialCharts = ['chartFunnel', 'chartCaseAging'];
                if (sequentialCharts.indexOf(canvasId) === -1) {
                    items.sort(function (a, b) { return b.value - a.value; });
                }
                var total = sum(dataset.values);
                items.forEach(function (item) {
                    var node = document.createElement('div');
                    node.className = 'rep-timeline-node';
                    var dot = document.createElement('div');
                    dot.className = 'rep-timeline-dot';
                    dot.style.borderColor = PALETTE[item.originalIndex % PALETTE.length];
                    node.appendChild(dot);
                    var content = document.createElement('div');
                    content.className = 'rep-timeline-content';
                    var labelGroup = document.createElement('div');
                    labelGroup.className = 'rep-timeline-label-group';
                    var labelNode = document.createElement('span');
                    labelNode.className = 'rep-timeline-node-label';
                    labelNode.textContent = item.label;
                    labelGroup.appendChild(labelNode);
                    var subNode = document.createElement('span');
                    subNode.className = 'rep-timeline-node-sub';
                    subNode.textContent = total > 0 ? ((item.value / total) * 100).toFixed(1) + '% contribution' : '0.0%';
                    labelGroup.appendChild(subNode);
                    content.appendChild(labelGroup);
                    var valNode = document.createElement('span');
                    valNode.className = 'rep-timeline-node-value';
                    valNode.textContent = item.value;
                    content.appendChild(valNode);
                    node.appendChild(content);
                    timeline.appendChild(node);
                });
            } else if (dataset.type === 'multi') {
                dataset.labels.forEach(function (month, mIdx) {
                    var val1 = dataset.datasets[0].values[mIdx] || 0;
                    var val2 = dataset.datasets[1].values[mIdx] || 0;
                    var node = document.createElement('div');
                    node.className = 'rep-timeline-node';
                    var dot = document.createElement('div');
                    dot.className = 'rep-timeline-dot';
                    dot.style.borderColor = '#10b981';
                    node.appendChild(dot);
                    var content = document.createElement('div');
                    content.className = 'rep-timeline-content';
                    var labelGroup = document.createElement('div');
                    labelGroup.className = 'rep-timeline-label-group';
                    var labelNode = document.createElement('span');
                    labelNode.className = 'rep-timeline-node-label';
                    labelNode.textContent = month + ' Monthly Rollout';
                    labelGroup.appendChild(labelNode);
                    var subNode = document.createElement('span');
                    subNode.className = 'rep-timeline-node-sub';
                    subNode.innerHTML = '\uD83D\uDC64 New: ' + val1 + ' \u00A0\u2022\u00A0 \uD83D\uDCC2 Uploads: ' + val2;
                    labelGroup.appendChild(subNode);
                    content.appendChild(labelGroup);
                    var valNode = document.createElement('span');
                    valNode.className = 'rep-timeline-node-value';
                    valNode.innerHTML = '<span style="color:#0ea5e9;">' + val1 + '</span> / <span style="color:#10b981;">' + val2 + '</span>';
                    content.appendChild(valNode);
                    node.appendChild(content);
                    timeline.appendChild(node);
                });
            }
            container.appendChild(timeline);
        }
    }

    // ── Bootstrap all rep-cards ────────────────────────────
    document.querySelectorAll('.rep-card').forEach(function (card) {
        var canvas = card.querySelector('canvas');
        if (!canvas) return;
        var canvasId = canvas.id;
        var dataset = getStandardizedDataset(canvasId);
        if (!dataset) {
            if (['chartRequirements', 'chartCasesStatus', 'chartCasesType'].indexOf(canvasId) >= 0) {
                card.style.display = 'none';
            }
            return;
        }

        var titleEl = card.querySelector('.rep-card-title');
        var subEl   = card.querySelector('.rep-card-sub');
        var header  = document.createElement('div');
        header.className = 'rep-card-header';
        var titleGroup = document.createElement('div');
        titleGroup.className = 'rep-card-title-group';

        if (titleEl) {
            titleEl.parentNode.insertBefore(header, titleEl);
            titleGroup.appendChild(titleEl);
            if (subEl) { titleGroup.appendChild(subEl); }
            header.appendChild(titleGroup);
        } else {
            card.insertBefore(header, card.firstChild);
            var prev = card.previousElementSibling;
            if (prev && prev.classList.contains('rep-section')) {
                var h2   = prev.querySelector('h2');
                var note = prev.querySelector('.rep-section-note');
                if (h2) {
                    var pTitle = document.createElement('p');
                    pTitle.className = 'rep-card-title';
                    pTitle.textContent = h2.textContent;
                    titleGroup.appendChild(pTitle);
                    if (note) {
                        var pSub = document.createElement('p');
                        pSub.className = 'rep-card-sub';
                        pSub.textContent = note.textContent;
                        titleGroup.appendChild(pSub);
                    }
                    header.appendChild(titleGroup);
                    prev.style.display = 'none';
                }
            }
        }

        var canvasWrap = canvas.parentNode;
        canvasWrap.style.position = 'relative';
        var htmlContainer = document.createElement('div');
        htmlContainer.className = 'rep-dynamic-container';
        htmlContainer.style.display = 'none';
        canvasWrap.parentNode.insertBefore(htmlContainer, canvasWrap.nextSibling);

        var defMode = getDefaultMode(canvasId);
        switchChartMode(canvasId, defMode);
    });

    // Expose switchChartMode globally so inline onclick handlers can call it
    window.switchChartMode = switchChartMode;
});
