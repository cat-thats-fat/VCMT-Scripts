(() => {
  const LOG_PREFIX = "[JaneBookingOn]";
  const DEFAULT_TIMEOUT_MS = 20000;
  const POLL_INTERVAL_MS = 150;

  let isRunning = false;

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type !== "RUN_JANE_BOOKING_ON") return;

    run().catch((error) => {
      console.error(`${LOG_PREFIX} Automation failed:`, error);
      alert(`${LOG_PREFIX} Automation failed: ${error.message}`);
    }).finally(() => {
      // Ensure isRunning is always reset, even if there's an error
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
        throw new Error("Expected a Jane URL like #staff/<id> or #staff/<id>/edit.");
      }

      const { baseUrl, staffId, isEdit } = parsed;
      const editUrl = `${baseUrl}#staff/${staffId}/edit`;

      console.log(`${LOG_PREFIX} Starting for staff ${staffId}. Current URL: ${window.location.href}`);

      if (!isEdit) {
        console.log(`${LOG_PREFIX} Navigating to edit page: ${editUrl}`);
        window.location.assign(editUrl);
        await waitForLocation(editUrl);
      } else {
        console.log(`${LOG_PREFIX} Already on edit page for staff ${staffId}.`);
      }

      await openOnlineBookingTab();
      await ensureOnlineBookingEnabled();
      await ensureRollingAvailabilityNoLimit();
      await clickSaveAndWaitForCompletion(staffId);

      // Give Jane some extra time to settle after save
      await wait(2000);

      const nextId = staffId + 1;
      const nextUrl = `${baseUrl}#staff/${nextId}/edit`;
      console.log(`${LOG_PREFIX} Moving to next staff: ${nextId}. URL: ${nextUrl}`);
      
      // Navigate directly to the next staff edit page
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
    const match = url.hash.match(/^#staff\/(\d+)(\/edit)?$/);
    if (!match) return null;

    return {
      baseUrl: `${url.origin}${url.pathname}`,
      staffId: Number(match[1]),
      isEdit: Boolean(match[2])
    };
  }

  async function openOnlineBookingTab() {
    console.log(`${LOG_PREFIX} Opening Online Booking tab.`);

    const menuItem = await waitFor(() => {
      const candidates = Array.from(
        document.querySelectorAll('li[role="menuitem"], [role="menuitem"]')
      );

      return candidates.find((el) =>
        normalizeText(el.textContent).includes("online booking")
      );
    }, "Online Booking menu item not found");

    clickElement(menuItem);

    await waitFor(() => {
      return document.querySelector('[name="allow_online_booking"]');
    }, 'Field [name="allow_online_booking"] did not appear after clicking Online Booking');

    console.log(`${LOG_PREFIX} Online Booking tab is active.`);
  }

  async function ensureOnlineBookingEnabled() {
    console.log(`${LOG_PREFIX} Looking for online booking enable field...`);
    
    const field = await waitFor(() => document.querySelector('[name="allow_online_booking"]'),
      'Field [name="allow_online_booking"] not found.');

    console.log(`${LOG_PREFIX} Found field:`, field.tagName, field.type, field.name, 'Current value:', field.value, 'Checked:', field.checked);

    const isCheckbox = field instanceof HTMLInputElement && field.type === "checkbox";
    const isRadio = field instanceof HTMLInputElement && field.type === "radio";

    if (isCheckbox) {
      // Check both the checked property and aria-checked attribute
      const isChecked = field.checked || field.getAttribute('aria-checked') === 'true';
      
      if (isChecked) {
        console.log(`${LOG_PREFIX} Enable Online Booking checkbox is already checked.`);
        return;
      }

      console.log(`${LOG_PREFIX} Checking the Enable Online Booking checkbox.`);
      
      // Try multiple methods to activate this checkbox
      
      // Method 1: Look for clickable elements around the checkbox
      const clickTargets = [
        // Look for a label
        document.querySelector(`label[for="${field.id}"]`),
        field.closest('label'),
        // Look for nearby clickable elements (buttons, divs with click handlers)
        field.parentElement?.querySelector('button'),
        field.parentElement?.querySelector('[role="button"]'),
        field.parentElement?.querySelector('.clickable, .btn'),
        // Look for siblings that might be the visual representation
        field.nextElementSibling,
        field.previousElementSibling,
        // The parent element itself
        field.parentElement
      ].filter(el => el && el !== field);

      console.log(`${LOG_PREFIX} Found ${clickTargets.length} potential click targets around checkbox.`);
      
      // Try clicking each potential target
      for (let i = 0; i < clickTargets.length; i++) {
        const target = clickTargets[i];
        console.log(`${LOG_PREFIX} Trying click target ${i + 1}: ${target.tagName} ${target.className}`);
        
        clickElement(target);
        await wait(200);
        
        // Check if it worked
        if (field.checked || field.getAttribute('aria-checked') === 'true') {
          console.log(`${LOG_PREFIX} Success! Checkbox activated by clicking ${target.tagName}.`);
          break;
        }
      }
      
      // Method 2: If clicking didn't work, try programmatic activation
      if (!field.checked && field.getAttribute('aria-checked') !== 'true') {
        console.log(`${LOG_PREFIX} Click methods failed, trying programmatic activation...`);
        
        // Force the checkbox state
        field.checked = true;
        field.setAttribute('aria-checked', 'true');
        
        // Try different event combinations
        const events = ['mousedown', 'mouseup', 'click', 'input', 'change'];
        for (const eventType of events) {
          field.dispatchEvent(new MouseEvent(eventType, { bubbles: true, cancelable: true }));
          await wait(50);
        }
        
        // Try keyboard events
        field.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
        field.dispatchEvent(new KeyboardEvent('keyup', { key: ' ', bubbles: true }));
      }
      
      await wait(500);
      
      const finalChecked = field.checked || field.getAttribute('aria-checked') === 'true';
      console.log(`${LOG_PREFIX} Checkbox after enabling - checked:`, field.checked, 'aria-checked:', field.getAttribute('aria-checked'));
      return;
    }

    if (isRadio) {
      // For radio buttons, we need to find the "yes/true/on" option
      const radioGroup = Array.from(document.querySelectorAll(`[name="${field.name}"]`));
      console.log(`${LOG_PREFIX} Found ${radioGroup.length} radio buttons for online booking`);
      
      const enabledRadio = radioGroup.find(radio => {
        const val = String(radio.value).toLowerCase();
        return val === "1" || val === "true" || val === "yes" || val === "on";
      });
      
      if (enabledRadio) {
        if (enabledRadio.checked) {
          console.log(`${LOG_PREFIX} Enable Online Booking radio is already selected.`);
          return;
        }
        
        console.log(`${LOG_PREFIX} Selecting Enable Online Booking radio button (value: ${enabledRadio.value}).`);
        enabledRadio.focus();
        enabledRadio.checked = true;
        enabledRadio.dispatchEvent(new Event("input", { bubbles: true }));
        enabledRadio.dispatchEvent(new Event("change", { bubbles: true }));
        enabledRadio.dispatchEvent(new Event("click", { bubbles: true }));
        enabledRadio.blur();
        await wait(500);
        return;
      }
    }

    // Handle select dropdown or text input
    const value = String(field.value ?? "").toLowerCase();
    const truthyValues = new Set(["1", "true", "yes", "on"]);

    if (truthyValues.has(value)) {
      console.log(`${LOG_PREFIX} Enable Online Booking is already ON (value: ${field.value}).`);
      return;
    }

    console.log(`${LOG_PREFIX} Setting Online Booking field to enabled (setting value to "1").`);
    field.focus();
    field.value = "1";
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    field.blur();
    await wait(500);
    
    console.log(`${LOG_PREFIX} Field value after setting:`, field.value);
  }

  async function ensureRollingAvailabilityNoLimit() {
    console.log(`${LOG_PREFIX} Looking for rolling availability field...`);
    
    // Try to find the field, but don't throw error if not found
    const select = await waitFor(() => document.querySelector('[name="max_bookable_offset"]'),
      'Field [name="max_bookable_offset"] not found - may already be disabled.', 5000).catch(() => {
        console.log(`${LOG_PREFIX} Rolling availability field not found - likely already set correctly or not applicable.`);
        return null;
      });

    if (!select) {
      console.log(`${LOG_PREFIX} Skipping rolling availability - field not present (may already be configured).`);
      return;
    }

    if (!(select instanceof HTMLSelectElement)) {
      console.log(`${LOG_PREFIX} Rolling availability field is not a select - skipping.`);
      return;
    }

    const alreadyNoLimit = select.value === "";
    if (alreadyNoLimit) {
      console.log(`${LOG_PREFIX} Rolling Availability already set to No Limit.`);
      return;
    }

    const hasNoLimitOption = Array.from(select.options).some((option) => option.value === "");
    if (!hasNoLimitOption) {
      console.log(`${LOG_PREFIX} No Limit option not found - may not be available for this staff member.`);
      return;
    }

    console.log(`${LOG_PREFIX} Setting Rolling Availability to No Limit.`);
    select.value = "";
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async function clickSaveAndWaitForCompletion(staffId) {
    const saveButton = await waitFor(() => {
      const buttons = Array.from(document.querySelectorAll("button"));
      return buttons.find((btn) => normalizeText(btn.textContent) === "save");
    }, "Save button not found");

    console.log(`${LOG_PREFIX} Clicking Save.`);
    clickElement(saveButton);
    
    // Be very patient with Jane's slow/fragile UI
    await wait(1000);
    console.log(`${LOG_PREFIX} Waiting patiently for save to complete (current URL: ${window.location.href})...`);
    
    // Much more patient save detection - just wait for any change or timeout gracefully
    let attempts = 0;
    const maxAttempts = 60; // 30 seconds total (500ms * 60)
    
    while (attempts < maxAttempts) {
      const currentHash = window.location.hash;
      const currentUrl = window.location.href;
      
      if (attempts % 10 === 0) { // Log every 5 seconds
        console.log(`${LOG_PREFIX} Save check ${attempts + 1}/${maxAttempts} - current hash: ${currentHash}`);
      }
      
      // Accept completion if URL changes in any way from the edit page
      if (currentHash !== `#staff/${staffId}/edit`) {
        console.log(`${LOG_PREFIX} Save detected - URL changed from edit page to: ${currentHash}`);
        return;
      }
      
      // Also check for visual save indicators
      const saveIndicator = document.querySelector('.success, .saved, [data-success], .alert-success');
      if (saveIndicator) {
        console.log(`${LOG_PREFIX} Save detected - found success indicator`);
        await wait(2000); // Wait a bit more after success indicator
        return;
      }
      
      await wait(500);
      attempts++;
    }
    
    // If we get here, just continue anyway - Jane might have saved but not redirected
    console.warn(`${LOG_PREFIX} Save timeout reached for staff ${staffId}, but continuing anyway...`);
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
