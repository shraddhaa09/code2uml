// Code2UML AI Frontend Application

let currentArchitecture = null;
let currentMermaidStructuralCode = "";
let currentMermaidFullCode = "";
let currentMermaidUmlCode = "";
let showUsesEdges = false;
let focusedController = "";
let zoomLevel = 1.0;
let activeTab = "diagramTab";

document.addEventListener("DOMContentLoaded", () => {
    // Initialize Mermaid
    if (window.mermaid) {
        mermaid.initialize({
            startOnLoad: false,
            theme: "dark",
            securityLevel: "loose",
            flowchart: {
                curve: "basis",
                htmlLabels: true,
                padding: 20,
                nodeSpacing: 50,
                rankSpacing: 55
            }
        });
    }

    checkHealth();
    setupEventListeners();
});

// Check AI & Backend Status
async function checkHealth() {
    const badge = document.getElementById("aiStatusBadge");
    const deploymentBadge = document.getElementById("deploymentBadge");
    const hostedBanner = document.getElementById("hostedWarningBanner");

    try {
        const res = await fetch("/api/health");
        if (res.ok) {
            const data = await res.json();
            
            // Deployment mode check
            if (data.deployment_mode === "hosted") {
                if (deploymentBadge) deploymentBadge.textContent = "🛡️ Static Analysis";
                if (hostedBanner) hostedBanner.classList.remove("hidden");
            } else {
                if (deploymentBadge) deploymentBadge.textContent = "🛡️ Local Static Analysis";
                if (hostedBanner) hostedBanner.classList.add("hidden");
            }

            // AI configuration check
            if (data.ai_configured || data.ai_enabled) {
                badge.className = "badge badge-ai";
                badge.textContent = `🤖 Gemma Active: ${data.ai_model}`;
            } else {
                badge.className = "badge badge-ai offline";
                badge.textContent = "⚡ Offline Rules Engine Active (Gemma API Key Optional)";
            }
        }
    } catch (e) {
        if (badge) {
            badge.className = "badge badge-ai offline";
            badge.textContent = "⚡ Offline Rules Engine Active (Gemma API Key Optional)";
        }
    }
}

function setupEventListeners() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");
    const browseBtn = document.getElementById("browseBtn");
    const sampleBtn = document.getElementById("sampleBtn");
    const closeErrorBtn = document.getElementById("closeErrorBtn");
    const toggleUses = document.getElementById("toggleUsesEdges");
    const focusSelect = document.getElementById("focusControllerSelect");

    browseBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    dropzone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", (e) => {
        if (e.target.files && e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    // Drag & Drop
    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    // Sample Project Button
    sampleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        loadSampleProject();
    });

    closeErrorBtn.addEventListener("click", hideError);

    // Tab Navigation
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

            btn.classList.add("active");
            const targetId = btn.getAttribute("data-tab");
            activeTab = targetId;
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.add("active");
                if (targetId === "diagramTab") {
                    renderActiveDiagram();
                } else if (targetId === "umlTab") {
                    renderUmlDiagram();
                }
            }
        });
    });

    // Toggle Uses Edges
    if (toggleUses) {
        toggleUses.addEventListener("change", (e) => {
            showUsesEdges = e.target.checked;
            renderActiveDiagram();
        });
    }

    // Focus Controller Select
    if (focusSelect) {
        focusSelect.addEventListener("change", (e) => {
            focusedController = e.target.value;
            renderActiveDiagram();
        });
    }

    // Zoom Controls
    document.getElementById("zoomInBtn").addEventListener("click", () => adjustZoom(0.15));
    document.getElementById("zoomOutBtn").addEventListener("click", () => adjustZoom(-0.15));
    document.getElementById("resetZoomBtn").addEventListener("click", () => setZoom(1.0));

    // Copy Mermaid
    document.getElementById("copyMermaidBtn").addEventListener("click", () => {
        let codeToCopy = "";
        if (activeTab === "umlTab") {
            codeToCopy = currentMermaidUmlCode;
        } else {
            codeToCopy = getEffectiveMermaidCode();
        }
        if (codeToCopy) {
            navigator.clipboard.writeText(codeToCopy);
            const btn = document.getElementById("copyMermaidBtn");
            const orig = btn.textContent;
            btn.textContent = "✅ Copied!";
            setTimeout(() => btn.textContent = orig, 2000);
        }
    });

    // Chat Form
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");

    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (text && currentArchitecture) {
            askQuestion(text);
            chatInput.value = "";
        }
    });

    // Observations Toggle
    const toggleObsBtn = document.getElementById("toggleObsBtn");
    const obsList = document.getElementById("observationsList");
    if (toggleObsBtn && obsList) {
        toggleObsBtn.addEventListener("click", () => {
            const isHidden = obsList.classList.toggle("hidden");
            toggleObsBtn.textContent = isHidden ? "Expand" : "Collapse";
        });
    }

    // Diagnostics Toggle
    const toggleDiagBtn = document.getElementById("toggleDiagBtn");
    const diagList = document.getElementById("diagnosticsList");
    if (toggleDiagBtn && diagList) {
        toggleDiagBtn.addEventListener("click", () => {
            const isHidden = diagList.classList.toggle("hidden");
            toggleDiagBtn.textContent = isHidden ? "Details" : "Hide Details";
        });
    }
}

function adjustZoom(delta) {
    setZoom(Math.max(0.3, Math.min(2.5, zoomLevel + delta)));
}

function setZoom(lvl) {
    zoomLevel = lvl;
    const container = document.getElementById("mermaidOutput");
    if (container) {
        container.style.transform = `scale(${zoomLevel})`;
    }
    const umlContainer = document.getElementById("mermaidUmlOutput");
    if (umlContainer) {
        umlContainer.style.transform = `scale(${zoomLevel})`;
    }
}

function showLoading(msg = "Extracting & analyzing Spring Boot architecture...") {
    document.getElementById("loadingText").textContent = msg;
    document.getElementById("loadingOverlay").classList.remove("hidden");
    hideError();
}

function hideLoading() {
    document.getElementById("loadingOverlay").classList.add("hidden");
}

function showError(msg) {
    document.getElementById("errorText").textContent = msg;
    document.getElementById("errorMessage").classList.remove("hidden");
}

function hideError() {
    document.getElementById("errorMessage").classList.add("hidden");
}

// Upload & Analyze ZIP
async function uploadFile(file) {
    if (!file.name.toLowerCase().endsWith(".zip")) {
        showError("Please select a valid .zip file containing your Spring Boot project.");
        return;
    }

    if (file.size > 50 * 1024 * 1024) {
        showError("File size exceeds the maximum limit of 50MB.");
        return;
    }

    showLoading(`Analyzing ${file.name}...`);
    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            let errDetail = "Analysis failed";
            try {
                const err = await response.json();
                errDetail = err.detail || errDetail;
            } catch (e) {
                errDetail = `Server error (HTTP ${response.status})`;
            }
            throw new Error(errDetail);
        }

        const data = await response.json();
        renderAnalysis(data);
    } catch (err) {
        showError(err.message || "Failed to analyze ZIP file. Please verify the archive.");
    } finally {
        hideLoading();
    }
}

// Load Built-in Sample Project
async function loadSampleProject() {
    showLoading("Loading and analyzing built-in Sample Spring Boot project...");
    try {
        const response = await fetch("/api/analyze/sample", {
            method: "POST"
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to load sample project.");
        }

        const data = await response.json();
        renderAnalysis(data);
    } catch (err) {
        showError(err.message || "Failed to load sample project.");
    } finally {
        hideLoading();
    }
}

// Render Results
async function renderAnalysis(data) {
    currentArchitecture = data.architecture;
    const summary = currentArchitecture.summary || {};

    // 1. Build Structural vs Full Mermaid Diagram Codes
    buildMermaidDiagrams(data);

    // Large project automatic fallback: default to structural edges only if >40 types or >80 relationships
    const isLargeProject = (summary.total_types > 40 || summary.relationships > 80);
    const usesToggle = document.getElementById("toggleUsesEdges");
    if (isLargeProject) {
        showUsesEdges = false;
        if (usesToggle) usesToggle.checked = false;
    }

    // Populate Focus Controller Select Dropdown
    const focusSelect = document.getElementById("focusControllerSelect");
    if (focusSelect) {
        focusSelect.innerHTML = '<option value="">Full Architecture</option>';
        (currentArchitecture.controllers || []).forEach(ctrl => {
            const opt = document.createElement("option");
            opt.value = ctrl.name;
            opt.textContent = `Focus: ${ctrl.name}`;
            focusSelect.appendChild(opt);
        });
        focusedController = "";
    }

    // 2. Populate All 9 Summary Cards
    document.getElementById("statTotalTypes").textContent = summary.total_types || summary.total_classes || 0;
    document.getElementById("statTypesSubtitle").textContent = `${summary.classes || 0} classes · ${summary.interfaces || 0} interfaces`;
    document.getElementById("statControllers").textContent = summary.controllers || 0;

    document.getElementById("statServices").textContent = summary.services || 0;
    const srvSublabel = document.getElementById("statServicesSublabel");
    if (summary.service_interfaces && summary.service_interfaces > 0) {
        srvSublabel.textContent = `(+${summary.service_interfaces} service interface)`;
    } else {
        srvSublabel.textContent = "";
    }

    document.getElementById("statRepositories").textContent = summary.repositories || 0;
    document.getElementById("statEntities").textContent = summary.entities || 0;
    document.getElementById("statDTOs").textContent = summary.dtos || 0;
    document.getElementById("statApplications").textContent = summary.applications || 0;
    document.getElementById("statEndpoints").textContent = summary.endpoints || 0;
    document.getElementById("statRelationships").textContent = summary.relationships || 0;
    document.getElementById("tabEndpointCount").textContent = summary.endpoints || 0;

    // Architecture Observations Banner
    const obsSection = document.getElementById("observationsSection");
    const obsList = document.getElementById("observationsList");
    if (obsSection && obsList) {
        const obsArray = currentArchitecture.observations || [];
        if (obsArray.length > 0) {
            obsList.innerHTML = obsArray.map(obs => {
                const icon = obs.severity === "warning" ? "⚠️" : "ℹ️";
                return `<div class="observation-item"><span>${icon}</span> <span>${escapeHtml(obs.message)}</span></div>`;
            }).join("");
            obsSection.classList.remove("hidden");
        } else {
            obsSection.classList.add("hidden");
        }
    }

    // Analysis Coverage & Diagnostics Banner
    const diagSection = document.getElementById("diagnosticsSection");
    const diagList = document.getElementById("diagnosticsList");
    const diagBadge = document.getElementById("diagCoverageBadge");
    if (diagSection && currentArchitecture.diagnostics) {
        const diag = currentArchitecture.diagnostics;
        const cov = diag.coverage_percentage !== undefined ? diag.coverage_percentage : 100.0;
        
        if (diagBadge) {
            diagBadge.textContent = cov === 100.0 ? "100% Deterministic Coverage" : `${cov}% Coverage (Partial)`;
            if (cov < 100.0) {
                diagBadge.classList.add("partial");
            } else {
                diagBadge.classList.remove("partial");
            }
        }

        if (diagList) {
            let diagHtml = `<div>• <b>Files Scanned:</b> ${diag.total_files_discovered || 0} Java files (${diag.parsed_ast_count || 0} via AST, ${diag.parsed_fallback_count || 0} via tokenizer fallback)</div>`;
            if (diag.skipped_count && diag.skipped_count > 0) {
                diagHtml += `<div>• <b>Skipped Files:</b> ${diag.skipped_count} (test / build artifacts excluded)</div>`;
            }
            if (diag.unsupported_languages && Object.keys(diag.unsupported_languages).length > 0) {
                const langs = Object.entries(diag.unsupported_languages).map(([k, v]) => `${k} (${v})`).join(", ");
                diagHtml += `<div>• <b>Unsupported JVM Sources:</b> ${langs} (currently Java-only analysis)</div>`;
            }
            if (diag.failed_count && diag.failed_count > 0) {
                diagHtml += `<div style="color: var(--accent-red);">• <b>Unparsed Files:</b> ${diag.failed_count} file(s) had syntax or decoding errors</div>`;
            }
            if (diag.warnings && diag.warnings.length > 0) {
                diag.warnings.forEach(w => {
                    diagHtml += `<div style="color: var(--accent-orange);">• <b>Warning:</b> ${escapeHtml(w)}</div>`;
                });
            }
            diagList.innerHTML = diagHtml;
        }
        diagSection.classList.remove("hidden");
    }

    // Reset Chat Thread & Welcome Bubble
    resetChatThread();

    // Dynamically Generate Suggestion Chips
    generateDynamicChips();

    // Show Results Section
    document.getElementById("resultsSection").classList.remove("hidden");

    // 3. Render Active Diagram
    if (activeTab === "umlTab") {
        renderUmlDiagram();
    } else {
        renderActiveDiagram();
    }

    // 4. Render Endpoints Table
    renderEndpointsTable(currentArchitecture.endpoints || []);

    // 5. Render Rich Component Catalog
    renderComponentCatalog(currentArchitecture.classes || []);

    // 6. Render Raw JSON
    document.getElementById("rawJsonOutput").textContent = JSON.stringify(currentArchitecture, null, 2);
}

function resetChatThread() {
    const chatMessages = document.getElementById("chatMessages");
    if (!chatMessages) return;

    const projName = currentArchitecture ? (currentArchitecture.project || "your project") : "your project";
    chatMessages.innerHTML = `
        <div class="chat-bubble bot-bubble">
            <div class="bubble-header" id="welcomeBubbleHeader">Architecture Assistant</div>
            <div class="bubble-content" id="welcomeBubbleContent">
                Hello! I'm ready to explain the architecture of <b>${escapeHtml(projName)}</b>.
                Try clicking one of the suggested prompts below or ask your own question!
            </div>
        </div>
    `;
}

function generateDynamicChips() {
    const container = document.getElementById("suggestionsContainer");
    if (!container || !currentArchitecture) return;

    container.innerHTML = "";
    const controllers = currentArchitecture.controllers || [];
    const repositories = currentArchitecture.repositories || [];
    const services = currentArchitecture.services || [];

    const prompts = [];

    // 1. Request Flow
    if (controllers.length > 0) {
        prompts.push({
            label: "🔄 Request flow",
            prompt: `Explain the request flow for ${controllers[0].name}`
        });
    } else {
        prompts.push({
            label: "🔄 Request flow",
            prompt: "Explain the overall request flow from controller to database."
        });
    }

    // 2. Direct dependency check
    if (controllers.length > 0 && repositories.length > 0) {
        prompts.push({
            label: `❓ ${controllers[0].name} ➔ ${repositories[0].name}?`,
            prompt: `Does ${controllers[0].name} directly depend on ${repositories[0].name}?`
        });
    } else if (controllers.length > 0 && services.length > 0) {
        prompts.push({
            label: `❓ ${controllers[0].name} ➔ ${services[0].name}?`,
            prompt: `Does ${controllers[0].name} directly depend on ${services[0].name}?`
        });
    }

    // 3. Endpoints
    if (controllers.length > 0) {
        prompts.push({
            label: "🌐 Endpoints",
            prompt: `List all REST endpoints in ${controllers[0].name}`
        });
    } else {
        prompts.push({
            label: "🌐 Endpoints",
            prompt: "List all REST endpoints, HTTP methods, and their controllers."
        });
    }

    // 4. Database vendor
    prompts.push({
        label: "🏢 Database vendor",
        prompt: "Which database vendor is used?"
    });

    // 5. Authentication
    prompts.push({
        label: "🔒 Auth components",
        prompt: "Is there an authentication component?"
    });

    // 6. Entities & Repositories
    prompts.push({
        label: "🗄️ Entities & Repos",
        prompt: "What database entities and repositories are present?"
    });

    prompts.forEach(p => {
        const chip = document.createElement("span");
        chip.className = "suggestion-chip";
        chip.textContent = p.label;
        chip.setAttribute("data-prompt", p.prompt);
        chip.addEventListener("click", () => askQuestion(p.prompt));
        container.appendChild(chip);
    });
}

let renderCounter = 0;

function cleanupStrayMermaidElements() {
    const strayNodes = document.querySelectorAll(
        "body > svg[id^='dmermaid'], body > #dmermaid, body > svg[aria-roledescription='error'], body > .error-icon, body > svg[id^='mermaid-']"
    );
    strayNodes.forEach(node => {
        if (!node.closest(".app-container")) {
            node.remove();
        }
    });
}

function updateRelationshipCaption(activeCode) {
    const captionEl = document.getElementById("diagramCaption");
    if (!captionEl) return;

    if (!activeCode || !currentArchitecture) {
        captionEl.textContent = "";
        return;
    }

    const totalRels = currentArchitecture.summary?.relationships ?? (currentArchitecture.relationships?.length || 0);
    const edgeMatches = activeCode.match(/(-->|-\.->|--\|>|==>)/g) || [];
    const activeRels = edgeMatches.length;

    let focusNote = focusedController ? ` (Focused on ${focusedController})` : "";
    let usesNote = (!showUsesEdges && totalRels > activeRels) ? " · Showing structural edges only" : "";

    captionEl.textContent = `Showing ${activeRels} of ${totalRels} relationships${focusNote}${usesNote}`;
}

function buildMermaidDiagrams(data) {
    currentMermaidUmlCode = data.mermaid_uml || "";
    if (data.mermaid_full && data.mermaid) {
        currentMermaidFullCode = data.mermaid_full;
        currentMermaidStructuralCode = data.mermaid;
        return;
    }

    const baseMermaid = data.mermaid || "";
    currentMermaidFullCode = baseMermaid;
    currentMermaidStructuralCode = baseMermaid;
}

function getEffectiveMermaidCode() {
    if (!currentArchitecture) return "";

    // If a specific controller is focused, build a focused subgraph
    if (focusedController) {
        return buildClientFocusDiagram(focusedController);
    }

    return showUsesEdges ? currentMermaidFullCode : currentMermaidStructuralCode;
}

function buildClientFocusDiagram(targetCtrlName) {
    if (!currentArchitecture) return "";

    const ctrl = (currentArchitecture.controllers || []).find(c => c.name === targetCtrlName);
    if (!ctrl) return currentMermaidStructuralCode;

    // Reachable nodes
    const reachable = new Set([ctrl.name]);
    const queue = [ctrl.name];
    const adj = {};

    (currentArchitecture.relationships || []).forEach(r => {
        if (!adj[r.source]) adj[r.source] = [];
        adj[r.source].push(r.target);
    });

    while (queue.length > 0) {
        const curr = queue.shift();
        const neighbors = adj[curr] || [];
        neighbors.forEach(n => {
            if (!reachable.has(n)) {
                reachable.add(n);
                queue.push(n);
            }
        });
    }

    // Filter structural mermaid code lines to reachable nodes & edges
    const lines = currentMermaidStructuralCode.split("\n");
    const outputLines = [];
    let insideReachableSubgraph = false;

    for (let line of lines) {
        if (line.includes("subgraph ")) {
            outputLines.push(line);
            insideReachableSubgraph = true;
        } else if (line.trim() === "end") {
            outputLines.push(line);
            insideReachableSubgraph = false;
        } else if (line.includes("-->") || line.includes("-.->") || line.includes("==>")) {
            // Check if source and target in edge line are reachable
            const parts = line.split(/-->|-\.->|==>|--\|>/);
            if (parts.length >= 2) {
                const s = parts[0].trim().split(" ")[0];
                const t = parts[1].trim().split(" ")[0].replace(/\|.*\|/, "").trim();
                if (reachable.has(s) && reachable.has(t)) {
                    outputLines.push(line);
                }
            }
        } else {
            // Node definition line
            const m = line.match(/^\s*([A-Za-z0-9_]+)\[/);
            if (m) {
                if (reachable.has(m[1])) {
                    outputLines.push(line);
                }
            } else {
                outputLines.push(line);
            }
        }
    }

    return outputLines.join("\n");
}

async function renderActiveDiagram() {
    const mermaidContainer = document.getElementById("mermaidOutput");
    if (!mermaidContainer) return;

    mermaidContainer.innerHTML = "";
    let activeCode = getEffectiveMermaidCode();

    updateRelationshipCaption(activeCode);

    if (!activeCode) {
        mermaidContainer.innerHTML = `<p style="color: var(--text-muted);">No diagram available.</p>`;
        return;
    }

    cleanupStrayMermaidElements();

    try {
        renderCounter++;
        const renderId = `dmermaid_${Date.now()}_${renderCounter}`;

        if (window.mermaid && typeof mermaid.parse === "function") {
            try {
                await mermaid.parse(activeCode);
            } catch (parseErr) {
                console.error("Mermaid parse error:", parseErr);
                cleanupStrayMermaidElements();

                // If full mode failed on a large project, automatically retry with structural mode
                if (showUsesEdges) {
                    console.warn("Retrying render with structural edges only...");
                    showUsesEdges = false;
                    const usesToggle = document.getElementById("toggleUsesEdges");
                    if (usesToggle) usesToggle.checked = false;
                    activeCode = getEffectiveMermaidCode();
                    updateRelationshipCaption(activeCode);

                    try {
                        await mermaid.parse(activeCode);
                    } catch (retryErr) {
                        mermaidContainer.innerHTML = `
                            <div class="error-banner" style="margin: 1rem; width: 100%;">
                                <span class="error-icon">⚠️</span>
                                <span>Failed to parse Mermaid diagram: ${escapeHtml(retryErr.message || String(retryErr))}. Copy Mermaid is still available.</span>
                            </div>
                        `;
                        return;
                    }
                } else {
                    mermaidContainer.innerHTML = `
                        <div class="error-banner" style="margin: 1rem; width: 100%;">
                            <span class="error-icon">⚠️</span>
                            <span>Failed to parse Mermaid diagram: ${escapeHtml(parseErr.message || String(parseErr))}. Copy Mermaid is still available.</span>
                        </div>
                    `;
                    return;
                }
            }
        }

        const { svg } = await mermaid.render(renderId, activeCode);
        mermaidContainer.innerHTML = svg;
    } catch (e) {
        console.error("Mermaid render error:", e);
        cleanupStrayMermaidElements();
        mermaidContainer.innerHTML = `
            <div class="error-banner" style="margin: 1rem; width: 100%;">
                <span class="error-icon">⚠️</span>
                <span>Failed to render Mermaid diagram: ${escapeHtml(e.message || String(e))}. Copy Mermaid is still available.</span>
            </div>
        `;
    } finally {
        cleanupStrayMermaidElements();
    }
}

async function renderUmlDiagram() {
    const umlContainer = document.getElementById("mermaidUmlOutput");
    if (!umlContainer) return;

    umlContainer.innerHTML = "";
    if (!currentMermaidUmlCode) {
        umlContainer.innerHTML = `<p style="color: var(--text-muted);">No UML class diagram available.</p>`;
        return;
    }

    cleanupStrayMermaidElements();

    try {
        renderCounter++;
        const renderId = `dmermaid_uml_${Date.now()}_${renderCounter}`;

        if (window.mermaid && typeof mermaid.parse === "function") {
            try {
                await mermaid.parse(currentMermaidUmlCode);
            } catch (parseErr) {
                console.error("Mermaid UML parse error:", parseErr);
                cleanupStrayMermaidElements();
                umlContainer.innerHTML = `
                    <div class="error-banner" style="margin: 1rem; width: 100%;">
                        <span class="error-icon">⚠️</span>
                        <span>Failed to parse UML Class Diagram: ${escapeHtml(parseErr.message || String(parseErr))}. Copy Mermaid is still available.</span>
                    </div>
                `;
                return;
            }
        }

        const { svg } = await mermaid.render(renderId, currentMermaidUmlCode);
        umlContainer.innerHTML = svg;
    } catch (e) {
        console.error("Mermaid UML render error:", e);
        cleanupStrayMermaidElements();
        umlContainer.innerHTML = `
            <div class="error-banner" style="margin: 1rem; width: 100%;">
                <span class="error-icon">⚠️</span>
                <span>Failed to render UML Class Diagram: ${escapeHtml(e.message || String(e))}. Copy Mermaid is still available.</span>
            </div>
        `;
    } finally {
        cleanupStrayMermaidElements();
    }
}

function renderEndpointsTable(endpoints) {
    const tbody = document.getElementById("endpointsTableBody");
    tbody.innerHTML = "";

    if (endpoints.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No REST endpoints detected.</td></tr>`;
        return;
    }

    endpoints.forEach(ep => {
        const tr = document.createElement("tr");
        const methodClass = `method-${ep.http_method.toLowerCase()}`;
        tr.innerHTML = `
            <td><span class="method-badge ${methodClass}">${escapeHtml(ep.http_method)}</span></td>
            <td><code>${escapeHtml(ep.path)}</code></td>
            <td><b>${escapeHtml(ep.controller)}</b></td>
            <td><code>${escapeHtml(ep.method_name)}()</code></td>
            <td><code>${escapeHtml(ep.return_type || "void")}</code></td>
        `;
        tbody.appendChild(tr);
    });
}

function formatAnnotation(name, attrs) {
    if (!attrs || Object.keys(attrs).length === 0) {
        return `@${escapeHtml(name)}`;
    }
    const pairs = Object.entries(attrs).map(([k, v]) => {
        let valStr;
        if (typeof v === "string") {
            if (v.includes(".") || v === "true" || v === "false" || (!isNaN(Number(v)) && v.trim() !== "") || v.startsWith('"')) {
                valStr = v;
            } else {
                valStr = `"${v}"`;
            }
        } else if (typeof v === "object") {
            valStr = JSON.stringify(v);
        } else {
            valStr = String(v);
        }
        return `${escapeHtml(k)} = ${escapeHtml(valStr)}`;
    });
    return `@${escapeHtml(name)}(${pairs.join(", ")})`;
}

function renderComponentCatalog(classes) {
    const list = document.getElementById("componentsList");
    list.innerHTML = "";

    if (classes.length === 0) {
        list.innerHTML = `<p style="color: var(--text-muted); padding: 1rem;">No Java components detected.</p>`;
        return;
    }

    classes.forEach(c => {
        const card = document.createElement("div");
        card.className = "component-card";

        const roleLabel = c.type.toUpperCase().replace("_", " ");
        const kindLabel = c.is_interface ? "INTERFACE" : "CLASS";

        const annoBadges = (c.annotations || []).map(aname => {
            const attrs = (c.annotation_attributes || {})[aname] || {};
            const formatted = formatAnnotation(aname, attrs);
            return `<span class="tag tag-anno">${formatted}</span>`;
        }).join(" ");

        let sectionsHtml = "";

        // 1. Controller Section
        if (c.type === "controller") {
            const bp = c.base_path ? `<code>${escapeHtml(c.base_path)}</code>` : "<em>None</em>";
            const epCount = (c.endpoints || []).length;
            const deps = (c.dependencies || []).length > 0
                ? c.dependencies.map(d => `<span class="tag tag-dep">↳ ${escapeHtml(d)}</span>`).join(" ")
                : "<em>None</em>";

            sectionsHtml += `
                <div class="component-section">
                    <div class="section-label">Controller Details</div>
                    <div style="font-size: 0.84rem; display: flex; flex-direction: column; gap: 0.3rem;">
                        <div><b>Base path:</b> ${bp}</div>
                        <div><b>Endpoints:</b> ${epCount} detected</div>
                        <div><b>Direct Dependencies:</b> ${deps}</div>
                    </div>
                </div>
            `;
        }

        // 2. Entity Section (Table & Fields)
        if (c.type === "entity") {
            const tbl = c.table_name ? `<code>${escapeHtml(c.table_name)}</code>` : "<em>default</em>";
            let fieldsRows = "";
            (c.fields || []).forEach(f => {
                const fAnnos = (f.annotations || []).map(aname => {
                    const fattrs = (f.annotation_attributes || {})[aname] || {};
                    const formatted = formatAnnotation(aname, fattrs);
                    return `<span class="tag ${f.is_id ? 'tag-id' : 'tag-anno'}">${formatted}</span>`;
                }).join(" ");

                fieldsRows += `
                    <tr>
                        <td><b>${escapeHtml(f.name)}</b></td>
                        <td><code>${escapeHtml(f.type)}</code></td>
                        <td>${fAnnos || "—"}</td>
                    </tr>
                `;
            });

            sectionsHtml += `
                <div class="component-section">
                    <div class="section-label">Entity Table & Fields</div>
                    <div style="font-size: 0.84rem; margin-bottom: 0.35rem;"><b>Table:</b> ${tbl}</div>
                    <table class="mini-table">
                        <thead>
                            <tr><th>Field</th><th>Type</th><th>Annotations</th></tr>
                        </thead>
                        <tbody>${fieldsRows || '<tr><td colspan="3">No fields detected</td></tr>'}</tbody>
                    </table>
                </div>
            `;
        }

        // 3. DTO Section (Fields)
        if (c.type === "dto") {
            let fieldsRows = "";
            (c.fields || []).forEach(f => {
                fieldsRows += `
                    <tr>
                        <td><b>${escapeHtml(f.name)}</b></td>
                        <td><code>${escapeHtml(f.type)}</code></td>
                    </tr>
                `;
            });

            sectionsHtml += `
                <div class="component-section">
                    <div class="section-label">DTO Fields</div>
                    <table class="mini-table">
                        <thead>
                            <tr><th>Field</th><th>Type</th></tr>
                        </thead>
                        <tbody>${fieldsRows || '<tr><td colspan="2">No fields detected</td></tr>'}</tbody>
                    </table>
                </div>
            `;
        }

        // 4. Repository Section (Extends & Methods)
        if (c.type === "repository") {
            const ext = c.extends ? `<code>${escapeHtml(c.extends)}</code>` : "<em>None</em>";
            const managed = c.managed_entity ? `<div><b>Manages:</b> <span class="tag tag-dep">${escapeHtml(c.managed_entity)}</span></div>` : "";

            let methodsList = "";
            if (c.declared_methods && c.declared_methods.length > 0) {
                methodsList = c.declared_methods.map(m => `<li><code>${escapeHtml(m.signature || m.name)}</code></li>`).join("");
            } else if (c.methods && c.methods.length > 0) {
                methodsList = c.methods.map(m => `<li><code>${escapeHtml(m)}()</code></li>`).join("");
            }

            sectionsHtml += `
                <div class="component-section">
                    <div class="section-label">Repository Details</div>
                    <div style="font-size: 0.84rem; display: flex; flex-direction: column; gap: 0.35rem;">
                        <div><b>Extends:</b> ${ext}</div>
                        ${managed}
                        ${methodsList ? `<div><b>Declared Methods:</b><ul style="padding-left: 1.25rem; margin-top: 0.25rem; font-size: 0.8rem;">${methodsList}</ul></div>` : ""}
                    </div>
                </div>
            `;
        }

        // 5. Service / Service Interface Section
        if (c.type === "service" || c.type === "service_interface") {
            const impls = (c.implements || []).length > 0
                ? c.implements.map(i => `<span class="tag tag-impl">${escapeHtml(i)}</span>`).join(" ")
                : "";
            const deps = (c.dependencies || []).length > 0
                ? c.dependencies.map(d => `<span class="tag tag-dep">↳ ${escapeHtml(d)}</span>`).join(" ")
                : "";

            let methodsList = "";
            if (c.declared_methods && c.declared_methods.length > 0) {
                methodsList = c.declared_methods.map(m => `<li><code>${escapeHtml(m.signature || m.name)}</code></li>`).join("");
            } else if (c.methods && c.methods.length > 0) {
                methodsList = c.methods.map(m => `<li><code>${escapeHtml(m)}()</code></li>`).join("");
            }

            sectionsHtml += `
                <div class="component-section">
                    <div class="section-label">Service Details</div>
                    <div style="font-size: 0.84rem; display: flex; flex-direction: column; gap: 0.35rem;">
                        ${impls ? `<div><b>Implements:</b> ${impls}</div>` : ""}
                        ${deps ? `<div><b>Dependencies:</b> ${deps}</div>` : ""}
                        ${methodsList ? `<div><b>Declared Methods:</b><ul style="padding-left: 1.25rem; margin-top: 0.25rem; font-size: 0.8rem;">${methodsList}</ul></div>` : ""}
                    </div>
                </div>
            `;
        }

        // Heuristic badge if present
        const heuristicBadge = c.detection_heuristic
            ? `<span class="badge tag-heuristic" title="Detection heuristic: ${escapeHtml(c.detection_heuristic)}">DTO (${escapeHtml(c.detection_heuristic)})</span>`
            : "";

        // Card Assembly
        card.innerHTML = `
            <div class="component-card-header">
                <span class="component-card-title">${escapeHtml(c.name)}</span>
                <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
                    <span class="badge" style="background: rgba(56, 189, 248, 0.15); color: var(--accent-blue);">${roleLabel}</span>
                    <span class="badge" style="background: rgba(148, 163, 184, 0.15); color: var(--text-muted);">${kindLabel}</span>
                    ${heuristicBadge}
                </div>
            </div>
            <div class="component-meta">
                <span><b>Package:</b> <code>${escapeHtml(c.package || "default")}</code></span>
                <span><b>File:</b> <code>${escapeHtml(c.file)}</code></span>
            </div>
            ${annoBadges ? `<div style="display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.4rem;">${annoBadges}</div>` : ""}
            ${sectionsHtml}
        `;
        list.appendChild(card);
    });
}

// Gemma / Architecture Q&A
async function askQuestion(question) {
    if (!currentArchitecture) return;

    const chatMessages = document.getElementById("chatMessages");

    // Add User Bubble
    const userDiv = document.createElement("div");
    userDiv.className = "chat-bubble user-bubble";
    userDiv.textContent = question;
    chatMessages.appendChild(userDiv);

    // Add Loading Bot Bubble
    const botDiv = document.createElement("div");
    botDiv.className = "chat-bubble bot-bubble";
    botDiv.innerHTML = `
        <div class="bubble-header">Architecture Assistant</div>
        <div class="bubble-content"><em>Analyzing architecture metadata...</em></div>
    `;
    chatMessages.appendChild(botDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                architecture: currentArchitecture,
                analysis_id: currentArchitecture.analysis_id
            })
        });

        if (!response.ok) {
            let errMsg = "Chat request failed";
            try {
                const err = await response.json();
                errMsg = err.detail || errMsg;
            } catch (e) {
                errMsg = `Server error (HTTP ${response.status})`;
            }
            throw new Error(errMsg);
        }

        const data = await response.json();
        const formattedAnswer = formatMarkdown(data.answer);
        botDiv.querySelector(".bubble-content").innerHTML = formattedAnswer;

        // Header label
        const headerEl = botDiv.querySelector(".bubble-header");
        if (data.model) {
            if (data.model.startsWith("Gemma")) {
                headerEl.textContent = `Gemma Assistant (${data.model})`;
            } else {
                headerEl.textContent = data.model;
            }
        }
    } catch (err) {
        botDiv.querySelector(".bubble-content").innerHTML = `<span style="color: var(--accent-red)">⚠️ ${escapeHtml(err.message)}</span>`;
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatMarkdown(text) {
    if (!text) return "";
    let raw = text.toString();

    // Escape raw HTML first
    let escaped = escapeHtml(raw);

    // 1. Code blocks
    escaped = escaped.replace(/```([\s\S]*?)```/g, (match, code) => {
        return `<pre class="code-block">${code.trim()}</pre>`;
    });

    // 2. Inline code
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');

    // 3. Headers
    escaped = escaped.replace(/^### (.*$)/gim, '<h4 style="margin: 0.5rem 0 0.2rem 0; color: var(--accent-blue);">$1</h4>');
    escaped = escaped.replace(/^## (.*$)/gim, '<h3 style="margin: 0.6rem 0 0.25rem 0; color: var(--accent-blue);">$1</h3>');

    // 4. Bold & Italics
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // 5. Ordered lists (1. Item\n2. Item\n3. Item)
    escaped = escaped.replace(/(?:^\d+\.\s+.*(?:\n|$))+/gm, (match) => {
        const items = match.trim().split('\n').map(line => {
            const itemText = line.replace(/^\d+\.\s+/, '');
            return `<li>${itemText}</li>`;
        }).join('');
        return `<ol>${items}</ol>`;
    });

    // 6. Unordered lists (- Item\n- Item)
    escaped = escaped.replace(/(?:^-\s+.*(?:\n|$))+/gm, (match) => {
        const items = match.trim().split('\n').map(line => {
            const itemText = line.replace(/^-\s+/, '');
            return `<li>${itemText}</li>`;
        }).join('');
        return `<ul>${items}</ul>`;
    });

    // 7. Line breaks
    escaped = escaped.replace(/\n\n+/g, '<br/><br/>');
    escaped = escaped.replace(/\n/g, '<br/>');

    // Clean up unwanted breaks around lists/headings
    escaped = escaped.replace(/<\/h([34])><br\/>/g, '</h$1>');
    escaped = escaped.replace(/<\/ol><br\/>/g, '</ol>');
    escaped = escaped.replace(/<\/ul><br\/>/g, '</ul>');
    escaped = escaped.replace(/<pre([^>]*)><br\/>/g, '<pre$1>');
    escaped = escaped.replace(/<br\/><\/pre>/g, '</pre>');

    return escaped;
}
