(() => {
  const LOG_PREFIX = "[TreamentToggle]";
  const DEFAULT_TIMEOUT_MS = 20000;
  const POLL_INTERVAL_MS = 150;

  // ─── Active mode ─────────────────────────────────────────────────────────────
  // Change this to the key of whichever mode you want to run.
  // Must match a key defined in MODES below.
  const ACTIVE_MODE = "intermediate";

  // ─── Mode definitions ─────────────────────────────────────────────────────────
  // Each mode has a list of treatments that must remain DISABLED.
  // An empty disabledTreatments array means all treatments are enabled (hybrid-style).
  //
  // To add a new mode, append a new entry:
  //   mymode: {
  //     label: "mymode",
  //     disabledTreatments: ["Treatment Name One", "Treatment Name Two"]
  //   }
  const MODES = {
    intermediate: {
      label: "intermediate",
      disabledTreatments: [
        "Surrey student - Prebook Free",
        "ADVANCED MASSAGE",
        "PREGNANCY MASSAGE"
      ]
    },
    advanced: {
      label: "advanced",
      disabledTreatments: [
        "Surrey student - Prebook Free",
        "INTERMEDIATE MASSAGE",
        "Intermediate Massage (ORIENTATION)"
      ]
    },
    hybrid: {
      label: "hybrid",
      disabledTreatments: [] // All treatments enabled
    },
    surrey: {
      label: "surrey",
      disabledTreatments: [] // All treatments enabled
    }
  };

  let isRunning = false;

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type !== "RUN_TREAMENT_TOGGLE") return;

    run().catch((error) => {
      console.error(`${LOG_PREFIX} Automation failed:`, error);
      alert(`${LOG_PREFIX} Automation failed: ${error.message}`);
    }).finally(() => {
      isRunning = false;
      console.log(`${LOG_PREFIX} Extension state reset.`);
    });
  });

  async function run() {
    if (isRunning) {
      console.warn(`${LOG_PREFIX} Already running on this tab; ignoring duplicate trigger.`);
      const forceReset = confirm(`${LOG_PREFIX} Extension is already running. Click OK to force reset and continue, or Cancel to wait.`);
      if (forceReset) {
        console.log(`${LOG_PREFIX} Force resetting extension state.`);
        isRunning = false;
      } else {
        return;
      }
    }

    isRunning = true;
    console.log(`${LOG_PREFIX} Starting automation...`);

    // Safety timeout - reset flag after 2 minutes max
    const safetyTimeout = setTimeout(() => {
      if (isRunning) {
        console.warn(`${LOG_PREFIX} Safety timeout reached - resetting extension state.`);
        isRunning = false;
      }
    }, 120000); // 2 minutes

    try {
      const parsed = parseStaffUrl(window.location.href);
      if (!parsed) {
        throw new Error("Expected a Jane URL like #staff/<id>/treatments or #staff/<id>");
      }

      const { baseUrl, staffId, isTreatments } = parsed;
      const treatmentsUrl = `${baseUrl}#staff/${staffId}/treatments`;

      console.log(`${LOG_PREFIX} Starting for staff ${staffId}. Current URL: ${window.location.href}`);

      if (!isTreatments) {
        console.log(`${LOG_PREFIX} Navigating to treatments page: ${treatmentsUrl}`);
        window.location.assign(treatmentsUrl);
        await waitForLocation(treatmentsUrl);
      } else {
        console.log(`${LOG_PREFIX} Already on treatments page for staff ${staffId}.`);
      }

      // Wait for page to fully load
      await wait(1000);

      await applyModeTreatmentToggles();

      // Wait for Jane to process the changes
      await wait(2000);

      const nextId = staffId + 1;
      const nextUrl = `${baseUrl}#staff/${nextId}/treatments`;
      console.log(`${LOG_PREFIX} Moving to next staff: ${nextId}. URL: ${nextUrl}`);

      // Navigate directly to the next staff treatments page
      window.location.assign(nextUrl);
      console.log(`${LOG_PREFIX} Successfully completed staff ${staffId} and moved to ${nextId}`);

      // Wait a bit before resetting flag to prevent race condition during navigation
      await wait(1000);

      // Reset running state after successful completion
      isRunning = false;
      clearTimeout(safetyTimeout);
      console.log(`${LOG_PREFIX} Extension state reset after successful completion.`);
    } catch (error) {
      // Ensure we reset the flag even on error
      isRunning = false;
      clearTimeout(safetyTimeout);
      console.error(`${LOG_PREFIX} Extension state reset after error.`);
      throw error; // Re-throw the error for the catch handler
    }
  }

  function parseStaffUrl(urlString) {
    const url = new URL(urlString);
    const match = url.hash.match(/^#staff\/(\d+)(\/treatments)?/);
    if (!match) return null;

    return {
      baseUrl: `${url.origin}${url.pathname}`,
      staffId: Number(match[1]),
      isTreatments: Boolean(match[2])
    };
  }

  function getModeConfig() {
    const mode = MODES[ACTIVE_MODE];
    if (!mode) {
      throw new Error(
        `Unknown mode "${ACTIVE_MODE}". Available modes: ${Object.keys(MODES).join(", ")}`
      );
    }
    return {
      modeLabel: mode.label,
      disabledTreatments: mode.disabledTreatments
    };
  }

  async function applyModeTreatmentToggles() {
    const { modeLabel, disabledTreatments } = getModeConfig();
    console.log(`${LOG_PREFIX} Applying ${modeLabel} mode treatment toggles...`);
    console.log(`${LOG_PREFIX} Treatments to keep disabled:`, disabledTreatments);

    // Wait for treatment list to load
    await waitFor(() => {
      const treatmentItems = document.querySelectorAll('.list-group-item');
      return treatmentItems.length > 0;
    }, 'Treatment list not found or empty', 10000);

    const treatmentItems = document.querySelectorAll('.list-group-item');
    console.log(`${LOG_PREFIX} Found ${treatmentItems.length} treatment items`);

    let toggledOnCount = 0;
    let toggledOffCount = 0;
    let unchangedCount = 0;

    for (const treatmentItem of treatmentItems) {
      const treatmentText = treatmentItem.textContent?.trim() || '';
      const normalizedTreatmentText = normalizeText(treatmentText);

      const shouldDisable = disabledTreatments.some(targetTreatment =>
        normalizedTreatmentText.includes(normalizeText(targetTreatment))
      );
      const shouldEnable = !shouldDisable;

      // Look for the toggle button within this treatment item
      const toggleBtnOn = treatmentItem.querySelector('.toggle-btn.on');
      const toggleBtnOff = treatmentItem.querySelector('.toggle-btn.off, .toggle-btn:not(.on)');

      if (shouldDisable && toggleBtnOn) {
        console.log(`${LOG_PREFIX} Toggling off: "${treatmentText}"`);
        clickElement(toggleBtnOn);
        toggledOffCount++;
        await wait(500);
      } else if (shouldEnable && toggleBtnOff) {
        console.log(`${LOG_PREFIX} Toggling on: "${treatmentText}"`);
        clickElement(toggleBtnOff);
        toggledOnCount++;
        await wait(500);
      } else {
        unchangedCount++;
      }
    }

    console.log(
      `${LOG_PREFIX} Toggle summary — on: ${toggledOnCount}, off: ${toggledOffCount}, unchanged: ${unchangedCount}`
    );
  }

  async function waitForLocation(expectedUrl, timeoutMs = DEFAULT_TIMEOUT_MS) {
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
      if (window.location.href === expectedUrl) return;
      await wait(100);
    }

    throw new Error(`Timed out waiting for navigation to ${expectedUrl}`);
  }

  function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function clickElement(element) {
    const clickable = element.querySelector("a, button") || element;

    clickable.dispatchEvent(new MouseEvent("mouseover", { bubbles: true, cancelable: true }));
    clickable.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true }));
    clickable.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true }));
    clickable.click();
  }

  function normalizeText(text) {
    return (text || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  async function waitFor(getter, errorMessage, timeoutMs = DEFAULT_TIMEOUT_MS) {
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
      const result = getter();
      if (result) return result;
      await wait(150);
    }

    throw new Error(errorMessage);
  }
})();
