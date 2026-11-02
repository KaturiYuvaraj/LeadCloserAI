/**
 * Main Frontend Application Logic for Telugu AI Caller & CRM.
 * Manages Live Voice Calling, Excel Leads Ingestion, Autonomous Campaigns,
 * and Persistent Call Summaries & Transcripts.
 */

document.addEventListener("DOMContentLoaded", () => {
  const caller = new VoiceCallClient();
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

  caller.onCallEnd = (summaryData) => {
    if (doneSpeakingBtn) doneSpeakingBtn.style.display = "none";
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
      const leadId = selectedLead ? selectedLead.id : null;
      transcriptBox.innerHTML = "";
      caller.startCall(leadId, selectedCallLanguage);
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
    });
  }

  if (sendTestBtn && testInput) {
    sendTestBtn.addEventListener("click", () => {
      const text = testInput.value.trim();
      if (!text) return;

      if (!caller.isCallActive) {
        const leadId = selectedLead ? selectedLead.id : null;
        caller.startCall(leadId).then(() => {
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
    document.querySelectorAll(".lead-card").forEach(el => el.classList.remove("active"));
    const card = document.getElementById(`lead-card-${lead.id}`);
    if (card) card.classList.add("active");

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
  // EXCEL / CSV UPLOAD CONTROLLER
  // ===================================================================
  const uploadExcelModal = document.getElementById("uploadExcelModal");
  const openUploadExcelBtn = document.getElementById("openUploadExcelBtn");
  const sidebarUploadBtn = document.getElementById("sidebarUploadBtn");
  const closeUploadModal = document.getElementById("closeUploadModal");
  const excelFileInput = document.getElementById("excelFileInput");
  const excelDropzone = document.getElementById("excelDropzone");
  const dropzoneText = document.getElementById("dropzoneText");
  const submitExcelUploadBtn = document.getElementById("submitExcelUploadBtn");
  const uploadStatusMsg = document.getElementById("uploadStatusMsg");

  function openUpload() {
    uploadStatusMsg.style.display = "none";
    excelFileInput.value = "";
    dropzoneText.innerText = "Click or Drag & Drop Excel (.xlsx) or CSV file";
    uploadExcelModal.classList.add("open");
  }

  if (openUploadExcelBtn) openUploadExcelBtn.addEventListener("click", openUpload);
  if (sidebarUploadBtn) sidebarUploadBtn.addEventListener("click", openUpload);
  if (closeUploadModal) {
    closeUploadModal.addEventListener("click", () => uploadExcelModal.classList.remove("open"));
  }

  if (excelFileInput) {
    excelFileInput.addEventListener("change", () => {
      if (excelFileInput.files.length > 0) {
        dropzoneText.innerText = `Selected: ${excelFileInput.files[0].name} (${Math.round(excelFileInput.files[0].size / 1024)} KB)`;
      }
    });
  }

  if (excelDropzone) {
    excelDropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      excelDropzone.classList.add("dragover");
    });
    excelDropzone.addEventListener("dragleave", () => {
      excelDropzone.classList.remove("dragover");
    });
    excelDropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      excelDropzone.classList.remove("dragover");
      if (e.dataTransfer.files.length > 0) {
        excelFileInput.files = e.dataTransfer.files;
        dropzoneText.innerText = `Selected: ${e.dataTransfer.files[0].name} (${Math.round(e.dataTransfer.files[0].size / 1024)} KB)`;
      }
    });
  }

  if (submitExcelUploadBtn) {
    submitExcelUploadBtn.addEventListener("click", async () => {
      if (!excelFileInput.files || excelFileInput.files.length === 0) {
        alert("Please select an Excel (.xlsx) or CSV file first.");
        return;
      }

      submitExcelUploadBtn.disabled = true;
      submitExcelUploadBtn.innerText = "Parsing & Ingesting...";
      uploadStatusMsg.style.display = "none";

      const formData = new FormData();
      formData.append("file", excelFileInput.files[0]);

      try {
        const resp = await fetch("/api/leads/upload-excel", {
          method: "POST",
          body: formData
        });
        const data = await resp.json();

        if (resp.ok && data.success) {
          uploadStatusMsg.style.display = "block";
          uploadStatusMsg.style.background = "rgba(16, 185, 129, 0.2)";
          uploadStatusMsg.style.color = "#34d399";
          uploadStatusMsg.style.border = "1px solid rgba(16, 185, 129, 0.4)";
          uploadStatusMsg.innerHTML = `
            <strong>✅ Import Successful!</strong><br/>
            Found: ${data.total_parsed} leads | Added: ${data.inserted} | Updated: ${data.updated}
          `;

          setTimeout(() => {
            uploadExcelModal.classList.remove("open");
            refreshLeads();
          }, 1800);
        } else {
          uploadStatusMsg.style.display = "block";
          uploadStatusMsg.style.background = "rgba(239, 68, 68, 0.2)";
          uploadStatusMsg.style.color = "#f87171";
          uploadStatusMsg.style.border = "1px solid rgba(239, 68, 68, 0.4)";
          uploadStatusMsg.innerText = data.detail || (data.errors ? data.errors.join(", ") : "Failed to import leads.");
        }
      } catch (err) {
        uploadStatusMsg.style.display = "block";
        uploadStatusMsg.style.background = "rgba(239, 68, 68, 0.2)";
        uploadStatusMsg.style.color = "#f87171";
        uploadStatusMsg.innerText = "Upload failed: " + err.message;
      } finally {
        submitExcelUploadBtn.disabled = false;
        submitExcelUploadBtn.innerText = "Upload & Ingest";
      }
    });
  }

  // ===================================================================
  // AUTONOMOUS AUTO-CALLING CAMPAIGN CONTROLLER
  // ===================================================================
  const campaignModal = document.getElementById("campaignModal");
  const openCampaignModalBtn = document.getElementById("openCampaignModalBtn");
  const closeCampaignModal = document.getElementById("closeCampaignModal");
  const startCampaignSubmitBtn = document.getElementById("startCampaignSubmitBtn");

  const campaignBanner = document.getElementById("campaignBanner");
  const campaignModeBadge = document.getElementById("campaignModeBadge");
  const campaignProgressBar = document.getElementById("campaignProgressBar");
  const campaignCurrentLead = document.getElementById("campaignCurrentLead");
  const campaignProgressText = document.getElementById("campaignProgressText");
  const campaignDemosCount = document.getElementById("campaignDemosCount");
  const campaignWonCount = document.getElementById("campaignWonCount");
  const campaignFollowCount = document.getElementById("campaignFollowCount");
  const pauseCampaignBtn = document.getElementById("pauseCampaignBtn");
  const stopCampaignBtn = document.getElementById("stopCampaignBtn");

  if (openCampaignModalBtn) {
    openCampaignModalBtn.addEventListener("click", () => {
      campaignModal.classList.add("open");
    });
  }

  if (closeCampaignModal) {
    closeCampaignModal.addEventListener("click", () => {
      campaignModal.classList.remove("open");
    });
  }

  if (startCampaignSubmitBtn) {
    startCampaignSubmitBtn.addEventListener("click", async () => {
      const mode = document.getElementById("campaignModeSelect").value;
      const target = document.getElementById("campaignTargetSelect").value;
      const delay = parseInt(document.getElementById("campaignDelaySelect").value, 10);

      startCampaignSubmitBtn.disabled = true;
      startCampaignSubmitBtn.innerText = "Starting...";

      try {
        const resp = await fetch("/api/campaign/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode: mode,
            delay_seconds: delay
          })
        });

        const data = await resp.json();
        if (resp.ok && data.success) {
          campaignModal.classList.remove("open");
          campaignBanner.classList.add("active");
          campaignModeBadge.innerText = mode.toUpperCase();
          startCampaignPolling();
        } else {
          alert(data.detail || "Could not start campaign.");
        }
      } catch (err) {
        alert("Campaign start error: " + err.message);
      } finally {
        startCampaignSubmitBtn.disabled = false;
        startCampaignSubmitBtn.innerText = "🚀 Start Auto-Dialing";
      }
    });
  }

  function startCampaignPolling() {
    if (campaignPollInterval) clearInterval(campaignPollInterval);

    campaignPollInterval = setInterval(async () => {
      try {
        const resp = await fetch("/api/campaign/status");
        const status = await resp.json();

        campaignProgressBar.style.width = `${status.progress_percent || 0}%`;
        campaignProgressText.innerText = `${status.completed_leads || 0} / ${status.total_leads || 0}`;

        if (status.current_lead) {
          campaignCurrentLead.innerHTML = `📞 Calling: <strong>${status.current_lead.name}</strong> (${status.current_lead.phone}) • ${status.current_lead.service_needed || 'Software'}`;
        } else if (status.is_running) {
          campaignCurrentLead.innerText = "Dialing next lead...";
        }

        const res = status.results || {};
        campaignDemosCount.innerText = res.demo_scheduled || 0;
        campaignWonCount.innerText = res.closed_won || 0;
        campaignFollowCount.innerText = res.follow_up || 0;

        if (pauseCampaignBtn) {
          pauseCampaignBtn.innerText = status.is_paused ? "▶️ Resume" : "⏸️ Pause";
        }

        if (!status.is_running && status.total_leads > 0 && status.completed_leads >= status.total_leads) {
          clearInterval(campaignPollInterval);
          campaignPollInterval = null;
          campaignCurrentLead.innerHTML = `🎉 <strong>Campaign Complete!</strong> ${status.completed_leads} leads called. Call summaries saved.`;
          refreshLeads();
          refreshCallHistory();
          setTimeout(() => {
            campaignBanner.classList.remove("active");
          }, 8000);
        }
      } catch (e) {
        console.error("Campaign poll error:", e);
      }
    }, 1500);
  }

  if (pauseCampaignBtn) {
    pauseCampaignBtn.addEventListener("click", async () => {
      const isPaused = pauseCampaignBtn.innerText.includes("Resume");
      const endpoint = isPaused ? "/api/campaign/resume" : "/api/campaign/pause";
      await fetch(endpoint, { method: "POST" });
    });
  }

  if (stopCampaignBtn) {
    stopCampaignBtn.addEventListener("click", async () => {
      if (confirm("Stop the running auto-calling campaign?")) {
        await fetch("/api/campaign/stop", { method: "POST" });
        if (campaignPollInterval) clearInterval(campaignPollInterval);
        campaignBanner.classList.remove("active");
        refreshLeads();
      }
    });
  }

  // ===================================================================
  // MANUAL LEAD & PHONE DIAL MODALS
  // ===================================================================
  if (phoneCallBtn) {
    phoneCallBtn.addEventListener("click", () => {
      const phone = selectedLead ? selectedLead.phone : "";
      document.getElementById("phoneCallInput").value = phone;
      document.getElementById("phoneCallModal").classList.add("open");
    });
  }

  const closePhoneModal = document.getElementById("closePhoneModal");
  if (closePhoneModal) {
    closePhoneModal.addEventListener("click", () => {
      document.getElementById("phoneCallModal").classList.remove("open");
    });
  }

  const submitPhoneCallBtn = document.getElementById("submitPhoneCallBtn");
  if (submitPhoneCallBtn) {
    submitPhoneCallBtn.addEventListener("click", async () => {
      const phone = document.getElementById("phoneCallInput").value.trim();
      if (!phone) {
        alert("Please enter a phone number");
        return;
      }

      try {
        const resp = await fetch("/api/call/outbound", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            phone: phone,
            lead_id: selectedLead ? selectedLead.id : null
          })
        });
        const data = await resp.json();
        if (data.success) {
          alert("Outbound phone call initiated! Check your phone.");
          document.getElementById("phoneCallModal").classList.remove("open");
        } else {
          alert(data.error || "Failed to trigger phone call.");
        }
      } catch (e) {
        alert("Error initiating phone call: " + e.message);
      }
    });
  }

  // Add Lead Modal
  const addLeadModal = document.getElementById("addLeadModal");
  const openAddLeadBtn = document.getElementById("openAddLeadBtn");
  const closeAddLeadModal = document.getElementById("closeAddLeadModal");

  if (openAddLeadBtn && addLeadModal) {
    openAddLeadBtn.addEventListener("click", () => addLeadModal.classList.add("open"));
  }
  if (closeAddLeadModal && addLeadModal) {
    closeAddLeadModal.addEventListener("click", () => addLeadModal.classList.remove("open"));
  }

  const leadForm = document.getElementById("leadForm");
  if (leadForm) {
    leadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const langEl = document.getElementById("leadLangInput");
      const payload = {
        name: document.getElementById("leadNameInput").value,
        phone: document.getElementById("leadPhoneInput").value,
        company: document.getElementById("leadCompanyInput").value,
        service_needed: document.getElementById("leadServiceInput").value,
        budget: document.getElementById("leadBudgetInput").value,
        timeline: document.getElementById("leadTimelineInput").value,
        notes: document.getElementById("leadNotesInput").value,
        preferred_language: langEl ? langEl.value : "te-IN",
        status: "NEW"
      };

      const resp = await fetch("/api/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (resp.ok) {
        addLeadModal.classList.remove("open");
        leadForm.reset();
        refreshLeads();
      }
    });
  }

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

        card.innerHTML = `
          <div class="lead-header">
            <span class="lead-name">${lead.name}</span>
            <span class="lead-status status-${(lead.status || 'new').toLowerCase()}">${lead.status || 'NEW'}</span>
          </div>
          <div class="lead-company">${lead.company || 'Business'} • ${lead.service_needed || 'Software'}</div>
          <div class="lead-details-row">
            <span>💰 ${lead.budget || 'Flexible'}</span>
            <span>⏱️ ${lead.timeline || 'Immediate'}</span>
          </div>
          ${summaryHtml}
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
        item.className = "tip-item";
        item.style.cursor = "pointer";
        item.onclick = () => window.openCallDetails(call.id);
        item.title = "Click to view full transcript & call summary";
        item.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="tip-title">${call.lead_name || 'Web Call'}</span>
            <span style="font-size:0.7rem; color: var(--primary); font-weight: 600;">${call.duration_seconds}s ↗</span>
          </div>
          <div style="font-size:0.71rem; color: var(--text-muted); margin: 2px 0;">Stage: <strong style="color: #059669;">${(call.deal_stage || '').toUpperCase()}</strong></div>
          <div style="font-size:0.79rem; line-height: 1.35; color: var(--text-secondary);">${call.summary || 'Call recorded successfully.'}</div>
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

  window.switchMainTab = (tabName, targetSectionId = null) => {
    currentMainTab = tabName;
    const viewLanding = document.getElementById("viewLanding");
    const viewCrm = document.getElementById("viewCrm");
    const navLaunchCrmText = document.getElementById("navLaunchCrmText");

    // Remove active from all nav tab buttons
    document.querySelectorAll(".nav-tab-btn").forEach(btn => btn.classList.remove("active"));

    if (tabName === "crm") {
      if (viewLanding) viewLanding.style.display = "none";
      if (viewCrm) viewCrm.style.display = "block";
      const btnCrm = document.getElementById("tabBtnCrm");
      if (btnCrm) btnCrm.classList.add("active");
      if (navLaunchCrmText) navLaunchCrmText.innerText = "← View Overview";
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      if (viewLanding) viewLanding.style.display = "block";
      if (viewCrm) viewCrm.style.display = "none";
      if (navLaunchCrmText) navLaunchCrmText.innerText = "Launch CRM Station";

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
      } else if (targetSectionId === "integrationsSection") {
        const btn = document.getElementById("tabBtnIntegrations");
        if (btn) btn.classList.add("active");
        window.scrollToSection("integrationsSection");
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

});