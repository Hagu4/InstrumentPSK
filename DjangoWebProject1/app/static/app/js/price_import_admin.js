(function () {
  "use strict";

  const bulkForm = document.querySelector("[data-price-bulk-form]");
  const tableBody = document.querySelector("[data-price-table-body]");
  if (!bulkForm || !tableBody) return;

  const selectAll = bulkForm.querySelector("[data-price-select-all]");
  const submitButton = bulkForm.querySelector("[data-price-bulk-submit]");
  const selectedCount = bulkForm.querySelector("[data-price-selected-count]");
  const status = bulkForm.querySelector("[data-price-bulk-status]");
  let busy = false;

  function rowCheckboxes() {
    return Array.from(tableBody.querySelectorAll("[data-price-row-select]"));
  }

  function updateSelection() {
    const checkboxes = rowCheckboxes();
    const checked = checkboxes.filter((checkbox) => checkbox.checked);
    selectedCount.textContent = String(checked.length);
    submitButton.disabled = busy || checked.length === 0;
    selectAll.disabled = busy || checkboxes.length === 0;
    selectAll.checked = checkboxes.length > 0 && checked.length === checkboxes.length;
    selectAll.indeterminate = checked.length > 0 && checked.length < checkboxes.length;
  }

  function showStatus(message, kind) {
    status.textContent = message || "";
    status.classList.toggle("is-error", kind === "error");
    status.classList.toggle("is-success", kind === "success");
  }

  function updateSummary(summary) {
    Object.entries(summary || {}).forEach(([key, value]) => {
      const target = document.querySelector(`[data-price-summary="${key}"]`);
      if (target) target.textContent = String(value);
    });
  }

  function updateImportState(payload) {
    const statusLabel = document.querySelector("[data-price-import-status]");
    const applyAction = document.querySelector("[data-price-apply-action]");
    const confirmAction = document.querySelector("[data-price-confirm-action]");
    if (statusLabel && payload.status_display) {
      statusLabel.textContent = payload.status_display;
    }
    if (applyAction) applyAction.hidden = payload.status !== "ready";
    if (confirmAction) {
      confirmAction.hidden = !(
        payload.status === "draft" &&
        payload.summary &&
        payload.summary.anomalies > 0
      );
    }
  }

  function cleanDividers() {
    tableBody.querySelectorAll(".price-section-divider").forEach((divider) => {
      let sibling = divider.nextElementSibling;
      let hasRows = false;
      while (sibling && !sibling.classList.contains("price-section-divider")) {
        if (sibling.matches("[data-price-row]")) {
          hasRows = true;
          break;
        }
        sibling = sibling.nextElementSibling;
      }
      if (!hasRows) divider.remove();
    });
  }

  function ensureEmptyMessage() {
    if (tableBody.querySelector("[data-price-row]")) return;
    if (tableBody.querySelector("[data-price-empty-row]")) return;
    tableBody.insertAdjacentHTML(
      "beforeend",
      '<tr data-price-empty-row><td colspan="11">Изменений цен для просмотра нет.</td></tr>'
    );
  }

  function removeRows(rowIds) {
    const rows = (rowIds || [])
      .map((rowId) => tableBody.querySelector(`[data-price-row][data-row-id="${rowId}"]`))
      .filter(Boolean);
    rows.forEach((row) => row.classList.add("is-removing"));
    window.setTimeout(() => {
      rows.forEach((row) => row.remove());
      cleanDividers();
      ensureEmptyMessage();
      updateSelection();
    }, 170);
  }

  async function send(form) {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    let payload;
    try {
      payload = await response.json();
    } catch (_error) {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.error || "Не удалось убрать товары. Попробуйте ещё раз.");
    }
    return payload;
  }

  async function submitRemoval(form, button) {
    if (busy) return;
    busy = true;
    if (button) button.disabled = true;
    showStatus("Сохраняем изменения…");
    updateSelection();
    try {
      const payload = await send(form);
      updateSummary(payload.summary);
      updateImportState(payload);
      removeRows(payload.removed_ids);
      showStatus(`Убрано из обновления: ${payload.removed_ids.length}.`, "success");
    } catch (error) {
      showStatus(error.message, "error");
    } finally {
      busy = false;
      if (button) button.disabled = false;
      updateSelection();
    }
  }

  selectAll.addEventListener("change", () => {
    rowCheckboxes().forEach((checkbox) => {
      checkbox.checked = selectAll.checked;
    });
    updateSelection();
  });

  tableBody.addEventListener("change", (event) => {
    if (event.target.matches("[data-price-row-select]")) updateSelection();
  });

  bulkForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!rowCheckboxes().some((checkbox) => checkbox.checked)) return;
    submitRemoval(bulkForm, submitButton);
  });

  tableBody.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-price-row-remove-form]");
    if (!form) return;
    event.preventDefault();
    submitRemoval(form, form.querySelector("button[type=submit]"));
  });

  updateSelection();
})();
