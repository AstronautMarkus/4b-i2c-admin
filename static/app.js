document.addEventListener("submit", (event) => {
    const form = event.target;
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
    }
});

function makePlaylistRow(moduleId, title, icon, duration) {
    const li = document.createElement("li");
    li.className = "playlist-row";
    li.dataset.moduleId = moduleId;
    li.innerHTML = `
        <span class="row-icon">${icon || ""}</span>
        <span class="row-title">${title}</span>
        <input type="hidden" name="module_id" value="${moduleId}">
        <label class="row-duration">
            <input type="number" name="duration_seconds" min="1" value="${duration}" required> s
        </label>
        <span class="row-actions">
            <button type="button" class="btn-icon" data-action="up" title="Subir">↑</button>
            <button type="button" class="btn-icon" data-action="down" title="Bajar">↓</button>
            <button type="button" class="btn-icon" data-action="remove" title="Quitar">✕</button>
        </span>
    `;
    return li;
}

function initPlaylistEditor() {
    const rowsList = document.getElementById("playlist-rows");
    if (!rowsList) return;

    const emptyHint = document.getElementById("empty-hint");
    const updateEmptyHint = () => {
        if (emptyHint) emptyHint.hidden = rowsList.children.length > 0;
    };

    document.querySelectorAll(".add-module-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const { moduleId, title, icon, defaultDuration } = btn.dataset;
            rowsList.appendChild(makePlaylistRow(moduleId, title, icon, defaultDuration || 5));
            updateEmptyHint();
        });
    });

    rowsList.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        const row = button.closest(".playlist-row");

        switch (button.dataset.action) {
            case "remove":
                row.remove();
                break;
            case "up":
                if (row.previousElementSibling) rowsList.insertBefore(row, row.previousElementSibling);
                break;
            case "down":
                if (row.nextElementSibling) rowsList.insertBefore(row.nextElementSibling, row);
                break;
        }
        updateEmptyHint();
    });

    updateEmptyHint();
}

document.addEventListener("DOMContentLoaded", initPlaylistEditor);
