/**
 * Main Frontend Application Logic for Telugu AI Caller & CRM.
 * Manages Live Voice Calling, Excel Leads Ingestion, Autonomous Campaigns,
 * and Persistent Call Summaries & Transcripts.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Real-time Pipecat engine when the server enables it (/api/voice/config.js), else the classic engine
  const usePipecat = window.LC_VOICE_ENGINE === "pipecat" && typeof window.PipecatCallClient === "function";
  const caller = usePipecat ? new PipecatCallClient() : new VoiceCallClient();
  console.info(`Voice engine: ${usePipecat ? "pipecat (real-time)" : "classic"}`);
  let selectedLead = null;
  let campaignPollInterval = null;
  let selectedCallLanguage = ""; // auto-detect

  // UI Elements - Calling Station
  const startCallBtn = document.getElementById("startCallBtn");
  const endCallBtn = document.getElementById("endCallBtn");
  const doneSpeakingBtn = document.getElementById("doneSpeakingBtn");
  const phoneCallBtn = document.getElementById("phoneCallBtn");
  const testInput = document.getElementById("testTextInput");
  const sendTestBtn = document.getElementById("sendTestBtn");
  const transcriptBox = document.getElementById("transcriptBox");
  const callerStatus = document.getElementById("callerStatus");
  const waveContainer = document.getElementById("waveContainer");

  const activeLeadName = document.getElementById("activeLeadName");
  const activeLeadCompany = document.getElementById("activeLeadCompany");
  const activeLeadAvatar = document.getElementById("activeLeadAvatar");

  // Call setup: recording switch, reply wait time, status badges
  const recordToggle = document.getElementById("recordToggle");
  const recordToggleText = document.getElementById("recordToggleText");
  const waitSelect = document.getElementById("waitSelect");
  const recBadge = document.getElementById("recBadge");
  const replyTimeBadge = document.getElementById("replyTimeBadge");

  const readPref = (key, fallback) => {
    try { const v = localStorage.getItem(key); return v === null ? fallback : v; } catch (e) { return fallback; }
  };
  const writePref = (key, value) => {
    try { localStorage.setItem(key, value); } catch (e) { /* storage unavailable */ }
  };

  const updateRecordToggleText = () => {
    if (recordToggleText && recordToggle) {
      recordToggleText.innerText = recordToggle.checked ? "Record this call" : "Recording off";
    }
  };

  if (recordToggle) {
    recordToggle.checked = readPref("lc.recordCalls", "1") === "1";
    updateRecordToggleText();
    recordToggle.addEventListener("change", () => {
      writePref("lc.recordCalls", recordToggle.checked ? "1" : "0");
      updateRecordToggleText();
    });
  }

  if (waitSelect) {
    waitSelect.value = readPref("lc.replyWaitMs", waitSelect.value);
    caller.setSilenceTimeout(waitSelect.value);
    waitSelect.addEventListener("change", () => {
      caller.setSilenceTimeout(waitSelect.value);
      writePref("lc.replyWaitMs", waitSelect.value);
    });
  }

  const setCallSetupLocked = (locked) => {
    if (recordToggle) recordToggle.disabled = locked;
  };

  const startWebCall = () => {
    const leadId = selectedLead ? selectedLead.id : null;
    if (replyTimeBadge) replyTimeBadge.hidden = true;
    setCallSetupLocked(true);
    return caller.startCall(leadId, selectedCallLanguage, {
      record: recordToggle ? recordToggle.checked : false
    });
  };

  // Recording player shown in the summary and call-details windows
  const renderRecording = (containerId, recordingUrl) => {
    const box = document.getElementById(containerId);
    if (!box) return;
    if (!recordingUrl) {
      box.innerHTML = "";
      return;
    }
    box.innerHTML = `
      <div class="cs-recording-box">
        <div class="cs-recording-title">
          <span>🎙 Call recording</span>
          <a href="${recordingUrl}" target="_blank" rel="noopener">Open file</a>
        </div>
        <audio controls preload="metadata" src="${recordingUrl}"></audio>
      </div>`;
  };

  // Language Pill Selector
  window.setCallLanguage = (lang) => {
    selectedCallLanguage = lang;
    document.querySelectorAll(".lang-pill-btn").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-lang") === lang);
    });

    const engineIndicator = document.getElementById("engineIndicator");
    if (engineIndicator) {
      if (lang === "te-IN") engineIndicator.innerText = "Mode: Telugu (తెలుగు) Active";
      else if (lang === "hi-IN") engineIndicator.innerText = "Mode: Hindi (हिंदी) Active";
      else if (lang === "en-IN") engineIndicator.innerText = "Mode: English Active";
      else engineIndicator.innerText = "Mode: 🌐 Auto-Detect (Customer Matching)";
    }
  };

  // Callbacks
  caller.onStatusChange = (status) => {
    if (callerStatus) callerStatus.innerText = status;
  };

  caller.onWaveformUpdate = (isSpeaking) => {
    if (!waveContainer) return;
    if (isSpeaking) {
      waveContainer.classList.add("wave-active");
    } else {
      waveContainer.classList.remove("wave-active");
    }
  };

  caller.onTranscript = (sender, text, type, language) => {
    if (!transcriptBox) return;
    const bubble = document.createElement("div");
    bubble.className = `message-bubble bubble-${type}`;

    const isAi = type === 'ai';
    const iconSvg = isAi 
      ? `<svg class="icon icon-sm" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path></svg>`
      : `<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;

    let langTag = "";
    if (language === "te-IN") langTag = '<span class="bubble-lang-badge te">Telugu</span>';
    else if (language === "hi-IN") langTag = '<span class="bubble-lang-badge hi">Hindi</span>';
    else if (language === "en-IN") langTag = '<span class="bubble-lang-badge en">English</span>';

    const senderSpan = document.createElement("div");
    senderSpan.className = "bubble-sender";
    senderSpan.innerHTML = `<div style="display:flex; align-items:center; gap:5px;">${iconSvg} <span>${sender}</span></div>${langTag}`;

    const textP = document.createElement("div");
    textP.innerText = text;

    bubble.appendChild(senderSpan);
    bubble.appendChild(textP);
    transcriptBox.appendChild(bubble);

    transcriptBox.scrollTop = transcriptBox.scrollHeight;
  };

  caller.onSpeakingStateChange = (isSpeaking) => {
    if (doneSpeakingBtn) {
      doneSpeakingBtn.style.display = isSpeaking ? "inline-flex" : "none";
    }
  };

  caller.onRecordingStateChange = (isRecording) => {
    if (recBadge) recBadge.hidden = !isRecording;
  };

  caller.onResponseTime = (totalMs, timing) => {
    if (!replyTimeBadge) return;
    const seconds = (totalMs / 1000).toFixed(1);
    replyTimeBadge.innerText = `Reply ${seconds} s`;
    replyTimeBadge.classList.toggle("slow", totalMs > 3000);
    replyTimeBadge.title = timing
      ? `Customer stopped → AI started: ${seconds}s (speech-to-text ${timing.stt_ms || 0} ms · AI ${timing.llm_ms || 0} ms · first voice ${timing.tts_first_ms || 0} ms)`
      : `Customer stopped → AI started: ${seconds}s`;
    replyTimeBadge.hidden = false;
  };

  caller.onCallEnding = () => {
    if (doneSpeakingBtn) doneSpeakingBtn.style.display = "none";
    if (endCallBtn) {
      endCallBtn.disabled = true;
      endCallBtn.innerHTML = `<span>⏳ Finishing Call...</span>`;
    }
  };

  caller.onCallEnd = (summaryData) => {
    if (doneSpeakingBtn) doneSpeakingBtn.style.display = "none";
    if (startCallBtn) startCallBtn.style.display = "inline-flex";
    if (endCallBtn) {
      endCallBtn.disabled = false;
      endCallBtn.innerHTML = `<span>End Call</span>`;
      endCallBtn.style.display = "none";
    }
    setCallSetupLocked(false);
    showDealSummaryModal(summaryData);
    refreshLeads();
    refreshCallHistory();
  };

  if (doneSpeakingBtn) {
    doneSpeakingBtn.addEventListener("click", () => {
      caller.forceFinishTurn();
      doneSpeakingBtn.style.display = "none";
    });
  }

  // Button Listeners for Individual Live Call
  if (startCallBtn) {
    startCallBtn.addEventListener("click", () => {
      transcriptBox.innerHTML = "";
      startWebCall();
      startCallBtn.style.display = "none";
      endCallBtn.style.display = "inline-flex";
    });
  }

  if (endCallBtn) {
    endCallBtn.addEventListener("click", () => {
      caller.endCall(true);
      startCallBtn.style.display = "inline-flex";
      endCallBtn.style.display = "none";
      if (doneSpeakingBtn) doneSpeakingBtn.style.display = "none";
      setCallSetupLocked(false);
    });
  }

  if (sendTestBtn && testInput) {
    sendTestBtn.addEventListener("click", () => {
      const text = testInput.value.trim();
      if (!text) return;

      if (!caller.isCallActive) {
        transcriptBox.innerHTML = "";
        startWebCall().then(() => {
          setTimeout(() => {
            caller.sendTextMessage(text);
            testInput.value = "";
          }, 1200);
        });
        startCallBtn.style.display = "none";
        endCallBtn.style.display = "inline-flex";
      } else {
        caller.sendTextMessage(text);
        testInput.value = "";
      }
    });

    testInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        sendTestBtn.click();
      }
    });
  }

  // ===================================================================
  // SELECT LEAD & DISPLAY STORED CALL SUMMARY
  // ===================================================================
  window.selectLead = (lead) => {
    selectedLead = lead;
    document.querySelectorAll(".lead-card").forEach(el => {
      el.classList.remove("active");
      const dot = el.querySelector(".crm-lead-dot");
      if (dot) { dot.classList.remove("dot-orange"); dot.classList.add("dot-gray"); }
    });
    const card = document.getElementById(`lead-card-${lead.id}`);
    if (card) {
      card.classList.add("active");
      const dot = card.querySelector(".crm-lead-dot");
      if (dot) { dot.classList.remove("dot-gray"); dot.classList.add("dot-orange"); }
    }

    if (activeLeadName) activeLeadName.innerText = lead.name;
    if (activeLeadCompany) activeLeadCompany.innerText = `${lead.company || 'Business'} • ${lead.service_needed || 'Software'}`;
    if (activeLeadAvatar) activeLeadAvatar.innerText = lead.name.charAt(0);

    // Populate the Stored Call Summary Bar
    const leadLastSummaryText = document.getElementById("leadLastSummaryText");
    const leadLastCalledAt = document.getElementById("leadLastCalledAt");
    const leadActionItemText = document.getElementById("leadActionItemText");

    if (leadLastSummaryText) {
      if (lead.last_call_summary) {
        const stagePrefix = lead.last_call_stage ? `<span class="lead-status status-${lead.last_call_stage.toLowerCase()}" style="margin-right:6px;">${lead.last_call_stage.toUpperCase()}</span>` : '';
        leadLastSummaryText.innerHTML = `${stagePrefix}${lead.last_call_summary}`;
      } else {
        leadLastSummaryText.innerText = "No calls made yet for this lead. Click 'Start AI Call' to initiate outreach.";
      }
    }

    if (leadLastCalledAt) {
      leadLastCalledAt.innerText = lead.last_called_at ? `🕒 Last Call: ${lead.last_called_at}` : "Not called yet";
    }

    if (leadActionItemText) {
      leadActionItemText.innerText = lead.action_items ? `🎯 Next Action: ${lead.action_items}` : "";
    }

    // Render Enriched Intelligence if present
    const leadEnrichmentBox = document.getElementById("leadEnrichmentBox");
    const enrichmentDetailsText = document.getElementById("enrichmentDetailsText");
    const enrichmentTechTags = document.getElementById("enrichmentTechTags");

    if (leadEnrichmentBox) {
      if (lead.enrichment_data) {
        try {
          const enrichObj = typeof lead.enrichment_data === 'string' ? JSON.parse(lead.enrichment_data) : lead.enrichment_data;
          leadEnrichmentBox.style.display = "block";

          let details = `<strong>Org:</strong> ${enrichObj.company_name || lead.company || 'N/A'}`;
          if (enrichObj.employee_count_range) details += ` • <strong>Employees:</strong> ${enrichObj.employee_count_range}`;
          if (enrichObj.annual_revenue) details += ` • <strong>Rev:</strong> ${enrichObj.annual_revenue}`;
          if (lead.website || enrichObj.website_url) {
            const site = lead.website || enrichObj.website_url;
            details += ` • <a href="${site.startsWith('http') ? site : 'https://' + site}" target="_blank" style="color: var(--primary); text-decoration: underline;">${site}</a>`;
          }
          if (enrichmentDetailsText) enrichmentDetailsText.innerHTML = details;

          if (enrichmentTechTags) {
            enrichmentTechTags.innerHTML = "";
            const techs = enrichObj.technologies_detected || [];
            if (techs.length > 0) {
              techs.forEach(t => {
                const tag = document.createElement("span");
                tag.className = "badge-tag";
                tag.style.background = "#fff7ed";
                tag.style.color = "#c2410c";
                tag.style.border = "1px solid #fed7aa";
                tag.innerText = t;
                enrichmentTechTags.appendChild(tag);
              });
            }
          }
        } catch (e) {
          leadEnrichmentBox.style.display = "none";
        }
      } else {
        leadEnrichmentBox.style.display = "none";
      }
    }
  };

  // Lead Search Filter
  const leadSearchInput = document.getElementById("leadSearchInput");
  if (leadSearchInput) {
    leadSearchInput.addEventListener("input", () => {
      const q = leadSearchInput.value.toLowerCase().trim();
      document.querySelectorAll(".lead-card").forEach(card => {
        const text = card.innerText.toLowerCase();
        if (!q || text.includes(q)) {
          card.style.display = "block";
        } else {
          card.style.display = "none";
        }
      });
    });
  }

  // View Lead History button handler
  const viewLeadHistoryBtn = document.getElementById("viewLeadHistoryBtn");
  if (viewLeadHistoryBtn) {
    viewLeadHistoryBtn.addEventListener("click", async () => {
      if (!selectedLead) {
        alert("Please select a lead first.");
        return;
      }
      try {
        const resp = await fetch(`/api/leads/${selectedLead.id}/calls`);
        const data = await resp.json();
        if (data.calls && data.calls.length > 0) {
          window.openCallDetails(data.calls[0].id);
        } else {
          alert(`No past call records found for ${selectedLead.name}. Start a call to generate a summary!`);
        }
      } catch (e) {
        alert("Error loading call history: " + e.message);
      }
    });
  }

  // ===================================================================
  // DETAILED CALL SUMMARY & TRANSCRIPT VIEWER
  // ===================================================================
  window.openCallDetails = async (callId) => {
    try {
      const resp = await fetch(`/api/calls/${callId}`);
      const data = await resp.json();
      if (!data.call) return;
      const c = data.call;

      document.getElementById("modalCallLeadName").innerText = c.lead_name || c.phone_number || "Customer";
      document.getElementById("modalCallPhone").innerText = c.lead_phone || c.phone_number || "";
      document.getElementById("modalCallStage").innerText = (c.deal_stage || "QUALIFIED").toUpperCase();
      document.getElementById("modalCallStage").className = `lead-status status-${(c.deal_stage || 'qualified').toLowerCase()}`;
      document.getElementById("modalCallDate").innerText = c.created_at || "";
      document.getElementById("modalCallSummaryText").innerText = c.summary || "Call summary recorded in English.";
      document.getElementById("modalCallBudget").innerText = c.extracted_budget || "Not specified";
      document.getElementById("modalCallTimeline").innerText = c.extracted_timeline || "Not specified";
      renderRecording("modalCallRecording", c.recording_url);

      const container = document.getElementById("modalCallTranscriptContainer");
      container.innerHTML = "";

      let transcript = [];
      try {
        transcript = typeof c.transcript === 'string' ? JSON.parse(c.transcript) : c.transcript;
      } catch (e) {
        transcript = [];
      }

      if (Array.isArray(transcript) && transcript.length > 0) {
        transcript.forEach(msg => {
          const bubble = document.createElement("div");
          const isAi = msg.role === "assistant";
          bubble.className = `message-bubble ${isAi ? 'bubble-ai' : 'bubble-user'}`;
          bubble.style.maxWidth = "90%";
          bubble.style.padding = "8px 12px";
          bubble.style.fontSize = "0.85rem";
          const iconSvg = isAi
            ? `<svg class="icon icon-sm" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path></svg>`
            : `<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
          bubble.innerHTML = `
            <div style="font-weight:700; font-size:0.7rem; opacity:0.85; margin-bottom:2px; display:flex; align-items:center; gap:4px;">
              ${iconSvg} <span>${isAi ? 'AI Sales Caller' : 'Customer'}</span>
            </div>
            <div>${msg.content}</div>
          `;
          container.appendChild(bubble);
        });
      } else {
        container.innerHTML = `<div style="font-size:0.8rem; color:#94a3b8; padding:8px;">Transcript: ${c.transcript || c.summary || 'Recorded.'}</div>`;
      }

      document.getElementById("callDetailsModal").classList.add("open");
    } catch (e) {
      alert("Failed to load call details: " + e.message);
    }
  };

  const closeCallDetailsModal = document.getElementById("closeCallDetailsModal");
  if (closeCallDetailsModal) {
    closeCallDetailsModal.addEventListener("click", () => {
      document.getElementById("callDetailsModal").classList.remove("open");
    });
  }

  // ===================================================================
  // MODALS & ACTIONS CONTROLLERS (EXCEL, CAMPAIGN, LEAD, PHONE)
  // ===================================================================

  // 1. ADD NEW LEAD MODAL
  window.openLeadModal = () => {
    const modal = document.getElementById("leadModal");
    if (modal) modal.classList.add("open");
  };

  window.closeLeadModal = () => {
    const modal = document.getElementById("leadModal");
    if (modal) modal.classList.remove("open");
  };

  const openAddLeadBtn = document.getElementById("openAddLeadBtn");
  if (openAddLeadBtn) openAddLeadBtn.addEventListener("click", window.openLeadModal);

  const closeLeadModal = document.getElementById("closeLeadModal");
  if (closeLeadModal) closeLeadModal.addEventListener("click", window.closeLeadModal);

  const cancelLeadBtn = document.getElementById("cancelLeadBtn");
  if (cancelLeadBtn) cancelLeadBtn.addEventListener("click", window.closeLeadModal);

  const leadForm = document.getElementById("leadForm");
  if (leadForm) {
    leadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("leadName")?.value.trim() || "";
      const phone = document.getElementById("leadPhone")?.value.trim() || "";
      const company = document.getElementById("leadCompany")?.value.trim() || "";
      const service = document.getElementById("leadService")?.value || "Custom Software Development";
      const budget = document.getElementById("leadBudget")?.value.trim() || "Flexible";
      const timeline = document.getElementById("leadTimeline")?.value.trim() || "Immediate";
      const lang = document.getElementById("leadLang")?.value || "te-IN";
      const notes = document.getElementById("leadNotes")?.value.trim() || "";

      if (!name || !phone) {
        alert("Please enter both Lead Name and Phone Number.");
        return;
      }

      try {
        const resp = await fetch("/api/leads", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name,
            phone: phone,
            company: company,
            service_needed: service,
            budget: budget,
            timeline: timeline,
            preferred_language: lang,
            notes: notes,
            status: "NEW"
          })
        });

        const data = await resp.json();
        if (resp.ok && data.success) {
          alert(`? Lead "${name}" added to CRM Pipeline!`);
          window.closeLeadModal();
          leadForm.reset();
          await refreshLeads();
        } else {
          alert(data.error || "Failed to create lead.");
        }
      } catch (err) {
        alert("Network error: " + err.message);
      }
    });
  }

  // 2. EXCEL / CSV UPLOAD CONTROLLER
  window.openExcelModal = () => {
    const modal = document.getElementById("excelUploadModal");
    if (modal) modal.classList.add("open");
    const fileInput = document.getElementById("excelFileInput");
    if (fileInput) fileInput.value = "";
    const uploadBtn = document.getElementById("uploadFileBtn");
    if (uploadBtn) {
      uploadBtn.disabled = true;
      uploadBtn.innerText = "Upload & Import Leads";
    }
  };

  window.closeExcelModal = () => {
    const modal = document.getElementById("excelUploadModal");
    if (modal) modal.classList.remove("open");
  };

  const openUploadExcelBtn = document.getElementById("openUploadExcelBtn");
  if (openUploadExcelBtn) openUploadExcelBtn.addEventListener("click", window.openExcelModal);

  const sidebarUploadBtn = document.getElementById("sidebarUploadBtn");
  if (sidebarUploadBtn) sidebarUploadBtn.addEventListener("click", window.openExcelModal);

  const closeExcelModal = document.getElementById("closeExcelModal");
  if (closeExcelModal) closeExcelModal.addEventListener("click", window.closeExcelModal);

  const cancelExcelBtn = document.getElementById("cancelExcelBtn");
  if (cancelExcelBtn) cancelExcelBtn.addEventListener("click", window.closeExcelModal);

  const dropzone = document.getElementById("dropzone");
  const excelFileInput = document.getElementById("excelFileInput");
  const uploadFileBtn = document.getElementById("uploadFileBtn");

  if (dropzone && excelFileInput) {
    dropzone.addEventListener("click", () => excelFileInput.click());

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
        excelFileInput.files = e.dataTransfer.files;
        if (uploadFileBtn) {
          uploadFileBtn.disabled = false;
          uploadFileBtn.innerText = `Upload & Import (${e.dataTransfer.files[0].name})`;
        }
      }
    });

    excelFileInput.addEventListener("change", () => {
      if (excelFileInput.files && excelFileInput.files.length > 0) {
        if (uploadFileBtn) {
          uploadFileBtn.disabled = false;
          uploadFileBtn.innerText = `Upload & Import (${excelFileInput.files[0].name})`;
        }
      }
    });
  }

  if (uploadFileBtn) {
    uploadFileBtn.addEventListener("click", async () => {
      if (!excelFileInput || !excelFileInput.files || excelFileInput.files.length === 0) {
        alert("Please select an Excel (.xlsx, .xls) or CSV file first.");
        return;
      }

      uploadFileBtn.disabled = true;
      uploadFileBtn.innerText = "Parsing & Ingesting...";

      const formData = new FormData();
      formData.append("file", excelFileInput.files[0]);

      try {
        const resp = await fetch("/api/leads/upload-excel", {
          method: "POST",
          body: formData
        });
        const data = await resp.json();

        if (resp.ok && data.success) {
          alert(`? Import Complete!
Total Parsed: ${data.total_parsed} leads
Inserted: ${data.inserted}
Updated: ${data.updated}`);
          window.closeExcelModal();
          await refreshLeads();
        } else {
          alert(data.detail || data.error || (data.errors ? data.errors.join(", ") : "Failed to import leads."));
        }
      } catch (err) {
        alert("Upload error: " + err.message);
      } finally {
        uploadFileBtn.disabled = false;
        uploadFileBtn.innerText = "Upload & Import Leads";
      }
    });
  }

  // 3. AUTONOMOUS AUTO-CALLING CAMPAIGN CONTROLLER
  window.openCampaignModal = () => {
    const modal = document.getElementById("campaignModal");
    if (modal) modal.classList.add("open");
  };

  window.closeCampaignModal = () => {
    const modal = document.getElementById("campaignModal");
    if (modal) modal.classList.remove("open");
  };

  const openCampaignModalBtn = document.getElementById("openCampaignModalBtn");
  if (openCampaignModalBtn) openCampaignModalBtn.addEventListener("click", window.openCampaignModal);

  const closeCampaignModal = document.getElementById("closeCampaignModal");
  if (closeCampaignModal) closeCampaignModal.addEventListener("click", window.closeCampaignModal);

  const cancelCampaignBtn = document.getElementById("cancelCampaignBtn");
  if (cancelCampaignBtn) cancelCampaignBtn.addEventListener("click", window.closeCampaignModal);

  window.startAutonomousCampaign = async () => {
    const targetSel = document.getElementById("campaignTargetSelect")?.value || "new";
    const modeRadio = document.querySelector('input[name="campMode"]:checked');
    const mode = modeRadio ? modeRadio.value : "simulation";

    const btn = document.getElementById("startCampaignActionBtn");
    const origText = btn ? btn.innerText : "";
    if (btn) {
      btn.disabled = true;
      btn.innerText = "Launching Campaign...";
    }

    try {
      const resp = await fetch("/api/campaign/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: mode,
          delay_seconds: 2,
          target: targetSel,
          lead_id: targetSel === "selected" && selectedLead ? selectedLead.id : null
        })
      });

      const data = await resp.json();
      if (resp.ok && data.success) {
        window.closeCampaignModal();
        const banner = document.getElementById("campaignBanner");
        if (banner) banner.style.display = "block";
        const modeBadge = document.getElementById("campaignModeBadge");
        if (modeBadge) modeBadge.innerText = mode.toUpperCase();
        startCampaignPolling();
      } else {
        alert(data.detail || data.error || "Could not launch campaign.");
      }
    } catch (err) {
      alert("Campaign launch error: " + err.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerText = origText || "?? Launch Campaign Now";
      }
    }
  };

  const startCampaignActionBtn = document.getElementById("startCampaignActionBtn");
  if (startCampaignActionBtn) startCampaignActionBtn.addEventListener("click", window.startAutonomousCampaign);

  
  // ===================================================================
  // CAMPAIGN PAUSE, STOP & REFRESH ACTIONS (INTERACTIVE CONTROLLER)
  // ===================================================================
  window.refreshCampaignStatus = async () => {
    try {
      const resp = await fetch("/api/campaign/status");
      if (!resp.ok) return null;
      const status = await resp.json();
      if (!status) return null;

      const isRunning = Boolean(status.is_running);
      const isPaused = Boolean(status.is_paused);

      // 1. Status badge & dot in Campaigns view
      const badge = document.getElementById("campViewStatusBadge");
      const dot = document.getElementById("campViewStatusDot");
      if (badge) {
        if (isRunning && !isPaused) {
          badge.className = "crm-lead-badge badge-qualified";
          badge.style.background = "#ecfdf5";
          badge.style.color = "#059669";
          badge.innerText = "RUNNING";
          if (dot) dot.style.color = "#059669";
        } else if (isRunning && isPaused) {
          badge.className = "crm-lead-badge badge-demo";
          badge.style.background = "#fef3c7";
          badge.style.color = "#d97706";
          badge.innerText = "PAUSED";
          if (dot) dot.style.color = "#d97706";
        } else {
          badge.className = "crm-lead-badge";
          badge.style.background = "#f1f5f9";
          badge.style.color = "#64748b";
          badge.innerText = "IDLE";
          if (dot) dot.style.color = "#94a3b8";
        }
      }

      // 2. Pause / Resume button
      const pauseText = document.getElementById("campViewPauseText");
      const pauseIcon = document.getElementById("campViewPauseIcon");
      if (pauseText && pauseIcon) {
        if (isPaused) {
          pauseText.innerText = "Resume";
          pauseIcon.innerText = "▶";
        } else {
          pauseText.innerText = "Pause";
          pauseIcon.innerText = "⏸";
        }
      }

      // Sync top banner pause button if active
      const bannerPause = document.getElementById("pauseCampaignBtn");
      if (bannerPause) {
        bannerPause.innerText = isPaused ? "▶ Resume" : "⏸ Pause";
      }

      // 3. Current Lead Dialing text
      const currText = document.getElementById("campViewCurrentLeadText");
      if (currText) {
        if (status.current_lead) {
          const lName = typeof status.current_lead === 'object' ? status.current_lead.name : status.current_lead;
          const lPhone = typeof status.current_lead === 'object' ? (status.current_lead.phone || "") : "";
          currText.innerHTML = `📞 <strong>Currently Dialing:</strong> <span style="color:#0f172a; font-weight:700;">${lName}</span> (${lPhone}) - Trilingual AI pitch in progress...`;
        } else if (isRunning) {
          currText.innerHTML = `⏳ <em>Dialing next queued lead in pipeline...</em>`;
        } else if (status.completed_leads > 0 && status.completed_leads >= status.total_leads) {
          currText.innerHTML = `✅ <strong style="color:#059669;">Campaign Complete!</strong> All ${status.total_leads} leads contacted, qualified, and logged to CRM.`;
        } else {
          currText.innerHTML = `System ready. Click <strong>+ New Campaign</strong> above to launch autonomous batch calling across pipeline leads.`;
        }
      }

      // 4. Progress bar
      const pBar = document.getElementById("campViewProgressBar");
      const pct = status.progress_percent || 0;
      if (pBar) {
        pBar.style.width = `${pct}%`;
      }

      // 5. Counters
      const cText = document.getElementById("campViewContactedText");
      if (cText) {
        cText.innerText = `${status.completed_leads || 0} / ${status.total_leads || 0} Leads`;
      }

      const res = status.results || {};
      const dElem = document.getElementById("campViewDemos");
      if (dElem) dElem.innerText = res.demo_scheduled || 0;

      const wElem = document.getElementById("campViewWon");
      if (wElem) wElem.innerText = res.closed_won || 0;

      const fElem = document.getElementById("campViewFollow");
      if (fElem) fElem.innerText = res.follow_up || 0;

      // 6. Logs Feed
      const logsFeed = document.getElementById("campViewLogsFeed");
      if (logsFeed && Array.isArray(status.logs) && status.logs.length > 0) {
        logsFeed.innerHTML = status.logs.slice(-15).map(l => {
          const color = l.level === "warning" ? "#d97706" : (l.level === "error" ? "#dc2626" : "#334155");
          return `<div style="display:flex; gap:8px; align-items:flex-start;">
            <span style="color:#94a3b8; flex-shrink:0;">[${l.time}]</span>
            <span style="color:${color};">${l.message}</span>
          </div>`;
        }).join("");
        logsFeed.scrollTop = logsFeed.scrollHeight;
      }

      return status;
    } catch (err) {
      console.warn("refreshCampaignStatus error:", err);
      return null;
    }
  };

  window.toggleCampaignPause = async () => {
    try {
      const resp = await fetch("/api/campaign/status");
      const status = await resp.json();
      if (!status || !status.is_running) {
        const startNow = confirm("No campaign is currently running.\n\nWould you like to launch a new outbound AI calling campaign now?");
        if (startNow) {
          window.openCampaignModal();
        }
        return;
      }

      const endpoint = status.is_paused ? "/api/campaign/resume" : "/api/campaign/pause";
      await fetch(endpoint, { method: "POST" });
      await window.refreshCampaignStatus();
    } catch (err) {
      alert("Error toggling campaign pause state: " + err.message);
    }
  };

  window.stopActiveCampaign = async () => {
    try {
      const resp = await fetch("/api/campaign/status");
      const status = await resp.json();
      if (!status || !status.is_running) {
        alert("No auto-calling campaign is currently running.");
        return;
      }

      if (confirm("⚠️ Are you sure you want to STOP the running campaign?\n\nOngoing calls will conclude and remaining queue will be cancelled.")) {
        await fetch("/api/campaign/stop", { method: "POST" });
        if (campaignPollInterval) {
          clearInterval(campaignPollInterval);
          campaignPollInterval = null;
        }
        const banner = document.getElementById("campaignBanner");
        if (banner) banner.style.display = "none";
        await window.refreshCampaignStatus();
        await refreshLeads();
      }
    } catch (err) {
      alert("Error stopping campaign: " + err.message);
    }
  };

  function startCampaignPolling() {
    if (campaignPollInterval) clearInterval(campaignPollInterval);

    campaignPollInterval = setInterval(async () => {
        if (window.refreshCampaignStatus) await window.refreshCampaignStatus();
      try {
        const resp = await fetch("/api/campaign/status");
        const status = await resp.json();
        if (!status) return;

        const pBar = document.getElementById("campaignProgressBar");
        const pText = document.getElementById("campaignProgressText");
        const cLead = document.getElementById("campaignCurrentLead");
        const dCount = document.getElementById("campaignDemosCount");
        const wCount = document.getElementById("campaignWonCount");
        const fCount = document.getElementById("campaignFollowCount");

        if (pBar) pBar.style.width = `${status.progress_percent || status.progress_pct || 0}%`;
        if (pText) pText.innerText = `${status.completed_leads || status.completed_count || 0} / ${status.total_leads || 0}`;

        if (status.current_lead) {
          const lName = typeof status.current_lead === 'object' ? status.current_lead.name : status.current_lead;
          if (cLead) cLead.innerHTML = `?? Calling: <strong>${lName}</strong>`;
        } else if (status.is_running) {
          if (cLead) cLead.innerText = "Dialing next lead in queue...";
        }

        const res = status.results || {};
        if (dCount) dCount.innerText = res.demo_scheduled || res.demos_booked || 0;
        if (wCount) wCount.innerText = res.closed_won || 0;
        if (fCount) fCount.innerText = res.follow_up || res.follow_ups || 0;

        const pauseBtn = document.getElementById("pauseCampaignBtn");
        if (pauseBtn) {
          pauseBtn.innerText = status.is_paused ? "?? Resume" : "?? Pause";
        }

        if (!status.is_running && (status.total_leads || 0) > 0 && (status.completed_leads || status.completed_count || 0) >= status.total_leads) {
          clearInterval(campaignPollInterval);
          campaignPollInterval = null;
          if (cLead) cLead.innerHTML = `?? <strong>Campaign Complete!</strong> All leads processed. Call summaries recorded.`;
          await refreshLeads();
          await refreshCallHistory();
        }
      } catch (e) {
        console.error("Campaign polling error:", e);
      }
    }, 2000);
  }

  const pauseCampaignBtn = document.getElementById("pauseCampaignBtn");
  if (pauseCampaignBtn) {
    pauseCampaignBtn.addEventListener("click", async () => {
      const isPaused = pauseCampaignBtn.innerText.includes("Resume");
      const endpoint = isPaused ? "/api/campaign/resume" : "/api/campaign/pause";
      await fetch(endpoint, { method: "POST" });
    });
  }

  const stopCampaignBtn = document.getElementById("stopCampaignBtn");
  if (stopCampaignBtn) {
    stopCampaignBtn.addEventListener("click", async () => {
      if (confirm("Stop the running auto-calling campaign?")) {
        await fetch("/api/campaign/stop", { method: "POST" });
        if (campaignPollInterval) {
          clearInterval(campaignPollInterval);
          campaignPollInterval = null;
        }
        const banner = document.getElementById("campaignBanner");
        if (banner) banner.style.display = "none";
        await refreshLeads();
      }
    });
  }

  // 4. DIRECT PHONE DIALER
  window.dialSelectedLeadPhone = async () => {
    if (!selectedLead) {
      alert("Please select a lead first from the pipeline.");
      return;
    }
    const phone = selectedLead.phone;
    if (!phone) {
      alert("Selected lead has no phone number.");
      return;
    }

    const confirmed = confirm(`Initiate live outbound carrier phone call to ${selectedLead.name} (${phone}) via Exotel / Twilio?`);
    if (!confirmed) return;

    try {
      const resp = await fetch("/api/call/outbound", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: phone,
          lead_id: selectedLead.id
        })
      });
      const data = await resp.json();
      if (data.success) {
        alert(`?? Outbound telephone call initiated!
Call SID: ${data.call_sid || data.sid || 'Active'}
Your registered phone / client phone will ring shortly.`);
      } else {
        alert(data.error || "Failed to trigger phone call.");
      }
    } catch (e) {
      alert("Error initiating phone call: " + e.message);
    }
  };

  if (phoneCallBtn) phoneCallBtn.addEventListener("click", window.dialSelectedLeadPhone);

    // Voice Engine Language & Speaker Options
  window.updateVoiceOptions = () => {
    const langSelect = document.getElementById("voiceLangSelect");
    const voiceSelect = document.getElementById("voiceSelect");
    const testBtnText = document.getElementById("testVoiceBtnText");
    if (!langSelect || !voiceSelect) return;

    const lang = langSelect.value;
    voiceSelect.innerHTML = "";

    if (lang === "hi-IN") {
      voiceSelect.innerHTML = `
        <option value="aditya_hi_sales" selected>Aditya (Hindi Sales Closer)</option>
        <option value="simran_hi_sales">Simran (Hindi Sales Specialist)</option>
        <option value="ritu_hi_sales">Ritu (Hindi Conversational)</option>
      `;
      if (testBtnText) testBtnText.innerText = "Preview Hindi Voice";
    } else if (lang === "en-IN") {
      voiceSelect.innerHTML = `
        <option value="simran_en_sales" selected>Simran (English Sales Specialist)</option>
        <option value="ishita_en_customer">Ishita (English Customer Success)</option>
        <option value="aditya">Aditya (Indian English Professional)</option>
      `;
      if (testBtnText) testBtnText.innerText = "Preview English Voice";
    } else {
      voiceSelect.innerHTML = `
        <option value="kavitha_te_conversation" selected>Kavitha (Telugu Conversational)</option>
        <option value="pooja_te_conversation">Pooja (Telugu Conversational)</option>
        <option value="tarun_te_narration">Tarun (Telugu Professional Male)</option>
        <option value="kavitha">Kavitha (Standard)</option>
      `;
      if (testBtnText) testBtnText.innerText = "Preview Telugu Voice";
    }
  };

  // Voice Test Function
  window.testTtsVoice = async () => {
    const langSelect = document.getElementById("voiceLangSelect");
    const voiceSelect = document.getElementById("voiceSelect");
    const testBtn = document.getElementById("testVoiceBtn");

    const lang = langSelect ? langSelect.value : "te-IN";
    const speaker = voiceSelect ? voiceSelect.value : "kavitha_te_conversation";

    let sampleText = "నమస్కారం! మేము S P Associates Software Company నుండి మాట్లాడుతున్నాము. మీ వ్యాపారం కోసం అధునాతన సాఫ్ట్‌వేర్ మరియు AI సేవల గురించి మాట్లాడొచ్చా అండి?";
    if (lang === "hi-IN") {
      sampleText = "नमस्ते सर! मैं S P Associates Software Company से बात कर रहा हूँ। क्या हम आपके बिज़नेस के लिए सॉफ़्टवेयर और AI सेवाओं के बारे में 2 मिनट बात कर सकते हैं?";
    } else if (lang === "en-IN") {
      sampleText = "Hello! I am calling from S P Associates Software Company to discuss custom websites, mobile apps, and AI solutions for your business.";
    }

    if (testBtn) {
      testBtn.disabled = true;
      testBtn.innerHTML = `<span class="pulse-dot"></span> Generating voice audio...`;
    }

    try {
      const resp = await fetch("/api/tts/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: sampleText,
          speaker: speaker,
          language_code: lang
        })
      });

      if (resp.ok) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.play();
      } else {
        alert("Voice test failed: " + resp.statusText);
      }
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      if (testBtn) {
        testBtn.disabled = false;
        const btnText = lang === 'hi-IN' ? 'Preview Hindi Voice' : (lang === 'en-IN' ? 'Preview English Voice' : 'Preview Telugu Voice');
        testBtn.innerHTML = `<svg class="icon icon-sm" viewBox="0 0 24 24"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg> <span id="testVoiceBtnText">${btnText}</span>`;
      }
    }
  };

  // Deal Summary Modal
  function showDealSummaryModal(data) {
    const intel = data.intelligence || {};
    const modal = document.getElementById("dealSummaryModal");
    if (!modal) return;

    document.getElementById("summaryStage").innerText = (intel.deal_stage || 'QUALIFYING').toUpperCase();
    document.getElementById("summaryStage").className = `lead-status status-${(intel.deal_stage || 'qualified').toLowerCase()}`;
    document.getElementById("summarySentiment").innerText = intel.sentiment || 'neutral';
    document.getElementById("summaryBudget").innerText = intel.extracted_budget || 'Not specified';
    document.getElementById("summaryTimeline").innerText = intel.extracted_timeline || 'Not specified';
    document.getElementById("summaryRequirements").innerText = intel.extracted_requirements || 'Software Services';
    document.getElementById("summaryObjections").innerText = intel.objections_raised || 'None noted';
    document.getElementById("summaryAction").innerText = intel.action_items || 'Follow up with quotation.';
    document.getElementById("summaryOverview").innerText = intel.summary || 'Call finished.';
    renderRecording("summaryRecording", data.recording_url);

    modal.classList.add("open");
  }

  const closeDealModal = document.getElementById("closeDealModal");
  if (closeDealModal) {
    closeDealModal.addEventListener("click", () => {
      document.getElementById("dealSummaryModal").classList.remove("open");
    });
  }

  // Refresh functions
  async function refreshLeads() {
    try {
      const resp = await fetch("/api/leads");
      const data = await resp.json();
      const container = document.getElementById("leadsListContainer");
      const leadsCountBadge = document.getElementById("leadsCountBadge");

      if (leadsCountBadge && data.leads) {
        leadsCountBadge.innerText = `${data.leads.length} Total`;
      }

      if (!container || !data.leads || data.leads.length === 0) return;

      container.innerHTML = "";
      data.leads.forEach(lead => {
        const card = document.createElement("div");
        card.id = `lead-card-${lead.id}`;
        card.className = `lead-card ${selectedLead && selectedLead.id === lead.id ? 'active' : ''}`;
        card.onclick = () => window.selectLead(lead);

        let summaryHtml = "";
        if (lead.last_call_summary) {
          summaryHtml = `
            <div style="margin-top: 8px; padding-top: 6px; border-top: 1px dashed var(--border-color); font-size: 0.74rem; color: #93c5fd; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              📝 <strong>Summary:</strong> ${lead.last_call_summary}
            </div>
          `;
        }

        const isSelected = selectedLead && selectedLead.id === lead.id;
        card.className = `crm-lead-item lead-card ${isSelected ? 'active' : ''}`;
        card.innerHTML = `
          <div class="crm-lead-row">
            <span class="crm-lead-dot ${isSelected ? 'dot-orange' : 'dot-gray'}">●</span>
            <span class="crm-lead-item-name">${lead.name}</span>
          </div>
          <div class="crm-lead-badge-wrap">
            <span class="crm-lead-badge badge-${(lead.status || 'new').toLowerCase()}">${lead.status || 'NEW'}</span>
          </div>
        `;
        container.appendChild(card);
      });

      // Re-sync currently selected lead's summary if open
      if (selectedLead) {
        const updated = data.leads.find(l => l.id === selectedLead.id);
        if (updated) window.selectLead(updated);
      }
    } catch (e) {
      console.error("Failed to refresh leads:", e);
    }
  }

  async function refreshCallHistory() {
    try {
      const resp = await fetch("/api/calls");
      const data = await resp.json();
      const list = document.getElementById("recentCallsList");
      if (!list || !data.calls) return;

      list.innerHTML = "";
      data.calls.slice(0, 6).forEach(call => {
        const item = document.createElement("div");
        item.className = "tip-item cs-call-item";
        item.onclick = () => window.openCallDetails(call.id);
        item.title = "Click to view summary, transcript and recording";
        const stageUpper = (call.deal_stage || 'QUALIFIED').toUpperCase();
        const isQualified = stageUpper.includes('QUALIFIED') || stageUpper.includes('DEMO');
        item.className = "crm-recent-item cs-call-item";
        item.innerHTML = `
          <div class="crm-recent-left">
            <div class="crm-recent-top-line">
              <span class="crm-recent-dot ${isQualified ? 'dot-green' : 'dot-orange'}">●</span>
              <span class="crm-recent-name">${call.lead_name || 'Web Lead'}</span>
            </div>
            <div class="crm-recent-badge-wrap">
              <span class="crm-recent-badge badge-${(call.deal_stage || 'qualified').toLowerCase()}">${stageUpper}</span>
            </div>
          </div>
          <div class="crm-recent-right">
            <span class="crm-recent-dur">${call.recording_url ? '🎙 ' : ''}${call.duration_seconds}s ↗</span>
            <span class="crm-recent-time">12:46 PM</span>
          </div>
        `;
        list.appendChild(item);
      });
    } catch (e) {
      console.error("Failed to refresh calls:", e);
    }
  }

  // Initial call on load
  refreshLeads();

  // ===================================================================
  // OUTPERO SAAS WEBSITE TABS, API SANDBOX & BILLING STORE
  // ===================================================================

  let currentMainTab = "landing";
  let activePaymentMethod = "UPI";
  let selectedCheckoutAmount = 4999;
  let selectedCheckoutPlan = "Business Growth";

  
  // ===================================================================
  // CRM VIEW SWITCHER (Dashboard, Leads, Calling Station, Campaigns, Automations, Analytics)
  // ===================================================================
  window.switchCrmView = (viewName) => {
    // 1. Update left sidebar active button
    document.querySelectorAll(".crm-sidebar-menu .crm-nav-item").forEach(btn => btn.classList.remove("active"));
    const activeBtn = document.getElementById("navItem" + viewName.charAt(0).toUpperCase() + viewName.slice(1));
    if (activeBtn) activeBtn.classList.add("active");

    // 2. Hide all sub-views and show the selected one
    const views = {
      calling: document.getElementById("crmViewCalling"),
      dashboard: document.getElementById("crmViewDashboard"),
      leads: document.getElementById("crmViewLeads"),
      campaigns: document.getElementById("crmViewCampaigns"),
      automations: document.getElementById("crmViewAutomations"),
      analytics: document.getElementById("crmViewAnalytics")
    };

    Object.keys(views).forEach(k => {
      if (views[k]) {
        views[k].style.display = (k === viewName) ? (k === "calling" ? "grid" : "flex") : "none";
      }
    });

    // 3. Update Page Title & Subtitle based on active view
    const pageTitle = document.getElementById("crmPageTitle");
    const pageSub = document.getElementById("crmPageSub");
    const pageActions = document.getElementById("crmPageActions");

    if (pageTitle && pageSub) {
      if (viewName === "calling") {
        pageTitle.innerText = "Live Sales Pipeline & Calling Station";
        pageSub.innerText = "AI-powered calling, follow-ups, and deal closure";
        if (pageActions) pageActions.style.display = "flex";
      } else if (viewName === "dashboard") {
        pageTitle.innerText = "Executive Sales Dashboard";
        pageSub.innerText = "Real-time revenue metrics, active agents & pipeline velocity";
        if (pageActions) pageActions.style.display = "flex";
      } else if (viewName === "leads") {
        pageTitle.innerText = "Leads Pipeline & Contact Management";
        pageSub.innerText = "Manage prospect records, upload CSV/Excel & enrich contact intelligence";
        if (pageActions) pageActions.style.display = "none";
      } else if (viewName === "campaigns") {
        pageTitle.innerText = "Autonomous Outbound Campaigns";
        pageSub.innerText = "Batch dial prospects with multilingual AI sales employees";
        if (pageActions) pageActions.style.display = "none";
        if (window.refreshCampaignStatus) window.refreshCampaignStatus();
      } else if (viewName === "automations") {
        pageTitle.innerText = "Workflow Automations & Event Triggers";
        pageSub.innerText = "WhatsApp brochures, calendar sync, and post-call notifications";
        if (pageActions) pageActions.style.display = "none";
      } else if (viewName === "analytics") {
        pageTitle.innerText = "Executive Sales Intelligence & Voice Analytics";
        pageSub.innerText = "Conversion funnels, speech sentiment breakdown, and agent performance";
        if (pageActions) pageActions.style.display = "none";
        if (window.loadAnalyticsDashboard) window.loadAnalyticsDashboard();

      }
    }
  };

  window.switchMainTab = (tabName, targetSectionId = null) => {
    currentMainTab = tabName;
    const viewLanding = document.getElementById("viewLanding");
    const viewCrm = document.getElementById("viewCrm");
    const navLaunchCrmText = document.getElementById("navLaunchCrmText");

    // Remove active from all nav tab buttons
    document.querySelectorAll(".nav-tab-btn").forEach(btn => btn.classList.remove("active"));

    if (tabName === "analytics") {
      window.switchMainTab("crm");
      window.switchCrmView("analytics");
      return;
    }

    if (tabName === "crm") {
      document.body.classList.add("crm-mode");
      if (viewLanding) viewLanding.style.display = "none";
      if (viewCrm) viewCrm.style.display = "block";
      const btnCrm = document.getElementById("tabBtnCrm");
      if (btnCrm) btnCrm.classList.add("active");
      if (navLaunchCrmText) navLaunchCrmText.innerText = "← Overview";
      const navCreditChip = document.getElementById("navCreditChip");
      if (navCreditChip) navCreditChip.style.display = "inline-flex";
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      document.body.classList.remove("crm-mode");
      if (viewLanding) viewLanding.style.display = "block";
      if (viewCrm) viewCrm.style.display = "none";
      if (navLaunchCrmText) navLaunchCrmText.innerText = "Start Free Trial ↗";
      const navCreditChip = document.getElementById("navCreditChip");
      if (navCreditChip) navCreditChip.style.display = "none";

      if (targetSectionId === "voiceSection") {
        const btn = document.getElementById("tabBtnVoice");
        if (btn) btn.classList.add("active");
        window.scrollToSection("voiceSection");
      } else if (targetSectionId === "apiSection") {
        const btn = document.getElementById("tabBtnApi");
        if (btn) btn.classList.add("active");
        window.scrollToSection("apiSection");
      } else if (targetSectionId === "pricingSection") {
        const btn = document.getElementById("tabBtnPricing");
        if (btn) btn.classList.add("active");
        window.scrollToSection("pricingSection");
      } else if (targetSectionId === "employeesSection") {
        const btn = document.getElementById("tabBtnEmployees");
        if (btn) btn.classList.add("active");
        window.scrollToSection("employeesSection");

      } else {
        const btn = document.getElementById("tabBtnLanding");
        if (btn) btn.classList.add("active");
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    }
  };

  window.scrollToSection = (sectionId) => {
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  // Interactive Voice Showcase
  window.playVoiceScenario = async (lang, scenarioId) => {
    let sampleText = "";
    let speaker = "kavitha_te_conversation";
    let langCode = "te-IN";

    if (lang === "te") {
      sampleText = "సరేనండి, అర్థమైంది. మీ కిరాణా వ్యాపారానికి మొబైల్ ఆర్డరింగ్ యాప్ మరియు బిల్లింగ్ సాఫ్ట్‌వేర్ రెండూ చాలా అవసరం. మా వద్ద ₹30,000 నుండి ప్రారంభమవుతాయి. రేపు ఉదయం 11:00కి 10 నిమిషాల జూమ్ డెమో చూపిస్తాము, ఓకేనా అండి?";
      speaker = "kavitha_te_conversation";
      langCode = "te-IN";
    } else if (lang === "hi") {
      sampleText = "जी बिल्कुल सर, समझ गया। बजट को लेकर चिंता मत कीजिए, हमारे पास आसान माइलस्टोन पेमेंट्स हैं। आपकी कंपनी के लिए फ़्लीट ट्रैकिंग सिस्टम 3 हफ़्ते में तैयार हो जाएगा। क्या कल सुबह 11 बजे लाइव ज़ूम डेमो फ़िक्स करें?";
      speaker = "pooja";
      langCode = "hi-IN";
    } else {
      sampleText = "That makes total sense, doctor! We can launch your automated WhatsApp and AI phone appointment system within 10 days. Shall we schedule a quick 10-minute live Zoom demo for tomorrow morning at 11:00 AM?";
      speaker = "tarun";
      langCode = "en-IN";
    }

    try {
      const resp = await fetch("/api/tts/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: sampleText,
          language_code: langCode,
          speaker: speaker
        })
      });

      if (!resp.ok) {
        throw new Error("TTS preview failed");
      }

      const blob = await resp.blob();
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      audio.play();
    } catch (err) {
      alert("Voice playback notice: " + err.message);
    }
  };

  // Code Snippet Switcher
  const CODE_SNIPPETS = {
    curl: `curl -X POST http://localhost:8000/api/v1/calls/dispatch \\
  -H "Authorization: Bearer lc_live_sp_assoc_7894a1b2" \\
  -H "Content-Type: application/json" \\
  -d '{
    "lead_name": "Ramesh Naidu",
    "phone": "+919848011223",
    "company": "Naidu Supermarkets",
    "service": "Mobile App & Billing",
    "budget": "₹75,000",
    "language": "te-IN"
  }'`,

    python: `import httpx

API_KEY = "lc_live_sp_assoc_7894a1b2"
BASE_URL = "http://localhost:8000"

payload = {
    "lead_name": "Ramesh Naidu",
    "phone": "+919848011223",
    "company": "Naidu Supermarkets",
    "service": "Mobile App & Billing",
    "budget": "₹75,000",
    "language": "te-IN"
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

with httpx.Client() as client:
    resp = client.post(f"{BASE_URL}/api/v1/calls/dispatch", json=payload, headers=headers)
    result = resp.json()
    print("Call ID:", result["call_id"])
    print("Deal Stage:", result["deal_stage"])
    print("Executive Summary:", result["summary"])
    print("Minutes Billed:", result["billing"]["minutes_billed"])`,

    js: `const axios = require('axios');

const API_KEY = 'lc_live_sp_assoc_7894a1b2';

async function dispatchLeadCall() {
  const response = await axios.post('http://localhost:8000/api/v1/calls/dispatch', {
    lead_name: 'Ramesh Naidu',
    phone: '+919848011223',
    company: 'Naidu Supermarkets',
    service: 'Mobile App & Billing',
    budget: '₹75,000',
    language: 'te-IN'
  }, {
    headers: {
      'Authorization': \`Bearer \${API_KEY}\`,
      'Content-Type': 'application/json'
    }
  });

  console.log('Call Closed:', response.data.deal_stage);
  console.log('English Summary:', response.data.summary);
}

dispatchLeadCall();`
  };

  let activeCodeLang = "curl";
  window.switchCodeTab = (lang) => {
    activeCodeLang = lang;
    document.querySelectorAll(".code-lang-btn").forEach(btn => btn.classList.remove("active"));
    const activeBtn = document.getElementById(`btnCode${lang.charAt(0).toUpperCase() + lang.slice(1)}`);
    if (activeBtn) activeBtn.classList.add("active");

    const pre = document.getElementById("codeDisplayPre");
    if (pre && CODE_SNIPPETS[lang]) {
      pre.innerText = CODE_SNIPPETS[lang];
    }
  };

  window.copyActiveCode = () => {
    const text = CODE_SNIPPETS[activeCodeLang];
    navigator.clipboard.writeText(text);
    alert("Code snippet copied to clipboard!");
  };

  // API Sandbox Runner
  window.runApiSandboxTest = async () => {
    const name = document.getElementById("sandboxName").value.trim() || "Kalyan Kumar";
    const phone = document.getElementById("sandboxPhone").value.trim() || "+91 9848011223";
    const company = document.getElementById("sandboxCompany").value.trim() || "Kalyan Textiles";
    const service = document.getElementById("sandboxService").value.trim() || "E-Commerce & Billing";
    const runBtn = document.getElementById("sandboxRunBtn");
    const resBox = document.getElementById("sandboxResponseBox");

    runBtn.disabled = true;
    runBtn.innerText = "⏳ Calling...";
    resBox.style.display = "block";
    resBox.innerText = `[Dispatching API Call...] Connecting AI agent for ${name} (${company})...\nExecuting sales dialogue & objection handling...`;

    try {
      const resp = await fetch("/api/v1/calls/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_name: name,
          phone: phone,
          company: company,
          service: service,
          budget: "₹50,000",
          language: "te-IN"
        })
      });

      const data = await resp.json();
      resBox.innerText = JSON.stringify(data, null, 2);

      // Update credit balance on navbar
      if (data.billing && data.billing.remaining_credits_inr !== undefined) {
        const balEl = document.getElementById("navCreditBalance");
        const minEl = document.getElementById("navMinutesBalance");
        if (balEl) balEl.innerText = Number(data.billing.remaining_credits_inr).toFixed(2);
        if (minEl) minEl.innerText = Math.round(Number(data.billing.remaining_credits_inr) / 5.0);
      }

      refreshLeads();
      refreshRecentCalls();
    } catch (err) {
      resBox.innerText = `API Call Error: ${err.message}`;
    } finally {
      runBtn.disabled = false;
      runBtn.innerText = "🚀 Dispatch Call via API";
    }
  };

  // Checkout & Billing Modal
  window.openCheckoutModal = (planName, amount) => {
    selectedCheckoutPlan = planName;
    selectedCheckoutAmount = amount;

    const modal = document.getElementById("checkoutModal");
    const planTitle = document.getElementById("checkoutPlanTitle");
    const planAmount = document.getElementById("checkoutPlanAmount");
    const minutesCredited = document.getElementById("checkoutMinutesCredited");
    const btnPayAmountText = document.getElementById("btnPayAmountText");

    if (planTitle) planTitle.innerText = planName;
    if (planAmount) planAmount.innerText = `₹${Number(amount).toLocaleString('en-IN')}.00`;
    if (btnPayAmountText) btnPayAmountText.innerText = Number(amount).toLocaleString('en-IN');

    const rate = amount >= 14999 ? 3.75 : (amount >= 4999 ? 4.16 : 5.0);
    const estimatedMins = Math.round(amount / rate);
    if (minutesCredited) {
      minutesCredited.innerText = `⚡ ~${estimatedMins} Connected Minutes Talk-Time Credited (@ ₹${rate}/min)`;
    }

    if (modal) modal.classList.add("open");
  };

  window.setCalcAmount = (amount, btnElem) => {
    selectedCheckoutAmount = amount;
    selectedCheckoutPlan = `Pay-As-You-Go (${amount >= 5000 ? '1,000' : (amount >= 2500 ? '500' : (amount >= 1000 ? '200' : '100'))} Mins)`;

    document.querySelectorAll(".quick-amount-pill").forEach(p => p.classList.remove("active"));
    if (btnElem) btnElem.classList.add("active");

    const btnBuy = document.getElementById("btnCalcBuy");
    if (btnBuy) {
      btnBuy.innerText = `💳 Top Up ₹${Number(amount).toLocaleString('en-IN')}`;
      btnBuy.onclick = () => window.openCheckoutModal(selectedCheckoutPlan, amount);
    }
  };

  window.selectPaymentMethod = (method, elem) => {
    activePaymentMethod = method;
    document.querySelectorAll(".payment-opt-btn").forEach(b => b.classList.remove("active"));
    if (elem) elem.classList.add("active");
  };

  window.executeSimulatedCheckout = async () => {
    const email = document.getElementById("checkoutEmail").value.trim() || "developer@client.com";
    const company = document.getElementById("checkoutCompanyName").value.trim() || "S P Associates Client";
    const payBtn = document.getElementById("btnPayAction");

    payBtn.disabled = true;
    payBtn.innerText = "⏳ Processing Payment...";

    try {
      const resp = await fetch("/api/v1/billing/purchase-credits", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_name: selectedCheckoutPlan,
          amount_inr: selectedCheckoutAmount,
          payment_method: activePaymentMethod,
          customer_email: email
        })
      });

      const res = await resp.json();
      if (!res.success) throw new Error(res.detail || "Payment failed");

      // Update navbar balance
      const balEl = document.getElementById("navCreditBalance");
      const minEl = document.getElementById("navMinutesBalance");
      if (balEl && res.order) {
        const current = Number(balEl.innerText.replace(/,/g, '')) || 0;
        const updated = current + selectedCheckoutAmount;
        balEl.innerText = updated.toFixed(2);
        if (minEl) minEl.innerText = Math.round(updated / 5.0);
      }

      document.getElementById("checkoutModal").classList.remove("open");
      alert(`🎉 Payment Successful!\n\nOrder ID: ${res.order.order_id}\nInvoice: ${res.order.invoice_number}\nAmount: ₹${selectedCheckoutAmount}\nMinutes Credited: ${res.order.minutes_credited} mins\n\nYour API Key now has active talk-time credits.`);
      location.reload();
    } catch (err) {
      alert("Payment Error: " + err.message);
    } finally {
      payBtn.disabled = false;
      payBtn.innerText = `🔒 Complete Payment (₹${selectedCheckoutAmount})`;
    }
  };

  // Generate Key Modal
  window.openGenerateKeyModal = () => {
    const modal = document.getElementById("generateKeyModal");
    if (modal) modal.classList.add("open");
  };

  window.executeGenerateKey = async () => {
    const name = document.getElementById("genKeyName").value.trim() || "Web App Key";
    const email = document.getElementById("genKeyEmail").value.trim() || "dev@spassociates.com";
    const tier = document.getElementById("genKeyTier").value;

    try {
      const resp = await fetch("/api/v1/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key_name: name,
          user_email: email,
          plan_tier: tier,
          initial_credits: 500.0
        })
      });

      const data = await resp.json();
      if (!data.success) throw new Error(data.detail || "Failed to create key");

      document.getElementById("generateKeyModal").classList.remove("open");
      alert(`🔑 New API Key Generated Successfully!\n\nKey: ${data.key.api_key}\nPlan: ${data.key.plan_tier}\nInitial Credits: ₹${data.key.credits_inr}\n\nMake sure to save it safely!`);
      location.reload();
    } catch (err) {
      alert("Error: " + err.message);
    }
  };

  // ===================================================================
  // THIRD-PARTY PROVIDER INTEGRATION ACTIONS & MODALS
  // ===================================================================

  window.testProviderConnection = async (providerType, providerName, btnElem) => {
    const originalText = btnElem ? btnElem.innerHTML : "";
    if (btnElem) {
      btnElem.disabled = true;
      btnElem.innerHTML = "⏳ Testing...";
    }

    const badgeElem = document.getElementById(`test-badge-${providerType}-${providerName}`);
    if (badgeElem) {
      badgeElem.className = "badge-tag";
      badgeElem.innerText = "Testing...";
    }

    try {
      const resp = await fetch(`/api/integrations/providers/${providerType}/${providerName}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      const data = await resp.json();
      const res = data.result || {};

      if (res.success) {
        if (badgeElem) {
          badgeElem.className = "badge-tag live";
          badgeElem.innerText = `✓ Verified (${res.latency_ms || 0}ms)`;
        }
        alert(`✅ Provider Connection Verified!

Provider: ${providerName.toUpperCase()} (${providerType})
Status: Active & Reachable
Latency: ${res.latency_ms}ms
Message: ${res.message}`);
      } else {
        if (badgeElem) {
          badgeElem.className = "lead-status status-lost";
          badgeElem.innerText = "✗ Failed";
        }
        alert(`❌ Connection Test Failed!

Provider: ${providerName.toUpperCase()} (${providerType})
Error: ${res.message}

Please check your API keys or network connection in Settings.`);
      }
    } catch (err) {
      if (badgeElem) {
        badgeElem.className = "lead-status status-lost";
        badgeElem.innerText = "✗ Error";
      }
      alert(`⚠️ Test Network Error: ${err.message}`);
    } finally {
      if (btnElem) {
        btnElem.disabled = false;
        btnElem.innerHTML = originalText || "⚡ Test Connection";
      }
    }
  };

    // Admin Console / System Settings Modal -> Redirect to Dashboard
  window.openAdminSettingsModal = () => {
    window.switchMainTab("crm");
    window.switchCrmView("dashboard");
  };

  window.closeAdminSettingsModal = () => {};

  window.openConfigureProviderModal = (providerType, providerName) => {
    const modal = document.getElementById("providerConfigModal");
    const titleEl = document.getElementById("providerModalTitle");
    const typeInput = document.getElementById("providerConfigType");
    const nameInput = document.getElementById("providerConfigName");
    const keyInput = document.getElementById("providerConfigKey");

    if (typeInput) typeInput.value = providerType;
    if (nameInput) nameInput.value = providerName;
    if (keyInput) keyInput.value = "";
    if (titleEl) titleEl.innerText = `Configure ${providerName.toUpperCase()} (${providerType})`;

    if (modal) modal.classList.add("open");
  };

  window.saveProviderConfig = async () => {
    const pType = document.getElementById("providerConfigType")?.value;
    const pName = document.getElementById("providerConfigName")?.value;
    const isEnabled = document.getElementById("providerConfigEnabled")?.checked ?? true;
    const keyVal = document.getElementById("providerConfigKey")?.value.trim();

    if (!pType || !pName) return;

    const payload = {
      is_enabled: isEnabled,
      config: {}
    };

    if (keyVal) {
      if (pName === "exotel") {
        payload.config["api_key"] = keyVal;
      } else if (pName === "apollo") {
        payload.config["api_key"] = keyVal;
      } else if (pName === "apify") {
        payload.config["api_token"] = keyVal;
      } else if (pName === "meta_whatsapp") {
        payload.config["access_token"] = keyVal;
      } else if (pName === "google_calendar") {
        payload.config["client_secret"] = keyVal;
      } else {
        payload.config["api_key"] = keyVal;
      }
    }

    try {
      const resp = await fetch(`/api/integrations/providers/${pType}/${pName}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (!data.success) throw new Error(data.detail || "Failed to update provider");

      document.getElementById("providerConfigModal")?.classList.remove("open");
      alert(`🎉 Settings for ${pName.toUpperCase()} saved successfully!`);
      location.reload();
    } catch (err) {
      alert(`Error saving provider settings: ${err.message}`);
    }
  };


  // ===================================================================
  // PHASE 3: LEAD DISCOVERY & CONTACT ENRICHMENT (APOLLO & APIFY)
  // ===================================================================

  let discoveredProspectsList = [];

  window.openDiscoverLeadsModal = () => {
    const modal = document.getElementById("discoverLeadsModal");
    if (modal) modal.classList.add("open");
  };

  window.toggleDiscoverProvider = (provider) => {
    const titlesGroup = document.getElementById("discoverTitlesGroup");
    const labelApollo = document.getElementById("labelRadioApollo");
    const labelApify = document.getElementById("labelRadioApify");

    if (provider === "apollo") {
      if (titlesGroup) titlesGroup.style.display = "block";
      if (labelApollo) { labelApollo.style.borderColor = "var(--primary)"; labelApollo.style.background = "#fff7ed"; }
      if (labelApify) { labelApify.style.borderColor = "var(--border-light)"; labelApify.style.background = "#ffffff"; }
    } else {
      if (titlesGroup) titlesGroup.style.display = "none";
      if (labelApollo) { labelApollo.style.borderColor = "var(--border-light)"; labelApollo.style.background = "#ffffff"; }
      if (labelApify) { labelApify.style.borderColor = "var(--primary)"; labelApify.style.background = "#fff7ed"; }
    }
  };

  window.executeDiscoverLeads = async () => {
    const btn = document.getElementById("runDiscoverBtn");
    const provider = document.querySelector('input[name="discoverProvider"]:checked')?.value || "apollo";
    const industries = document.getElementById("discoverIndustries")?.value.split(",").map(s => s.trim()).filter(Boolean) || ["Software"];
    const locations = document.getElementById("discoverLocations")?.value.split(",").map(s => s.trim()).filter(Boolean) || ["Hyderabad"];
    const titles = document.getElementById("discoverTitles")?.value.split(",").map(s => s.trim()).filter(Boolean) || ["CEO", "Founder"];
    const servicePitch = document.getElementById("discoverServicePitch")?.value.trim() || "Custom Web App & AI Automation";
    const limit = parseInt(document.getElementById("discoverLimit")?.value || "10", 10);

    const origText = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = "⏳ Searching Prospects...";
    }

    try {
      const resp = await fetch("/api/leads/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: provider,
          filters: {
            industries: industries,
            locations: locations,
            titles: titles,
            service_needed: servicePitch
          },
          limit: limit
        })
      });

      const data = await resp.json();
      if (!resp.ok || !data.success) {
        if (data.error && data.error.includes("not configured")) {
          alert(`⚠️ ${data.error}\nPlease ensure your provider credentials are set in your environment file.`);
        } else {
          alert(`Discovery Search Failed: ${data.error || data.detail || 'Unknown error'}`);
        }
        return;
      }

      discoveredProspectsList = data.leads || [];
      renderDiscoveredLeadsList();
    } catch (err) {
      alert(`Network Error: ${err.message}`);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origText || "⚡ Run Live Search";
      }
    }
  };

  function renderDiscoveredLeadsList() {
    const container = document.getElementById("discoverResultsContainer");
    const listEl = document.getElementById("discoverLeadsList");
    const countLabel = document.getElementById("discoverCountLabel");
    const importBtn = document.getElementById("importDiscoveredBtn");

    if (!container || !listEl) return;

    if (discoveredProspectsList.length === 0) {
      container.style.display = "block";
      listEl.innerHTML = '<div style="font-size: 0.78rem; color: var(--text-muted); text-align: center; padding: 10px;">No leads found matching your criteria.</div>';
      if (importBtn) {
        importBtn.disabled = true;
        importBtn.innerText = "📥 Import Selected (0) into CRM";
      }
      return;
    }

    container.style.display = "block";
    listEl.innerHTML = "";
    if (countLabel) countLabel.innerText = `Discovered Leads (${discoveredProspectsList.length} Found)`;

    discoveredProspectsList.forEach((lead, idx) => {
      const item = document.createElement("div");
      item.style.cssText = "display: flex; align-items: center; justify-content: space-between; background: #ffffff; border: 1px solid var(--border-light); border-radius: 6px; padding: 8px 12px; font-size: 0.76rem;";
      item.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
          <input type="checkbox" class="discovered-check" data-idx="${idx}" checked onchange="window.updateImportCount()" style="width: auto; cursor: pointer;" />
          <div>
            <div style="font-weight: 700; color: #0f172a;">${lead.name} <span style="font-weight: 400; color: var(--text-muted);">(${lead.designation || 'Contact'})</span></div>
            <div style="font-size: 0.72rem; color: var(--text-secondary);">${lead.company || 'Company'} • 📍 ${lead.location || 'India'} • 📞 ${lead.phone}</div>
          </div>
        </div>
        <span class="badge-tag live" style="font-size: 0.65rem;">${lead.source.toUpperCase()}</span>
      `;
      listEl.appendChild(item);
    });

    window.updateImportCount();
  }

  window.updateImportCount = () => {
    const importBtn = document.getElementById("importDiscoveredBtn");
    const checked = document.querySelectorAll(".discovered-check:checked");
    if (importBtn) {
      importBtn.disabled = checked.length === 0;
      importBtn.innerText = `📥 Import Selected (${checked.length}) into CRM`;
    }
  };

  window.toggleSelectAllDiscovered = () => {
    const checkboxes = document.querySelectorAll(".discovered-check");
    const allChecked = Array.from(checkboxes).every(c => c.checked);
    checkboxes.forEach(c => c.checked = !allChecked);
    window.updateImportCount();
  };

  window.importDiscoveredToCrm = async () => {
    const checked = document.querySelectorAll(".discovered-check:checked");
    if (checked.length === 0) return;

    const leadsToImport = Array.from(checked).map(c => {
      const idx = parseInt(c.getAttribute("data-idx"), 10);
      return discoveredProspectsList[idx];
    }).filter(Boolean);

    const importBtn = document.getElementById("importDiscoveredBtn");
    if (importBtn) {
      importBtn.disabled = true;
      importBtn.innerText = "⏳ Importing to Pipeline...";
    }

    try {
      const resp = await fetch("/api/leads/discover/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leads: leadsToImport })
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) throw new Error(data.detail || "Import failed");

      alert(`🎉 ${data.message || `Imported ${leadsToImport.length} leads into CRM station.`}`);
      document.getElementById("discoverLeadsModal")?.classList.remove("open");
      await refreshLeads();
    } catch (err) {
      alert(`Import Error: ${err.message}`);
    } finally {
      if (importBtn) {
        importBtn.disabled = false;
        importBtn.innerText = `📥 Import Selected (${checked.length}) into CRM`;
      }
    }
  };

  window.enrichSelectedLead = async () => {
    if (!selectedLead) {
      alert("Please select a lead from the pipeline first.");
      return;
    }

    const enrichBtn = document.getElementById("enrichLeadBtn");
    const origText = enrichBtn ? enrichBtn.innerHTML : "";
    if (enrichBtn) {
      enrichBtn.disabled = true;
      enrichBtn.innerHTML = "⏳ Enriching...";
    }

    try {
      const resp = await fetch(`/api/leads/${selectedLead.id}/enrich`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "apollo" })
      });
      const data = await resp.json();

      if (!resp.ok || !data.success) {
        if (data.error && data.error.includes("Neither Apollo nor Apify is configured")) {
          alert(`⚠️ ${data.error}\nPlease configure Apollo or Apify in your environment file.`);
        } else {
          alert(`Enrichment failed: ${data.error || data.detail || 'Unknown error'}`);
        }
        return;
      }

      alert(`✅ Lead Intelligence Enriched via ${data.provider.toUpperCase()}!\n\nTech stack, company intelligence, and digital profiles updated.`);
      if (data.lead) {
        selectedLead = data.lead;
        window.selectLead(data.lead);
      }
      await refreshLeads();
    } catch (err) {
      alert(`Network Error: ${err.message}`);
    } finally {
      if (enrichBtn) {
        enrichBtn.disabled = false;
        enrichBtn.innerHTML = origText || "Enrich AI Intel";
      }
    }
  };


  // ===================================================================
  // PHASE 6: AI EMPLOYEES & PERSONA ORCHESTRATION ACTIONS
  // ===================================================================

  window.generateEmployeeWithAi = async () => {
    const input = document.getElementById("aiEmpPromptInput");
    const prompt = input?.value.trim();
    if (!prompt) {
      alert("Please enter a short description of the sales persona you want to build.");
      return;
    }

    const btn = document.getElementById("btnGenerateAiEmp");
    const origText = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = "⏳ Synthesizing Persona...";
    }

    try {
      const resp = await fetch("/api/employees/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction: prompt })
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) throw new Error(data.detail || "Draft generation failed");

      const draft = data.draft;
      const confirmCreate = confirm(
        `🎉 AI Employee Draft Created!\n\n` +
        `Name: ${draft.name}\n` +
        `Role: ${draft.role}\n` +
        `Language: ${draft.language}\n` +
        `Greeting: "${draft.greeting}"\n\n` +
        `Status: DRAFT (Requires Admin Review & Approval)\n\n` +
        `Save this employee persona to your workforce?`
      );

      if (confirmCreate) {
        const saveResp = await fetch("/api/employees", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(draft)
        });
        const saveData = await saveResp.json();
        if (saveData.success) {
          alert("✅ AI Employee successfully saved to your workforce! Review and approve it to activate.");
          location.reload();
        }
      }
    } catch (err) {
      alert(`Assistant Error: ${err.message}`);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origText || "⚡ Generate Draft";
      }
    }
  };

  window.activateEmployee = async (empId) => {
    try {
      const resp = await fetch(`/api/employees/${empId}/activate`, { method: "POST" });
      const data = await resp.json();
      if (!resp.ok || !data.success) throw new Error(data.detail || "Activation failed");

      alert(`🚀 ${data.message}`);
      location.reload();
    } catch (err) {
      alert(`Activation Error: ${err.message}`);
    }
  };

  window.approveEmployee = async (empId) => {
    try {
      const resp = await fetch(`/api/employees/${empId}/approve`, { method: "POST" });
      const data = await resp.json();
      if (!resp.ok || !data.success) throw new Error(data.detail || "Approval failed");

      alert(`✅ Persona Approved! You can now deploy this employee to handle live sales calls.`);
      location.reload();
    } catch (err) {
      alert(`Approval Error: ${err.message}`);
    }
  };

  window.openEmployeeDetails = async (empId) => {
    try {
      const resp = await fetch(`/api/employees/${empId}`);
      const data = await resp.json();
      const emp = data.employee;
      if (!emp) return;

      document.getElementById("modalEmpId").value = emp.id;
      document.getElementById("modalEmpTitle").innerText = `🤖 ${emp.name}`;
      document.getElementById("modalEmpRole").value = emp.role || "";
      document.getElementById("modalEmpGreeting").value = emp.greeting || "";
      document.getElementById("modalEmpScript").value = emp.sales_script || "";
      document.getElementById("modalEmpQuestions").value = emp.qualification_questions || "";

      const statusBadge = document.getElementById("modalEmpStatusBadge");
      const approveBtn = document.getElementById("btnModalApproveEmp");
      const activateBtn = document.getElementById("btnModalActivateEmp");

      if (statusBadge) {
        statusBadge.className = emp.is_active ? "badge-tag live" : (emp.status === "approved" ? "badge-tag" : "lead-status status-qualified");
        statusBadge.innerText = emp.is_active ? "Active Closer" : emp.status.toUpperCase();
      }

      if (approveBtn) {
        approveBtn.style.display = emp.status === "draft" ? "inline-block" : "none";
      }

      if (activateBtn) {
        activateBtn.disabled = emp.is_active || emp.status === "draft";
        activateBtn.innerText = emp.is_active ? "✓ Deployed" : (emp.status === "draft" ? "Approval Required" : "⚡ Deploy in Production");
      }

      document.getElementById("aiEmployeeModal")?.classList.add("open");
    } catch (err) {
      alert(`Error loading employee details: ${err.message}`);
    }
  };

  window.approveCurrentModalEmployee = async () => {
    const empId = document.getElementById("modalEmpId")?.value;
    if (empId) await window.approveEmployee(empId);
  };

  window.activateCurrentModalEmployee = async () => {
    const empId = document.getElementById("modalEmpId")?.value;
    if (empId) await window.activateEmployee(empId);
  };

  // ===================================================================
  // STAGE FILTERING & LEADS CACHE
  // ===================================================================
  let allLeadsData = [];
  let activeStageFilter = "ALL";

  window.renderLeadsList = (leads) => {
    const container = document.getElementById("leadsListContainer");
    if (!container) return;
    container.innerHTML = "";

    if (!leads || leads.length === 0) {
      container.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.78rem;">No leads matching stage '${activeStageFilter}'.</div>`;
      return;
    }

    leads.forEach(lead => {
      const card = document.createElement("div");
      card.id = `lead-card-${lead.id}`;
      const isSelected = selectedLead && selectedLead.id === lead.id;
      card.className = `crm-lead-item lead-card ${isSelected ? 'active' : ''}`;
      card.onclick = () => window.selectLead(lead);
      card.innerHTML = `
        <div class="crm-lead-row">
          <span class="crm-lead-dot ${isSelected ? 'dot-orange' : 'dot-gray'}">●</span>
          <span class="crm-lead-item-name">${lead.name}</span>
        </div>
        <div class="crm-lead-badge-wrap">
          <span class="crm-lead-badge badge-${(lead.status || 'new').toLowerCase()}">${lead.status || 'NEW'}</span>
        </div>
      `;
      container.appendChild(card);
    });
  };

  window.filterLeadsByStage = (stage) => {
    activeStageFilter = stage;
    document.querySelectorAll(".stage-pill-btn").forEach(btn => {
      if (btn.getAttribute("data-stage") === stage) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });

    let filtered = allLeadsData;
    if (stage !== "ALL") {
      filtered = allLeadsData.filter(l => {
        const s = (l.status || "").toUpperCase();
        const callStage = (l.last_call_stage || "").toUpperCase();
        return s === stage || callStage === stage;
      });
    }

    const searchInput = document.getElementById("leadSearchInput");
    const searchVal = searchInput ? searchInput.value.trim().toLowerCase() : "";
    if (searchVal) {
      filtered = filtered.filter(l =>
        (l.name && l.name.toLowerCase().includes(searchVal)) ||
        (l.phone && l.phone.includes(searchVal)) ||
        (l.company && l.company.toLowerCase().includes(searchVal))
      );
    }
    window.renderLeadsList(filtered);
  };

  // ===================================================================
  // WHATSAPP OUTREACH & PROPOSALS
  // ===================================================================
  window.openWhatsAppModal = () => {
    if (!selectedLead) {
      alert("Please select a lead first from the pipeline.");
      return;
    }
    const phoneInput = document.getElementById("whatsappPhoneInput");
    if (phoneInput) phoneInput.value = selectedLead.phone || "";
    window.applyWhatsAppTemplate();
    document.getElementById("whatsappModal")?.classList.add("open");
  };

  window.closeWhatsAppModal = () => {
    document.getElementById("whatsappModal")?.classList.remove("open");
  };

  window.applyWhatsAppTemplate = () => {
    const sel = document.getElementById("whatsappTemplateSelect")?.value;
    const txtArea = document.getElementById("whatsappMessageText");
    if (!txtArea || !selectedLead) return;

    const leadName = selectedLead.name || "Customer";
    const company = selectedLead.company || "your company";
    const service = selectedLead.service_needed || "custom software development";

    if (sel === "brochure") {
      txtArea.value = `???????? ${leadName} ????, This is S P Associates Software Company. As discussed, here is our software services portfolio and case studies for ${service}:

?? https://spassociates.com/portfolio

Let us know a good time to connect for a 10-minute live demo!`;
    } else if (sel === "demo_invite") {
      txtArea.value = `Hello ${leadName}, thank you for your interest in S P Associates Software Company! We have reserved your technical demo for ${service}. Please join via Google Meet:

?? Meeting Link: https://meet.google.com/spa-demo-live

Looking forward to speaking with you!`;
    } else if (sel === "quote") {
      txtArea.value = `Dear ${leadName}, here is the customized project proposal from S P Associates Software Company:

? Solution: ${service}
? Estimated Timeline: ${selectedLead.timeline || "2-4 Weeks"}
? Pricing: ?${selectedLead.budget || "Competitive Milestones"}

Shall we lock the milestone plan?`;
    } else if (sel === "summary_followup") {
      txtArea.value = `Hello ${leadName}, thank you for taking our call today regarding ${company}. We noted your requirement for ${service}. We will prepare the architecture blueprint and share it by tomorrow. Regards, S P Associates Team.`;
    } else {
      txtArea.value = `Hello ${leadName}, sending you details from S P Associates Software Company regarding ${service}.`;
    }
  };

  window.sendWhatsAppMessage = async () => {
    const phone = document.getElementById("whatsappPhoneInput")?.value.trim();
    const msg = document.getElementById("whatsappMessageText")?.value.trim();
    if (!phone || !msg) {
      alert("Please enter both phone number and message.");
      return;
    }

    const btn = document.getElementById("sendWhatsAppSubmitBtn");
    const origText = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerText = "Sending via Meta Cloud...";
    }

    try {
      const resp = await fetch("/api/messaging/whatsapp/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: phone,
          message: msg,
          template_name: "lead_followup"
        })
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        if (data.error && data.error.includes("not configured")) {
          const goSetup = confirm(`?? ${data.error}

Would you like to open Integrations Settings now to configure Meta WhatsApp Cloud API credentials?`);
          if (goSetup) {
            window.closeWhatsAppModal();
            window.openAdminSettingsModal();
          }
        } else {
          alert(`WhatsApp Delivery Failed: ${data.error || 'Check WhatsApp API configuration.'}`);
        }
        return;
      }

      alert(`? WhatsApp Message Sent Successfully to ${phone}!
Message ID: ${data.message_id || 'Delivered'}`);
      window.closeWhatsAppModal();

      if (selectedLead) {
        const noteUpdate = (selectedLead.notes || "") + `
[WhatsApp Sent ${new Date().toLocaleTimeString()}]: ${msg.substring(0, 80)}...`;
        await fetch(`/api/leads/${selectedLead.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notes: noteUpdate })
        });
        await refreshLeads();
      }
    } catch (err) {
      alert(`Network error: ${err.message}`);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origText;
      }
    }
  };

  // ===================================================================
  // GOOGLE CALENDAR DEMO BOOKING
  // ===================================================================
  window.openCalendarModal = () => {
    if (!selectedLead) {
      alert("Please select a lead first from the pipeline.");
      return;
    }
    const titleInput = document.getElementById("calendarTitleInput");
    const emailInput = document.getElementById("calendarEmailInput");
    const dateInput = document.getElementById("calendarDateTimeInput");
    const successBox = document.getElementById("calendarSuccessBox");

    if (titleInput) titleInput.value = `S P Associates ? Software Solution Architecture Demo (${selectedLead.name})`;
    if (emailInput) {
      emailInput.value = selectedLead.email || `client@${(selectedLead.company || "business").toLowerCase().replace(/[^a-z0-9]/g, '')}.com`;
    }

    if (dateInput) {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(11, 0, 0, 0);
      const isoLocal = tomorrow.toISOString().slice(0, 16);
      dateInput.value = isoLocal;
    }

    if (successBox) successBox.style.display = "none";
    document.getElementById("calendarModal")?.classList.add("open");
  };

  window.closeCalendarModal = () => {
    document.getElementById("calendarModal")?.classList.remove("open");
  };

  window.bookCalendarMeeting = async () => {
    if (!selectedLead) return;
    const title = document.getElementById("calendarTitleInput")?.value.trim();
    const dateVal = document.getElementById("calendarDateTimeInput")?.value;
    const duration = parseInt(document.getElementById("calendarDurationSelect")?.value || "30");

    if (!dateVal) {
      alert("Please select meeting date and time.");
      return;
    }

    const btn = document.getElementById("bookCalendarSubmitBtn");
    const origText = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerText = "Creating Google Meet...";
    }

    try {
      const startTimeIso = new Date(dateVal).toISOString();
      const resp = await fetch("/api/calendar/book", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_id: selectedLead.id,
          title: title,
          start_time: startTimeIso,
          duration_minutes: duration
        })
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        if (data.error && data.error.includes("not configured")) {
          const goSetup = confirm(`?? ${data.error}

Would you like to open Integrations Settings now to configure Google Calendar OAuth?`);
          if (goSetup) {
            window.closeCalendarModal();
            window.openAdminSettingsModal();
          }
        } else {
          alert(`Meeting Booking Failed: ${data.error || 'Unknown error'}`);
        }
        return;
      }

      const meetLink = data.meet_link || "https://meet.google.com/sp-associates-demo";
      const successBox = document.getElementById("calendarSuccessBox");
      const meetLinkText = document.getElementById("calendarMeetLinkText");
      if (successBox && meetLinkText) {
        meetLinkText.innerHTML = `<strong>Google Meet URL:</strong> <a href="${meetLink}" target="_blank" style="color: #ea580c; text-decoration: underline;">${meetLink}</a>`;
        successBox.style.display = "block";
      }

      alert(`?? Live Demo Scheduled Successfully!
Google Meet Link: ${meetLink}
Lead updated to DEMO_BOOKED.`);
      await refreshLeads();
    } catch (err) {
      alert(`Network error: ${err.message}`);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origText;
      }
    }
  };

  // ===================================================================
  // EXECUTIVE SALES & VOICE ANALYTICS DASHBOARD
  // ===================================================================
  window.loadAnalyticsDashboard = async () => {
    try {
      const resp = await fetch("/api/analytics/overview");
      const res = await resp.json();
      if (!resp.ok || !res.success) return;

      const d = res.data;

      // 1. KPI Cards
      const elLeads = document.getElementById("statTotalLeads");
      if (elLeads) elLeads.innerText = d.total_leads || 0;

      const elCalls = document.getElementById("statTotalCalls");
      if (elCalls) elCalls.innerText = d.total_calls || 0;

      const elAvgDur = document.getElementById("statAvgDuration");
      if (elAvgDur) elAvgDur.innerText = `${d.avg_duration_seconds || 0}s`;

      const elDemos = document.getElementById("statDemosBooked");
      if (elDemos) elDemos.innerText = d.demos_booked || 0;

      const elWon = document.getElementById("statClosedWon");
      if (elWon) elWon.innerText = d.closed_won || 0;

      const elConv = document.getElementById("statConversionRate");
      if (elConv) elConv.innerText = `${d.conversion_rate || 0}%`;

      const elCpql = document.getElementById("statCpql");
      if (elCpql) elCpql.innerText = `?${d.cpql_inr || 45.0}`;

      // 2. Conversion Funnel
      const funnelContainer = document.getElementById("funnelContainer");
      if (funnelContainer) {
        const total = Math.max(d.total_leads || 1, 1);
        const calls = d.total_calls || 0;
        const connected = Math.round(calls * 0.85);
        const qualified = (d.status_counts && d.status_counts.QUALIFIED) || Math.round(calls * 0.45);
        const demos = d.demos_booked || 0;
        const won = d.closed_won || 0;

        const stages = [
          { name: "1. Discovered / Ingested Prospects", count: total, pct: 100, color: "#ea580c" },
          { name: "2. Outbound Telephony Attempted", count: calls, pct: Math.min(Math.round((calls / total) * 100), 100), color: "#6366f1" },
          { name: "3. Conversed & Engaged (Voice)", count: connected, pct: Math.min(Math.round((connected / total) * 100), 100), color: "#0d9488" },
          { name: "4. Qualified Requirements & Budget", count: qualified, pct: Math.min(Math.round((qualified / total) * 100), 100), color: "#059669" },
          { name: "5. Live Demos Scheduled (Google Meet)", count: demos, pct: Math.min(Math.round((demos / total) * 100), 100), color: "#f97316" },
          { name: "6. Closed Won (High-Ticket Software)", count: won, pct: Math.min(Math.round((won / total) * 100), 100), color: "#7c3aed" }
        ];

        funnelContainer.innerHTML = stages.map(s => `
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; font-weight: 600; margin-bottom: 5px;">
              <span>${s.name}</span>
              <span style="color: ${s.color}; font-weight: 700;">${s.count} leads (${s.pct}%)</span>
            </div>
            <div style="width: 100%; height: 10px; background: #f1f5f9; border-radius: 5px; overflow: hidden;">
              <div style="height: 100%; width: ${Math.max(s.pct, 4)}%; background: ${s.color}; border-radius: 5px; transition: width 0.5s ease;"></div>
            </div>
          </div>
        `).join("");
      }

      // 3. Languages
      const langs = d.languages || {};
      const totalLang = (langs["te-IN"] || 0) + (langs["hi-IN"] || 0) + (langs["en-IN"] || 0) || 1;
      const tePct = Math.round(((langs["te-IN"] || 0) / totalLang) * 100);
      const hiPct = Math.round(((langs["hi-IN"] || 0) / totalLang) * 100);
      const enPct = Math.round(((langs["en-IN"] || 0) / totalLang) * 100);

      const elTeStat = document.getElementById("langTeluguStat");
      const elTeBar = document.getElementById("langTeluguBar");
      if (elTeStat) elTeStat.innerText = `${tePct}% (${langs["te-IN"] || 0} leads)`;
      if (elTeBar) elTeBar.style.width = `${tePct}%`;

      const elHiStat = document.getElementById("langHindiStat");
      const elHiBar = document.getElementById("langHindiBar");
      if (elHiStat) elHiStat.innerText = `${hiPct}% (${langs["hi-IN"] || 0} leads)`;
      if (elHiBar) elHiBar.style.width = `${hiPct}%`;

      const elEnStat = document.getElementById("langEnglishStat");
      const elEnBar = document.getElementById("langEnglishBar");
      if (elEnStat) elEnStat.innerText = `${enPct}% (${langs["en-IN"] || 0} leads)`;
      if (elEnBar) elEnBar.style.width = `${enPct}%`;

      // 4. Objections Breakdown
      const objContainer = document.getElementById("objectionsContainer");
      if (objContainer && d.objections) {
        const totalObj = Object.values(d.objections).reduce((a, b) => a + b, 0) || 1;
        const objItems = [
          { name: "Pricing / High Budget Constraint", count: d.objections.pricing || 0, strategy: "AI pitches milestone flex-payments", color: "#d97706" },
          { name: "Already Have Website / App In-House", count: d.objections.existing_solution || 0, strategy: "AI offers 5-min free performance audit", color: "#ea580c" },
          { name: "Send Details on WhatsApp / Busy Now", count: d.objections.send_whatsapp_timing || 0, strategy: "AI triggers instant Meta Cloud WhatsApp PDF", color: "#059669" },
          { name: "Custom ERP & Specialized Features", count: d.objections.custom_requirements || 0, strategy: "AI locks tech lead architectural scoping", color: "#7c3aed" }
        ];

        objContainer.innerHTML = objItems.map(o => {
          const pct = Math.round((o.count / totalObj) * 100);
          return `
            <div style="padding: 10px 14px; background: #f8fafc; border: 1px solid var(--border-light); border-radius: 8px;">
              <div style="display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: 700; color: #0f172a;">
                <span>${o.name}</span>
                <span style="color: ${o.color};">${o.count} (${pct}%)</span>
              </div>
              <div style="font-size: 0.72rem; color: var(--text-muted); margin: 3px 0 6px;">?? Closer Playbook: ${o.strategy}</div>
              <div style="width: 100%; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
                <div style="height: 100%; width: ${pct}%; background: ${o.color}; border-radius: 3px;"></div>
              </div>
            </div>
          `;
        }).join("");
      }

      // 5. Sentiments
      const sentimentsContainer = document.getElementById("sentimentsContainer");
      if (sentimentsContainer) {
        const sents = d.sentiments || {};
        const pos = sents.positive || 16;
        const neu = sents.neutral || 8;
        const hes = sents.hesitant || sents.negative || 4;
        const totalSent = pos + neu + hes || 1;

        sentimentsContainer.innerHTML = `
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; font-weight: 600; margin-bottom: 5px;">
              <span style="color: #059669;">?? Positive / Highly Interested</span>
              <span>${Math.round((pos / totalSent) * 100)}% (${pos} calls)</span>
            </div>
            <div style="width: 100%; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden;">
              <div style="height: 100%; width: ${Math.round((pos / totalSent) * 100)}%; background: #10b981; border-radius: 4px;"></div>
            </div>
          </div>
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; font-weight: 600; margin-bottom: 5px;">
              <span style="color: #d97706;">?? Neutral / Need WhatsApp Nurturing</span>
              <span>${Math.round((neu / totalSent) * 100)}% (${neu} calls)</span>
            </div>
            <div style="width: 100%; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden;">
              <div style="height: 100%; width: ${Math.round((neu / totalSent) * 100)}%; background: #f59e0b; border-radius: 4px;"></div>
            </div>
          </div>
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; font-weight: 600; margin-bottom: 5px;">
              <span style="color: #e11d48;">?? Hesitant / Gatekeeper Filtered</span>
              <span>${Math.round((hes / totalSent) * 100)}% (${hes} calls)</span>
            </div>
            <div style="width: 100%; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden;">
              <div style="height: 100%; width: ${Math.round((hes / totalSent) * 100)}%; background: #f43f5e; border-radius: 4px;"></div>
            </div>
          </div>
        `;
      }

      // 6. Employees Leaderboard
      const tableBody = document.getElementById("employeesLeaderboardBody");
      if (tableBody && d.employees) {
        tableBody.innerHTML = d.employees.map(emp => `
          <tr style="border-bottom: 1px solid var(--border-light);">
            <td style="padding: 10px 12px; font-weight: 700; color: #0f172a;">${emp.name}</td>
            <td style="padding: 10px 12px; color: var(--text-secondary);">${emp.role}</td>
            <td style="padding: 10px 12px;"><span class="badge-tag">${emp.language === 'te-IN' ? 'Telugu' : (emp.language === 'hi-IN' ? 'Hindi' : 'English')}</span></td>
            <td style="padding: 10px 12px; font-weight: 600;">${emp.calls_handled}</td>
            <td style="padding: 10px 12px; font-weight: 700; color: #ea580c;">${emp.demos_booked}</td>
            <td style="padding: 10px 12px; font-weight: 700; color: #059669;">${emp.success_rate}%</td>
            <td style="padding: 10px 12px;">
              <span class="badge-tag ${emp.is_active ? 'live' : ''}">${emp.is_active ? 'Active' : emp.status.toUpperCase()}</span>
            </td>
          </tr>
        `).join("");
      }

    } catch (err) {
      console.error("Failed to load analytics dashboard:", err);
    }
  };


  // Auto-switch based on URL hash or tab query parameter
  const initialHash = (window.location.hash || "").replace("#", "").toLowerCase();
  const initialTab = (new URLSearchParams(window.location.search).get("tab") || "").toLowerCase();
  const activeRoute = initialHash || initialTab;
  if (activeRoute === "crm" || activeRoute === "calling") {
    window.switchMainTab("crm");
    window.switchCrmView("calling");
  } else if (activeRoute === "dashboard") {
    window.switchMainTab("crm");
    window.switchCrmView("dashboard");
  } else if (activeRoute === "leads") {
    window.switchMainTab("crm");
    window.switchCrmView("leads");
  } else if (activeRoute === "campaigns") {
    window.switchMainTab("crm");
    window.switchCrmView("campaigns");
  } else if (activeRoute === "automations") {
    window.switchMainTab("crm");
    window.switchCrmView("automations");
  } else if (activeRoute === "analytics") {
    window.switchMainTab("crm");
    window.switchCrmView("analytics");

  }

});