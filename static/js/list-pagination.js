/**
 * Client-side table + mobile card pagination (field portal lists).
 */
(function (global) {
    'use strict';

    function initListPagination(options) {
        if (!options || !options.rowSelector) return null;

        var pageSize = options.pageSize || 5;
        var currentPage = 1;
        var rowSelector = options.rowSelector;
        var cardSelector = options.cardSelector || null;
        var infoEl = resolveEl(options.infoEl);
        var prevBtn = resolveEl(options.prevBtn);
        var nextBtn = resolveEl(options.nextBtn);
        var pageIndicator = resolveEl(options.pageIndicator);
        var renumberRows = options.renumberRows !== false;

        function resolveEl(el) {
            if (!el) return null;
            return typeof el === 'string' ? document.getElementById(el) : el;
        }

        function getRows() {
            return Array.from(document.querySelectorAll(rowSelector)).filter(function (row) {
                return !row.hasAttribute('data-pagination-skip');
            });
        }

        function getCards() {
            return cardSelector ? Array.from(document.querySelectorAll(cardSelector)) : [];
        }

        function renumberCardOrder(orderEl, num) {
            if (!orderEl) return;
            var text = (orderEl.textContent || '').trim();
            if (/^#/.test(text)) {
                orderEl.textContent = '#' + num;
            } else if (/^Task\s*#/i.test(text)) {
                orderEl.textContent = 'Task #' + num;
            } else if (/^Verification\s*#/i.test(text)) {
                orderEl.textContent = 'Verification #' + num;
            } else {
                orderEl.textContent = String(num);
            }
        }

        function render(resetPage) {
            if (resetPage) currentPage = 1;

            var rows = getRows();
            var cards = getCards();
            var total = rows.length;
            var totalPages = Math.max(1, Math.ceil(total / pageSize));
            currentPage = Math.min(Math.max(1, currentPage), totalPages);

            var start = (currentPage - 1) * pageSize;
            var end = start + pageSize;

            rows.forEach(function (row, i) {
                row.style.display = (i >= start && i < end) ? '' : 'none';
            });

            cards.forEach(function (card, i) {
                card.style.display = (i >= start && i < end) ? '' : 'none';
            });

            if (renumberRows) {
                rows.slice(start, end).forEach(function (row, idx) {
                    var first = row.querySelector('td:first-child');
                    if (first) first.textContent = String(start + idx + 1);
                });
                cards.slice(start, end).forEach(function (card, idx) {
                    renumberCardOrder(card.querySelector('.m-card-visit-order'), start + idx + 1);
                });
            }

            var displayStart = total === 0 ? 0 : start + 1;
            var displayEnd = total === 0 ? 0 : Math.min(end, total);

            if (infoEl) {
                infoEl.textContent = total === 0
                    ? 'Showing 0-0 of 0'
                    : 'Showing ' + displayStart + '-' + displayEnd + ' of ' + total;
            }
            if (pageIndicator) {
                pageIndicator.textContent = 'Page ' + currentPage + ' of ' + totalPages;
            }
            if (prevBtn) {
                var prevOff = currentPage <= 1 || total === 0;
                prevBtn.disabled = prevOff;
                prevBtn.classList.toggle('is-disabled', prevOff);
            }
            if (nextBtn) {
                var nextOff = currentPage >= totalPages || total === 0;
                nextBtn.disabled = nextOff;
                nextBtn.classList.toggle('is-disabled', nextOff);
            }
        }

        if (prevBtn) {
            prevBtn.addEventListener('click', function () {
                if (currentPage > 1) {
                    currentPage -= 1;
                    render(false);
                }
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', function () {
                var totalPages = Math.max(1, Math.ceil(getRows().length / pageSize));
                if (currentPage < totalPages) {
                    currentPage += 1;
                    render(false);
                }
            });
        }

        render(false);

        return {
            refresh: function () { render(true); },
            setPage: function (page) {
                currentPage = page;
                render(false);
            }
        };
    }

    global.initListPagination = initListPagination;
})(typeof window !== 'undefined' ? window : this);
