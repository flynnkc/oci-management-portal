(function () {
  const forceDeleteWarningText =
    'This resource bypasses garbage collection and will be deleted immediately.';

  function setCurrentYear() {
    const el = document.getElementById('currentYear');
    if (el) {
      el.textContent = new Date().getFullYear();
    }
  }

  function getModal(selector) {
    try {
      return document.querySelector(selector);
    } catch (err) {
      console.warn('Force delete warning selector error', err);
      return null;
    }
  }

  function handleForceDeleteWarning(trigger) {
    const modalId = trigger.getAttribute('data-bs-target');
    if (!modalId) {
      return;
    }

    const modalEl = getModal(modalId);
    if (!modalEl) {
      return;
    }

    const alertBox = modalEl.querySelector('[data-force-delete-warning]');
    if (!alertBox) {
      return;
    }

    if (trigger.dataset.forceDelete === 'true') {
      alertBox.textContent = forceDeleteWarningText;
      alertBox.classList.remove('d-none');
    } else {
      alertBox.textContent = '';
      alertBox.classList.add('d-none');
    }
  }

  function parseCurrency(text) {
    const numeric = Number(String(text || '').replace(/[^0-9.-]/g, ''));
    return Number.isFinite(numeric) ? numeric : 0;
  }

  function formatCurrency(value) {
    return '$' + Number(value || 0).toFixed(2);
  }

  function ensureNoResultsState() {
    const inventory = document.getElementById('inventory');
    if (!inventory) {
      return;
    }

    const remainingCards = inventory.querySelectorAll('form.card[id^="card-"]');
    const existingMessage = inventory.querySelector('[data-snooze-empty-state]');

    if (remainingCards.length === 0 && !existingMessage) {
      const message = document.createElement('h1');
      message.className = 'display-6 text-center';
      message.setAttribute('data-snooze-empty-state', 'true');
      message.textContent = 'No results';
      inventory.appendChild(message);
    } else if (remainingCards.length > 0 && existingMessage) {
      existingMessage.remove();
    }
  }

  function handleSnooze(trigger) {
    const cardId = trigger.getAttribute('data-card-id');
    const card = cardId ? document.getElementById(cardId) : trigger.closest('form.card');
    if (!card) {
      return;
    }

    const totalCountEl = document.getElementById('total-resource-count');
    if (totalCountEl) {
      const currentCount = parseInt(totalCountEl.textContent || '0', 10);
      const nextCount = Number.isFinite(currentCount)
        ? Math.max(0, currentCount - 1)
        : 0;
      totalCountEl.textContent = String(nextCount);
    }

    const totalCostEl = document.getElementById('total-current-cost');
    if (totalCostEl) {
      const currentTotal = parseCurrency(totalCostEl.textContent);
      const cardCost = Number(card.dataset.cost || 0);
      totalCostEl.textContent = formatCurrency(Math.max(0, currentTotal - cardCost));
    }

    card.remove();
    ensureNoResultsState();
  }

  function setSearchQueryMode(trigger) {
    const mode = document.getElementById('search-query-mode');
    if (mode) {
      mode.value = trigger.dataset.searchQueryMode;
    }
  }

  function closestTarget(event, selector) {
    return event.target && event.target.closest ? event.target.closest(selector) : null;
  }

  function exportCsv() {
    const params = new URLSearchParams();
    const filter = document.getElementById('filter');
    const region = document.getElementById('region_filter');
    const query = document.getElementById('search-query-input');
    const queryMode = document.getElementById('search-query-mode');

    if (filter && filter.value) {
      params.set('resource_type', filter.value);
    }
    if (region && region.value) {
      params.set('region', region.value);
    }
    if (queryMode && queryMode.value) {
      params.set('query_mode', queryMode.value);
    }
    if (query && query.value.trim()) {
      params.set('search_query', query.value.trim());
    }

    window.location.href = '/export.csv?' + params.toString();
  }

  function applyCostBadgeData(root) {
    const scope = root && root.querySelectorAll ? root : document;
    const badges = [];

    if (scope.matches && scope.matches('[data-card-cost][data-card-id]')) {
      badges.push(scope);
    }
    scope.querySelectorAll('[data-card-cost][data-card-id]').forEach((badge) => {
      badges.push(badge);
    });

    badges.forEach((badge) => {
      const card = document.getElementById(badge.dataset.cardId);
      if (card) {
        card.dataset.cost = badge.dataset.cardCost || 0;
      }
    });
  }

  document.addEventListener(
    'click',
    function (event) {
      const searchModeTrigger = closestTarget(event, '[data-search-query-mode]');
      if (searchModeTrigger) {
        setSearchQueryMode(searchModeTrigger);
      }
    },
    true
  );

  document.addEventListener('click', function (event) {
    const forceDeleteTrigger = closestTarget(event, '[data-force-delete-check]');
    if (forceDeleteTrigger) {
      handleForceDeleteWarning(forceDeleteTrigger);
    }

    const snoozeTrigger = closestTarget(event, '[data-snooze-card]');
    if (snoozeTrigger) {
      handleSnooze(snoozeTrigger);
    }

    const exportButton = closestTarget(event, '[data-export-csv]');
    if (exportButton) {
      exportCsv();
    }
  });

  document.body.addEventListener('htmx:afterSwap', function (event) {
    applyCostBadgeData(event.target);
  });
  document.body.addEventListener('htmx:oobAfterSwap', function (event) {
    applyCostBadgeData(event.target);
  });

  setCurrentYear();
  applyCostBadgeData(document);
})();
