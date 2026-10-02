// Code2UML AI Frontend Application

let currentArchitecture = null;
let currentMermaidStructuralCode = "";
let currentMermaidFullCode = "";
let currentMermaidUmlCode = "";
let showUsesEdges = false;
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
    try {
        const res = await fetch("/api/health");
        if (res.ok) {
            const data = await res.json();
            if (data.ai_configured) {
                badge.className = "badge badge-ai";
                badge.textContent = `🤖 Gemma Active: ${data.ai_model}`;
            } else {
                badge.className = "badge badge-ai offline";
                badge.textContent = "⚡ Offline Rules Engine Active (Gemma API Key Optional)";
            }
        }
    } catch (e) {
        badge.className = "badge badge-ai offline";
        badge.textContent = "⚡ Offline Rules Engine Active (Gemma API Key Optional)";
    }
}

function setupEventListeners() {
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");
    const browseBtn = document.getElementById("browseBtn");
    const sampleBtn = document.getElementById("sampleBtn");
    const closeErrorBtn = document.getElementById("closeErrorBtn");
    const toggleUses = document.getElementById("toggleUsesEdges");
    const toggleObsBtn = document.getElementById("toggleObsBtn");
    const obsList = document.getElementById("observationsList");

    if (toggleObsBtn && obsList) {
        toggleObsBtn.addEventListener("click", () => {
            if (obsList.style.display === "none") {
                obsList.style.display = "flex";
                toggleObsBtn.textContent = "Collapse";
            } else {
                obsList.style.display = "none";
                toggleObsBtn.textContent = "Expand";
            }
        });
    }

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
            codeToCopy = showUsesEdges ? currentMermaidFullCode : currentMermaidStructuralCode;
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

    // Suggestion Chips
    document.querySelectorAll(".suggestion-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const prompt = chip.getAttribute("data-prompt");
            if (prompt && currentArchitecture) {
                askQuestion(prompt);
            }
        });
    });
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

    // 2. Populate All 9 Summary Cards Directly From Summary
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

    // Chat welcome
    document.getElementById("chatProjectName").textContent = currentArchitecture.project || "your project";

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

let renderCounter = 0;

function cleanupStrayMermaidElements() {
    // Mermaid 10 sometimes appends error divs or svgs with ids like #dmermaid... or error-icon to document.body
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

    captionEl.textContent = `Showing ${activeRels} of ${totalRels} relationships`;
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

async function renderActiveDiagram() {
    const mermaidContainer = document.getElementById("mermaidOutput");
    if (!mermaidContainer) return;

    mermaidContainer.innerHTML = "";
    const activeCode = showUsesEdges ? currentMermaidFullCode : currentMermaidStructuralCode;

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
                console.warn("Mermaid parse error:", parseErr);
                cleanupStrayMermaidElements();
                mermaidContainer.innerHTML = `
                    <div class="error-banner" style="margin: 1rem; width: 100%;">
                        <span class="error-icon">⚠️</span>
                        <span>Failed to parse Mermaid diagram. Copy Mermaid is still available.</span>
                    </div>
                `;
                return;
            }
        }

        const { svg } = await mermaid.render(renderId, activeCode);
        mermaidContainer.innerHTML = svg;
    } catch (e) {
        console.warn("Mermaid render error:", e);
        cleanupStrayMermaidElements();
        mermaidContainer.innerHTML = `
            <div class="error-banner" style="margin: 1rem; width: 100%;">
                <span class="error-icon">⚠️</span>
                <span>Failed to render Mermaid diagram. Copy Mermaid is still available.</span>
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
                console.warn("Mermaid UML parse error:", parseErr);
                cleanupStrayMermaidElements();
                umlContainer.innerHTML = `
                    <div class="error-banner" style="margin: 1rem; width: 100%;">
                        <span class="error-icon">⚠️</span>
                        <span>Failed to parse UML Class Diagram. Copy Mermaid is still available.</span>
                    </div>
                `;
                return;
            }
        }

        const { svg } = await mermaid.render(renderId, currentMermaidUmlCode);
        umlContainer.innerHTML = svg;
    } catch (e) {
        console.warn("Mermaid UML render error:", e);
        cleanupStrayMermaidElements();
        umlContainer.innerHTML = `
            <div class="error-banner" style="margin: 1rem; width: 100%;">
                <span class="error-icon">⚠️</span>
                <span>Failed to render UML Class Diagram. Copy Mermaid is still available.</span>
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
        tr.innerHTML = `
            <td><span class="method-badge method-${escapeHtml(ep.http_method)}">${escapeHtml(ep.http_method)}</span></td>
            <td><code>${escapeHtml(ep.path)}</code></td>
            <td><b>${escapeHtml(ep.controller)}</b></td>
            <td><code>${escapeHtml(ep.method_name)}()</code></td>
            <td><small>${escapeHtml(ep.return_type || "void")}</small></td>
        `;
        tbody.appendChild(tr);
    });
}

function formatAnnotation(annoName, attrs) {
    if (!attrs || Object.keys(attrs).length === 0) {
        return `@${escapeHtml(annoName)}`;
    }
    const entries = Object.entries(attrs);
    if (entries.length === 1 && entries[0][0] === "value") {
        const val = entries[0][1];
        const isLiteral = !(typeof val === "string" && (val.includes(".") || val === "true" || val === "false" || !isNaN(val)));
        const formattedVal = isLiteral ? `"${escapeHtml(val)}"` : escapeHtml(val);
        return `@${escapeHtml(annoName)}(${formattedVal})`;
    }
    const pairs = entries.map(([k, v]) => {
        const isLiteral = !(typeof v === "string" && (v.includes(".") || v === "true" || v === "false" || !isNaN(v)));
        const valStr = isLiteral ? `"${escapeHtml(v)}"` : escapeHtml(v);
        return `${escapeHtml(k)} = ${valStr}`;
    }).join(", ");
    return `@${escapeHtml(annoName)}(${pairs})`;
}

function renderComponentCatalog(classes) {
    const list = document.getElementById("componentsList");
    list.innerHTML = "";

    if (classes.length === 0) {
        list.innerHTML = `<p style="color: var(--text-muted); padding: 1rem;">No components detected.</p>`;
        return;
    }

    classes.forEach(c => {
        const card = document.createElement("div");
        card.className = "component-card";

        // Role & Kind Badges
        const roleLabel = escapeHtml(c.type || "class");
        const kindLabel = c.is_interface ? "interface" : "class";

        // Annotations with Attributes
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

        // Card Assembly
        card.innerHTML = `
            <div class="component-card-header">
                <span class="component-card-title">${escapeHtml(c.name)}</span>
                <div style="display: flex; gap: 0.35rem;">
                    <span class="badge" style="background: rgba(56, 189, 248, 0.15); color: var(--accent-blue);">${roleLabel}</span>
                    <span class="badge" style="background: rgba(148, 163, 184, 0.15); color: var(--text-muted);">${kindLabel}</span>
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
                architecture: currentArchitecture
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
            if (data.model.includes("deterministic") || data.model.includes("offline")) {
                headerEl.textContent = "Deterministic rules engine (offline fallback)";
            } else {
                headerEl.textContent = `Gemma Assistant (${data.model})`;
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
