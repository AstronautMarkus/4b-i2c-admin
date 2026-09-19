document.addEventListener("submit", (event) => {
    const form = event.target;
    if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
    }
});

// ---------------------------------------------------------------------- //
// Playlist editor: agregar / quitar / reordenar (drag & drop)
// ---------------------------------------------------------------------- //

function makePlaylistRow(moduleId, title, icon, duration) {
    const li = document.createElement("li");
    li.className = "playlist-row";
    li.dataset.moduleId = moduleId;
    li.innerHTML = `
        <span class="drag-handle"><i class="fas fa-grip-vertical"></i></span>
        <span class="row-icon">${icon || ""}</span>
        <span class="row-title">${title}</span>
        <input type="hidden" name="module_id" value="${moduleId}">
        <label class="row-duration">
            <input type="number" name="duration_seconds" min="1" value="${duration}" required> s
        </label>
        <button type="button" class="btn btn-sm btn-outline-secondary" data-action="remove" title="Quitar">
            <i class="fas fa-xmark"></i>
        </button>
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
        const button = event.target.closest('button[data-action="remove"]');
        if (!button) return;
        button.closest(".playlist-row").remove();
        updateEmptyHint();
    });

    if (window.Sortable) {
        window.Sortable.create(rowsList, {
            handle: ".drag-handle",
            animation: 150,
            ghostClass: "sortable-ghost",
        });
    }

    updateEmptyHint();
}

// ---------------------------------------------------------------------- //
// Dashboard: donuts (paleta validada por el skill de dataviz, orden fijo)
// ---------------------------------------------------------------------- //

const CATEGORICAL_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const STATUS_COLORS = { "Válidos": "#0ca30c", "Inválidos": "#d03b3b" };
const MAX_SLICES = CATEGORICAL_COLORS.length;

function foldIntoOther(entries) {
    if (entries.length <= MAX_SLICES) return entries;
    const head = entries.slice(0, MAX_SLICES - 1);
    const otherTotal = entries.slice(MAX_SLICES - 1).reduce((sum, [, v]) => sum + v, 0);
    return [...head, ["Otros", otherTotal]];
}

function renderLegend(container, labels, colors, values, suffix) {
    if (!container) return;
    container.innerHTML = labels
        .map((label, i) => `
            <span><span class="swatch" style="background:${colors[i]}"></span>${label}: ${values[i]}${suffix || ""}</span>
        `)
        .join("");
}

function renderDonut(canvasId, legendId, rawEntries, { colorFn, suffix } = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !rawEntries || !rawEntries.length) return;

    const entries = foldIntoOther(rawEntries);
    const labels = entries.map(([label]) => label);
    const values = entries.map(([, value]) => value);
    const colors = colorFn
        ? labels.map((label) => colorFn(label))
        : labels.map((_, i) => CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length]);

    new Chart(canvas, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderColor: "#ffffff",
                borderWidth: 2,
            }],
        },
        options: {
            cutout: "62%",
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ` ${ctx.label}: ${ctx.parsed}${suffix || ""}`,
                    },
                },
            },
        },
    });

    renderLegend(document.getElementById(legendId), labels, colors, values, suffix);
}

function initDashboardCharts() {
    const data = window.DASHBOARD_CHARTS;
    if (!data || typeof Chart === "undefined") return;

    renderDonut("chart-duration", "legend-duration", data.duration, { suffix: "s" });
    renderDonut("chart-validity", "legend-validity", data.validity, {
        colorFn: (label) => STATUS_COLORS[label] || "#999999",
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initPlaylistEditor();
    initDashboardCharts();
});
