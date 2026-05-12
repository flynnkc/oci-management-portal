(function () {
  const searchInput = document.getElementById('resourceSearch');
  const filterSelect = document.getElementById('resourceFilter');
  const table = document.getElementById('resourcesTable');
  const noResults = document.getElementById('noResults');

  if (!searchInput || !filterSelect || !table) return;

  const rows = Array.from(table.querySelectorAll('tbody tr'));

  function applyFilter() {
    const query = searchInput.value.trim().toLowerCase();
    const filter = filterSelect.value;
    let visibleCount = 0;

    rows.forEach((row) => {
      const name = row.dataset.resourceName || '';
      const status = row.dataset.status || 'neither';

      const matchesSearch = !query || name.includes(query);
      const matchesFilter = filter === 'all' || status === filter;

      const show = matchesSearch && matchesFilter;
      row.classList.toggle('d-none', !show);

      if (show) visibleCount++;
    });

    noResults.classList.toggle('d-none', visibleCount !== 0);
    table.classList.toggle('d-none', visibleCount === 0);
  }

  searchInput.addEventListener('input', applyFilter);
  filterSelect.addEventListener('change', applyFilter);

  applyFilter();
})();