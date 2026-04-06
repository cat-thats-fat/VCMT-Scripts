(() => {
  const LOG_PREFIX = "[IntermediateToggle]";
  const DEFAULT_TIMEOUT_MS = 20000;
  const POLL_INTERVAL_MS = 150;

  // Treatment options to toggle off
  const TREATMENTS_TO_DISABLE = [
    "Surrey student - Prebook Free",
    "PREGNANCY MASSAGE", 
    "ADVANCED MASSAGE"
  ];

  let isRunning = false;

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type !== "RUN_INTERMEDIATE_TOGGLE") return;

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

      await toggleOffTargetTreatments();

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

  async function toggleOffTargetTreatments() {
    console.log(`${LOG_PREFIX} Looking for treatment options to disable...`);
    
    // Wait for treatment list to load
    await waitFor(() => {
      const treatmentItems = document.querySelectorAll('.list-group-item');
      return treatmentItems.length > 0;
    }, 'Treatment list not found or empty', 10000);

    const treatmentItems = document.querySelectorAll('.list-group-item');
    console.log(`${LOG_PREFIX} Found ${treatmentItems.length} treatment items`);

    let toggledCount = 0;

    for (const treatmentItem of treatmentItems) {
      const treatmentText = treatmentItem.textContent?.trim() || '';
      
      // Check if this treatment matches any of our target treatments
      const shouldDisable = TREATMENTS_TO_DISABLE.some(targetTreatment => 
        treatmentText.includes(targetTreatment)
      );

      if (shouldDisable) {
        console.log(`${LOG_PREFIX} Found target treatment: "${treatmentText}"`);
        
        // Look for the toggle button within this treatment item
        const toggleBtn = treatmentItem.querySelector('.toggle-btn.on');
        
        if (toggleBtn) {
          console.log(`${LOG_PREFIX} Toggling off: "${treatmentText}"`);
          
          // Click the toggle to turn it off
          clickElement(toggleBtn);
          toggledCount++;
          
          // Wait a bit between toggles
          await wait(500);
        } else {
          // Check if it's already off
          const toggleBtnOff = treatmentItem.querySelector('.toggle-btn.off, .toggle-btn:not(.on)');
          if (toggleBtnOff) {
            console.log(`${LOG_PREFIX} Treatment already disabled: "${treatmentText}"`);
          } else {
            console.log(`${LOG_PREFIX} No toggle button found for: "${treatmentText}"`);
          }
        }
      }
    }

    console.log(`${LOG_PREFIX} Toggled off ${toggledCount} treatments`);
    
    if (toggledCount === 0) {
      console.log(`${LOG_PREFIX} No target treatments found or all were already disabled`);
    }
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