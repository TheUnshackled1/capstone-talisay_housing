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
        var settledScroll = document.getElementById('caseDeskSettledDrawerScroll');
        if (settledScroll && html.settled_drawer != null) {
            settledScroll.innerHTML = html.settled_drawer;
        }
        var resolvedScroll = document.getElementById('caseDeskResolvedDrawerScroll');
        if (resolvedScroll && html.resolved_drawer != null) {
            resolvedScroll.innerHTML = html.resolved_drawer;
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

        if (global.caseDeskPaginationApi && typeof global.caseDeskPaginationApi.refresh === 'function') {
            global.caseDeskPaginationApi.refresh();
        }
    }

    function refreshDeskList(reason) {
        var config = cfg();
        if (!config || paused || inFlight) return Promise.resolve();
        if (document.hidden && reason === 'poll') return Promise.resolve();
        if (isModalBlockingSync() && reason === 'poll') return Promise.resolve();

        var params = filterParams();
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
        return refreshDeskList('local');
    }

    function startPolling() {
        var config = cfg();
        if (!config) return;
        stopPolling();
        var ms = config.pollMs || 4000;
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

        startPolling();
    }

    global.CaseDeskSync = {
        refresh: refreshDeskList,
        notifyChange: onLocalChange,
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
