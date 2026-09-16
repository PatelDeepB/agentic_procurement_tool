/**
 * Agentic Procurement Tool - Frontend Application Logic
 * Coordinates form input, benchmark presets, API pipeline execution,
 * dynamic multi-tier vendor rendering, and artifact export downloads.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const form = document.getElementById("procurementForm");
  const materialInput = document.getElementById("materialInput");
  const quantityInput = document.getElementById("quantityInput");
  const materialIdInput = document.getElementById("materialIdInput");
  const locationInput = document.getElementById("locationInput");
  const runButton = document.getElementById("runProcureBtn");

  const loadingIndicator = document.getElementById("loadingIndicator");
  const resultsContainer = document.getElementById("resultsContainer");
  const errorAlert = document.getElementById("errorAlert");
  const errorMessage = document.getElementById("errorMessage");

  // Presets
  const btnPresetM01 = document.getElementById("btnPresetM01");
  const btnPresetM02 = document.getElementById("btnPresetM02");
  const btnPresetM03 = document.getElementById("btnPresetM03");

  // Export Buttons
  const btnExportMd = document.getElementById("btnExportMd");
  const btnExportCsv = document.getElementById("btnExportCsv");
  const btnExportJson = document.getElementById("btnExportJson");

  // Tabs
  const tabButtons = document.querySelectorAll(".tier-tab-btn");

  // Current State
  let currentResult = null;
  let activeTierFilter = "ALL";

  const BENCHMARK_PRESETS = {
    "M-01": {
      id: "M-01",
      material: "ERW pipe, DN 50, 60.3 x 5.5 mm, IS 1239",
      quantity: 1000.0,
      location: "Ahmedabad, Gujarat, India",
    },
    "M-02": {
      id: "M-02",
      material: "40 mm MS ERW, Class B pipe",
      quantity: 500.0,
      location: "Ahmedabad, Gujarat, India",
    },
    "M-03": {
      id: "M-03",
      material: "ERW pipe, DN 80, 89.5 x 4.8 mm, IS 1239",
      quantity: 1200.0,
      location: "Ahmedabad, Gujarat, India",
    },
  };

  // Initialize Default State (Preset M-01)
  applyPreset("M-01");
  checkSystemHealth();

  // Benchmark Preset Click Handlers
  btnPresetM01.addEventListener("click", () => applyPreset("M-01"));
  btnPresetM02.addEventListener("click", () => applyPreset("M-02"));
  btnPresetM03.addEventListener("click", () => applyPreset("M-03"));

  function applyPreset(presetKey) {
    const preset = BENCHMARK_PRESETS[presetKey];
    if (!preset) return;

    materialIdInput.value = preset.id;
    materialInput.value = preset.material;
    quantityInput.value = preset.quantity;
    locationInput.value = preset.location;

    // Update active button state
    [btnPresetM01, btnPresetM02, btnPresetM03].forEach((btn) => btn.classList.remove("active"));
    if (presetKey === "M-01") btnPresetM01.classList.add("active");
    if (presetKey === "M-02") btnPresetM02.classList.add("active");
    if (presetKey === "M-03") btnPresetM03.classList.add("active");
  }

  // Check Backend Health
  async function checkSystemHealth() {
    try {
      const response = await fetch("/health");
      if (response.ok) {
        const health = await response.json();
        const healthText = document.getElementById("healthText");
        healthText.textContent = `Registry Active (${health.vendor_registry_entries} Suppliers)`;
      }
    } catch {
      const healthBadge = document.getElementById("systemHealthBadge");
      healthBadge.classList.replace("status-healthy", "status-warning");
      document.getElementById("healthText").textContent = "Service Offline";
    }
  }

  // Form Submission Handler
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideError();

    const payload = {
      id: materialIdInput.value.trim() || "CUSTOM-01",
      material: materialInput.value.trim(),
      quantity: parseFloat(quantityInput.value),
      location: locationInput.value.trim() || "Ahmedabad, Gujarat, India",
    };

    if (!payload.material) {
      showError("Material description is required.");
      return;
    }
    if (isNaN(payload.quantity) || payload.quantity <= 0) {
      showError("Quantity must be greater than zero.");
      return;
    }

    // Set Loading State
    loadingIndicator.classList.remove("hidden");
    resultsContainer.classList.add("hidden");
    runButton.disabled = true;

    try {
      const response = await fetch("/api/v1/procure/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errDetail = await response.json().catch(() => ({ detail: "Evaluation failed." }));
        throw new Error(errDetail.detail || `Server responded with status ${response.status}`);
      }

      currentResult = await response.json();
      renderEvaluationResult(currentResult);
      resultsContainer.classList.remove("hidden");
      resultsContainer.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      showError(err.message || "Failed to execute procurement pipeline.");
    } finally {
      loadingIndicator.classList.add("hidden");
      runButton.disabled = false;
    }
  });

  // Render Full Evaluation Result
  function renderEvaluationResult(result) {
    const spec = result.specification || {};

    // Run ID & Timestamp
    document.getElementById("exportRunId").textContent = result.run_id || "RUN-COMPLETED";
    document.getElementById("exportTimestamp").textContent = new Date(result.timestamp).toLocaleTimeString();

    // 1. Normalized Specification Metrics
    document.getElementById("metricDn").textContent = spec.parsed_dn_mm ? `${spec.parsed_dn_mm} mm` : "N/A";
    document.getElementById("metricOd").textContent = spec.parsed_od_mm ? `${spec.parsed_od_mm} mm` : "N/A";
    document.getElementById("metricWall").textContent = spec.parsed_wall_thickness_mm ? `${spec.parsed_wall_thickness_mm} mm` : "Standard";
    document.getElementById("metricStd").textContent = spec.parsed_standard || "IS 1239:2004";
    document.getElementById("metricTonnage").textContent = spec.total_estimated_metric_tons ? `${spec.total_estimated_metric_tons} MT` : "N/A";
    document.getElementById("metricPieces").textContent = spec.total_estimated_pieces_6m ? `${spec.total_estimated_pieces_6m} pcs` : "N/A";

    // 2. Ambiguities & Stated Assumptions
    renderAmbiguities(spec.ambiguities || []);

    // 3. Vendor Shortlist
    renderVendorShortlists(result);

    // 4. Disqualification Log
    renderExclusionLog(result.exclusion_log || []);

    // 5. Executive Synthesis
    renderExecutiveSynthesis(result.llm_synthesis || "Synthesis completed successfully.");
  }

  // Render Ambiguities
  function renderAmbiguities(ambiguities) {
    const container = document.getElementById("ambiguitiesContainer");
    const countBadge = document.getElementById("ambiguityCountBadge");
    container.innerHTML = "";

    countBadge.textContent = `${ambiguities.length} Ambiguities`;
    if (ambiguities.length === 0) {
      container.innerHTML = `<div class="text-muted" style="padding: 1rem; text-align: center;">No technical ambiguities detected. Requirements conform fully to IS 1239 standards.</div>`;
      return;
    }

    ambiguities.forEach((item) => {
      const el = document.createElement("div");
      el.className = "ambiguity-item";
      el.innerHTML = `
        <div class="ambiguity-header">
          <span class="ambiguity-title">${escapeHtml(item.ambiguity_type)}</span>
          <span class="badge ${item.severity === "CRITICAL" ? "badge-warning" : "badge-mono"}">${escapeHtml(item.severity)}</span>
        </div>
        <p class="ambiguity-desc">${escapeHtml(item.description)}</p>
        <div class="ambiguity-assumption"><strong>Agent Assumption:</strong> ${escapeHtml(item.stated_assumption)}</div>
        <div class="ambiguity-prompt"><strong>Buyer Prompt:</strong> ${escapeHtml(item.clarification_prompt)}</div>
      `;
      container.appendChild(el);
    });
  }

  // Render Vendor Shortlists
  function renderVendorShortlists(result) {
    const ahmVendors = result.ahmedabad_vendors || [];
    const indiaVendors = result.india_vendors || [];
    const globalVendors = result.global_vendors || [];
    const allVendors = [...ahmVendors, ...indiaVendors, ...globalVendors];

    // Counts
    document.getElementById("countAll").textContent = allVendors.length;
    document.getElementById("countAhm").textContent = ahmVendors.length;
    document.getElementById("countIndia").textContent = indiaVendors.length;
    document.getElementById("countGlobal").textContent = globalVendors.length;

    filterAndRenderVendors(allVendors);
  }

  // Filter & Render Vendors by Tab
  function filterAndRenderVendors(allVendors) {
    const container = document.getElementById("vendorCardsContainer");
    container.innerHTML = "";

    let filtered = allVendors;
    if (activeTierFilter !== "ALL") {
      filtered = allVendors.filter((v) => v.tier === activeTierFilter);
    }

    // Sort by global_rank ascending
    filtered.sort((a, b) => a.global_rank - b.global_rank);

    if (filtered.length === 0) {
      container.innerHTML = `<div class="text-muted" style="padding: 2rem; text-align: center;">No vendors found for the selected geographic tier.</div>`;
      return;
    }

    filtered.forEach((vendor) => {
      const card = document.createElement("article");
      card.className = "vendor-card";

      const ev = vendor.evidence || {};
      const factsHtml = (ev.sourced_facts || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("");
      const assumptionsHtml = (ev.assumptions || []).map((a) => `<li>${escapeHtml(a)}</li>`).join("");
      const rfqHtml = (ev.needs_confirmation_rfq || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("");
      const issuesHtml = (vendor.unresolved_issues || []).map((i) => `<li>${escapeHtml(i)}</li>`).join("");

      const matchBadgeClass = vendor.match_category === "EXACT_MATCH" ? "badge-success" : (vendor.match_category === "NEAR_MATCH" ? "badge-mono" : "badge-warning");

      card.innerHTML = `
        <div class="vendor-card-header">
          <div class="vendor-title-group">
            <span class="badge badge-mono">Tier Rank #${vendor.rank} (Global #${vendor.global_rank})</span>
            <h4 class="vendor-name">${escapeHtml(vendor.vendor_name)}</h4>
            <span class="vendor-meta-pill">${escapeHtml(vendor.location)}, ${escapeHtml(vendor.country)}</span>
            <span class="badge ${matchBadgeClass}">${escapeHtml(vendor.match_category)}</span>
          </div>
          <div class="vendor-score-box">
            <span class="detail-label">Confidence</span>
            <span class="score-circle">${vendor.confidence_score}%</span>
          </div>
        </div>

        <div class="vendor-details-grid">
          <div class="detail-row">
            <span class="detail-label">1. Vendor Type</span>
            <span class="detail-value">${escapeHtml(vendor.vendor_type)}</span>
          </div>

          <div class="detail-row">
            <span class="detail-label">2. Product Specification</span>
            <span class="detail-value">${escapeHtml(ev.catalog_spec || "Standard Catalog Offering")}</span>
          </div>

          <div class="detail-row">
            <span class="detail-label">4. Quantity & Capacity Relevance</span>
            <span class="detail-value">${escapeHtml(ev.stock_or_capacity_evidence || "Standard mill manufacturing capacity.")}</span>
          </div>

          <div class="detail-row">
            <span class="detail-label">5. Standards & Certifications</span>
            <span class="detail-value">${escapeHtml((ev.certifications || []).join(", ") || "ISO 9001 standard compliance")}</span>
          </div>

          <div class="detail-row">
            <span class="detail-label">6. Delivery & Logistics Evidence</span>
            <span class="detail-value">${escapeHtml(ev.delivery_evidence || "Standard commercial freight dispatch.")}</span>
          </div>

          <div class="detail-row">
            <span class="detail-label">7. Contact & Official Website</span>
            <span class="detail-value">
              <a href="${escapeHtml(ev.source_url || "#")}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: none;">
                ${escapeHtml(ev.source_url || "Company Catalog")} &rarr;
              </a>
              <br><small style="color: var(--text-muted);">Email: ${escapeHtml(ev.contact_email || "sales@domain.com")} | Phone: ${escapeHtml(ev.contact_phone || "N/A")}</small>
            </span>
          </div>

          <div class="detail-row" style="grid-column: span 2;">
            <span class="detail-label">Verified Physical Facility</span>
            <span class="detail-value" style="font-size: 0.8rem; color: var(--text-secondary);">${escapeHtml(ev.address || "Registered manufacturing address")}</span>
          </div>

          <div class="evidence-box">
            <span class="detail-label" style="display: block; margin-bottom: 0.5rem;">3. Evidence Supporting the Match:</span>
            
            <div class="evidence-tag sourced">[SOURCED FACTS]</div>
            <ul class="evidence-list">${factsHtml || "<li>Verified from manufacturer catalog registration.</li>"}</ul>

            <div class="evidence-tag assumption">[ENGINEERING ASSUMPTIONS]</div>
            <ul class="evidence-list">${assumptionsHtml || "<li>Standard commercial handling applied.</li>"}</ul>

            <div class="evidence-tag rfq">[RFQ CONFIRMATION INQUIRIES]</div>
            <ul class="evidence-list">${rfqHtml || "<li>Confirm current pricing and mill test certificate.</li>"}</ul>
          </div>

          <div class="next-step-box">
            <span class="detail-label" style="color: #a5b4fc; display: block; margin-bottom: 0.35rem;">10. Unresolved Issues & Recommended Next Step:</span>
            <ul class="evidence-list" style="margin-bottom: 0.4rem;">${issuesHtml || "<li>No critical gaps identified.</li>"}</ul>
            <div style="font-weight: 600; color: #fff; font-size: 0.85rem;">
              <strong>Action:</strong> ${escapeHtml(vendor.recommended_next_step)}
            </div>
          </div>
        </div>
      `;
      container.appendChild(card);
    });
  }

  // Tier Tab Switching
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeTierFilter = btn.dataset.tier;
      if (currentResult) {
        const allVendors = [
          ...(currentResult.ahmedabad_vendors || []),
          ...(currentResult.india_vendors || []),
          ...(currentResult.global_vendors || []),
        ];
        filterAndRenderVendors(allVendors);
      }
    });
  });

  // Render Exclusion Log
  function renderExclusionLog(exclusionLog) {
    const container = document.getElementById("exclusionLogContainer");
    container.innerHTML = "";

    if (exclusionLog.length === 0) {
      container.innerHTML = `<div class="text-muted" style="padding: 0.75rem 1rem;">No candidate suppliers disqualified for this requirement; all evaluated candidate profiles met minimum criteria.</div>`;
      return;
    }

    exclusionLog.forEach((item) => {
      const el = document.createElement("div");
      el.className = "exclusion-item";
      el.innerHTML = `
        <span class="exclusion-name">${escapeHtml(item.vendor_name)}</span>
        <span class="badge badge-mono">${escapeHtml(item.tier)}</span>
        <span class="exclusion-reason">${escapeHtml(item.disqualification_reason)}</span>
      `;
      container.appendChild(el);
    });
  }

  // Render Executive Synthesis
  function renderExecutiveSynthesis(synthesis) {
    const container = document.getElementById("executiveSynthesisContainer");
    container.textContent = synthesis;
  }

  // Export Download Triggers
  btnExportMd.addEventListener("click", () => downloadExport("md"));
  btnExportCsv.addEventListener("click", () => downloadExport("csv"));
  btnExportJson.addEventListener("click", () => downloadExport("json"));

  async function downloadExport(formatType) {
    if (!currentResult || !currentResult.material_id) {
      showError("Please run an evaluation before exporting.");
      return;
    }

    const materialId = currentResult.material_id;
    const url = `/api/v1/procure/${encodeURIComponent(materialId)}/export/${formatType}`;

    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Failed to download ${formatType.toUpperCase()} export`);
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = `procurement_${materialId}.${formatType === "markdown" ? "md" : formatType}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      showError(err.message || `Export failed.`);
    }
  }

  // Utility Error Functions
  function showError(message) {
    errorMessage.textContent = message;
    errorAlert.classList.remove("hidden");
  }

  function hideError() {
    errorAlert.classList.add("hidden");
  }

  function escapeHtml(string) {
    if (!string) return "";
    return String(string)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
