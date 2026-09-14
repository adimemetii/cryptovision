document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('menu-toggle');
  const sidebar = document.getElementById('sidebar');
  if (toggle && sidebar) toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
  const input = document.getElementById('file-input');
  const zone = document.getElementById('drop-zone');
  const selected = document.getElementById('selected-file');
  if (input && zone) {
    const showFile = () => { selected.textContent = input.files.length ? `Selected: ${input.files[0].name}` : ''; };
    input.addEventListener('change', showFile);
    ['dragenter', 'dragover'].forEach(event => zone.addEventListener(event, e => { e.preventDefault(); zone.classList.add('dragover'); }));
    ['dragleave', 'drop'].forEach(event => zone.addEventListener(event, e => { e.preventDefault(); zone.classList.remove('dragover'); }));
    zone.addEventListener('drop', e => { if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; showFile(); } });
  }
  const entityColumn = document.getElementById('entity-column');
  const entityValue = document.getElementById('entity-value');
  if (entityColumn && entityValue) {
    entityColumn.addEventListener('change', () => {
      if (!entityColumn.value) { entityValue.innerHTML = '<option value="">All values</option>'; return; }
      const datasetId = entityColumn.dataset.datasetId;
      fetch(`/api/dataset/${datasetId}/values?column=${encodeURIComponent(entityColumn.value)}`)
        .then(response => response.json())
        .then(data => {
          entityValue.innerHTML = '<option value="">All values</option>';
          data.values.forEach(value => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = value;
            entityValue.appendChild(option);
          });
        }).catch(() => { entityValue.innerHTML = '<option value="">Unable to load values</option>'; });
    });
  }
});
