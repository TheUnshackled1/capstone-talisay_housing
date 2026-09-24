/**
 * Live sync for Module 5 case desk lists (field ↔ second/fourth member).
 * Polls desk-feed API and uses BroadcastChannel so open tabs update without reload.
 */
(function (global) {
    'use strict';

    var CHANNEL_NAME = 'tha-case-desk-sync-v1';
    var pollTimer = null;
    var lastVersion = null;
    var paused = false;
    var inFlight = false;
    var drawerInFlight = {};

    function cfg() {
        return global.CASE_DESK_SYNC || null;
    }

    function csrfToken() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function filterParams() {
        var q = (document.getElementById('searchInput')?.value || '').trim();
        var type = document.getElementById('typeFilter')?.value || 'all';
        var params = new URLSearchParams();
        if (q) params.set('q', q);
        if (type && type !== 'all') params.set('type', type);
        return params;
    }

    function isModalBlockingSync() {
        var ids = ['caseModal', 'newCaseModal', 'settledLogModal'];
        for (var i = 0; i < ids.length; i++) {
            var el = document.getElementById(ids[i]);
            if (el && el.style.display === 'flex') return true;
        }
        return false;
    }

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = String(text);
    }

    function markDrawersStale() {
        ['caseDeskResolvedDrawerScroll', 'caseDeskSettledDrawerScroll', 'caseDeskPendingDrawerScroll']
            .forEach(function (id) {
                var el = document.getElementById(id);
                if (!el) return;
                el.setAttribute('data-drawer-loaded', '0');
            });
    }

    function applyFeed(data) {
        var html = data.html || {};
        var tbody = document.getElementById('caseDeskTableBody');
        if (tbody && html.table_body != null) {
            tbody.innerHTML = html.table_body;
        }
        var cards = document.getElementById('caseDeskMobileCards');
        if (cards && html.mobile_cards != null) {
            cards.innerHTML = html.mobile_cards;
        }
        // Drawers are lazy — invalidate on list change; do not replace until opened.
        if (data.drawers_stale) {
            markDrawersStale();
        }
        if (html.settled_drawer != null) {
            var settledScroll = document.getElementById('caseDeskSettledDrawerScroll');
            if (settledScroll) {
                settledScroll.innerHTML = html.settled_drawer;
                settledScroll.setAttribute('data-drawer-loaded', '1');
            }
        }
        if (html.resolved_drawer != null) {
            var resolvedScroll = document.getElementById('caseDeskResolvedDrawerScroll');
            if (resolvedScroll) {
                resolvedScroll.innerHTML = html.resolved_drawer;
                resolvedScroll.setAttribute('data-drawer-loaded', '1');
            }
        }
        if (html.pending_drawer != null) {
            var pendingScroll = document.getElementById('caseDeskPendingDrawerScroll');
            if (pendingScroll) {
                pendingScroll.innerHTML = html.pending_drawer;
                pendingScroll.setAttribute('data-drawer-loaded', '1');
            }
        }

        if (data.desk_row_count != null) {
            setText('caseDeskTotalCount', data.desk_row_count);
        }
        var sc = data.status_counts || {};
        setText('caseDeskKpiPending', sc.pending_review != null ? sc.pending_review : '');
        setText('caseDeskKpiResolved', sc.resolved != null ? sc.resolved : '');
        if (data.desk_row_count != null) {
            setText('caseDeskKpiSettled', data.desk_row_count);
        }
        setText('caseDeskResolvedDrawerSubtitle', (sc.resolved || 0) + ' case' + ((sc.resolved || 0) === 1 ? '' : 's') + ' marked resolved');
        setText('caseDeskSettledDrawerSubtitle', (data.settled_on_site_count || 0) + ' incident log' + ((data.settled_on_site_count || 0) === 1 ? '' : 's') + ' — handled without a formal case');
        if (sc.pending_review != null) {
            setText('caseDeskPendingDrawerSubtitle', (sc.pending_review || 0) + ' case' + ((sc.pending_review || 0) === 1 ? '' : 's') + ' pending review');
        }

        if (global.caseDeskPaginationApi && typeof global.caseDeskPaginationApi.refresh === 'function') {
            global.caseDeskPaginationApi.refresh();
        }
    }

    function scrollElForPart(part) {
        if (part === 'resolved') return document.getElementById('caseDeskResolvedDrawerScroll');
        if (part === 'settled') return document.getElementById('caseDeskSettledDrawerScroll');
        if (part === 'pending') return document.getElementById('caseDeskPendingDrawerScroll');
        return null;
    }

    function loadDrawerPart(part) {
        var config = cfg();
        var scroll = scrollElForPart(part);
        if (!config || !scroll || !part) return Promise.resolve();
        if (scroll.getAttribute('data-drawer-loaded') === '1') return Promise.resolve();
        if (drawerInFlight[part]) return drawerInFlight[part];

        var params = filterParams();
        params.set('part', part);
        var url = '/cases/' + encodeURIComponent(config.position) + '/desk-feed/';
        if (params.toString()) url += '?' + params.toString();

        scroll.innerHTML = '<p class="cases-resolved-drawer-empty">Loading…</p>';
        drawerInFlight[part] = fetch(url, {
            headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(function (r) {
                if (!r.ok) throw new Error('drawer ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data.success) return;
                var html = (data.html || {})[part + '_drawer'];
                if (html != null) {
                    scroll.innerHTML = html;
                    scroll.setAttribute('data-drawer-loaded', '1');
                }
                if (data.status_counts) {
                    var sc = data.status_counts;
                    setText('caseDeskKpiResolved', sc.resolved != null ? sc.resolved : '');
                    setText('caseDeskKpiPending', sc.pending_review != null ? sc.pending_review : '');
                    setText('caseDeskResolvedDrawerSubtitle', (sc.resolved || 0) + ' case' + ((sc.resolved || 0) === 1 ? '' : 's') + ' marked resolved');
                    if (sc.pending_review != null) {
                        setText('caseDeskPendingDrawerSubtitle', (sc.pending_review || 0) + ' case' + ((sc.pending_review || 0) === 1 ? '' : 's') + ' pending review');
                    }
                }
                if (data.settled_on_site_count != null) {
                    setText('caseDeskSettledDrawerSubtitle', (data.settled_on_site_count || 0) + ' incident log' + ((data.settled_on_site_count || 0) === 1 ? '' : 's') + ' — handled without a formal case');
                }
            })
            .catch(function () {
                scroll.innerHTML = '<p class="cases-resolved-drawer-empty">Could not load. Close and try again.</p>';
            })
            .finally(function () {
                drawerInFlight[part] = null;
            });
        return drawerInFlight[part];
    }

    function refreshDeskList(reason) {
        var config = cfg();
        if (!config || paused || inFlight) return Promise.resolve();
        if (document.hidden && reason === 'poll') return Promise.resolve();
        if (isModalBlockingSync() && reason === 'poll') return Promise.resolve();

        var params = filterParams();
        // Send current version so server can short-circuit with a ~200-byte
        // "unchanged" response instead of rendering HTML templates.
        if (lastVersion) params.set('v', lastVersion);
        var url = '/cases/' + encodeURIComponent(config.position) + '/desk-feed/';
        if (params.toString()) url += '?' + params.toString();

        inFlight = true;
        return fetch(url, {
            headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(function (r) {
                if (!r.ok) throw new Error('feed ' + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data.success) return;
                // Server confirmed no change — nothing to do.
                if (data.unchanged) return;
                if (lastVersion === data.version) return;
                lastVersion = data.version;
                applyFeed(data);
            })
            .catch(function () { /* silent on poll */ })
            .finally(function () {
                inFlight = false;
            });
    }

    function notifyPeers() {
        try {
            var bc = new global.BroadcastChannel(CHANNEL_NAME);
            bc.postMessage({ type: 'desk-changed', at: Date.now() });
            bc.close();
        } catch (e) { /* unsupported */ }
    }

    function onLocalChange() {
        notifyPeers();
        lastVersion = null;
        markDrawersStale();
        return refreshDeskList('local');
    }

    function onFilterChange() {
        lastVersion = null;
        markDrawersStale();
        return refreshDeskList('filter');
    }

    function startPolling() {
        var config = cfg();
        if (!config) return;
        stopPolling();
        var ms = config.pollMs || 15000;
        pollTimer = global.setInterval(function () {
            refreshDeskList('poll');
        }, ms);
    }

    function stopPolling() {
        if (pollTimer) {
            global.clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function init() {
        var config = cfg();
        if (!config) return;
        lastVersion = config.initialVersion || null;

        try {
            var bc = new global.BroadcastChannel(CHANNEL_NAME);
            bc.onmessage = function (ev) {
                if (ev.data && ev.data.type === 'desk-changed') {
                    lastVersion = null;
                    refreshDeskList('broadcast');
                }
            };
        } catch (e) { /* ignore */ }

        document.addEventListener('visibilitychange', function () {
            if (!document.hidden) refreshDeskList('visible');
        });

        var searchInput = document.getElementById('searchInput');
        var typeFilter = document.getElementById('typeFilter');
        if (searchInput) {
            var searchTimer = null;
            searchInput.addEventListener('input', function () {
                global.clearTimeout(searchTimer);
                searchTimer = global.setTimeout(onFilterChange, 300);
            });
        }
        if (typeFilter) {
            typeFilter.addEventListener('change', onFilterChange);
        }

        startPolling();
    }

    global.CaseDeskSync = {
        refresh: refreshDeskList,
        notifyChange: onLocalChange,
        loadDrawer: loadDrawerPart,
        start: startPolling,
        stop: stopPolling,
        pause: function () { paused = true; },
        resume: function () { paused = false; },
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(typeof window !== 'undefined' ? window : this);
