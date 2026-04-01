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
    });
  });

  async function run() {
    if (isRunning) {
      console.warn(`${LOG_PREFIX} Already running on this tab; ignoring duplicate trigger.`);
      return;
    }

    isRunning = true;

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
      } else {
        console.log(`${LOG_PREFIX} Already on edit page for staff ${staffId}.`);
      }

      await waitForRoute(`#staff/${staffId}/edit`);
      await waitForDocumentReady();

      await openOnlineBookingTab();
      await ensureOnlineBookingEnabled();
      await ensureRollingAvailabilityNoLimit();
      await clickSaveAndWaitForCompletion(staffId);

      const nextId = staffId + 1;
      const nextUrl = `${baseUrl}#staff/${nextId}/edit`;
      console.log(`${LOG_PREFIX} Moving to next staff: ${nextId}. URL: ${nextUrl}`);
      window.location.assign(nextUrl);
    } finally {
      isRunning = false;
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
      const items = Array.from(document.querySelectorAll('[role="menuitem"], li[role="menuitem"]'));
      return items.find((item) => normalizeText(item.textContent).includes("online booking"));
    }, "Online Booking tab/menu item not found.");

    clickElement(menuItem);

    await waitFor(() => document.querySelector('[name="allow_online_booking"]'),
      "Online Booking fields did not load after opening the tab.");

    console.log(`${LOG_PREFIX} Online Booking tab is active.`);
  }

  async function ensureOnlineBookingEnabled() {
    const field = await waitFor(() => document.querySelector('[name="allow_online_booking"]'),
      'Field [name="allow_online_booking"] not found.');

    const isCheckbox = field instanceof HTMLInputElement && field.type === "checkbox";

    if (isCheckbox) {
      if (field.checked) {
        console.log(`${LOG_PREFIX} Enable Online Booking is already ON.`);
        return;
      }

      console.log(`${LOG_PREFIX} Enabling Online Booking (checkbox).`);
      field.checked = true;
      field.dispatchEvent(new Event("input", { bubbles: true }));
      field.dispatchEvent(new Event("change", { bubbles: true }));
      return;
    }

    const value = String(field.value ?? "").toLowerCase();
    const truthyValues = new Set(["1", "true", "yes", "on"]);

    if (truthyValues.has(value)) {
      console.log(`${LOG_PREFIX} Enable Online Booking is already ON (value-based field).`);
      return;
    }

    console.log(`${LOG_PREFIX} Enabling Online Booking (value-based field).`);
    field.value = "1";
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async function ensureRollingAvailabilityNoLimit() {
    const select = await waitFor(() => document.querySelector('[name="max_bookable_offset"]'),
      'Field [name="max_bookable_offset"] not found.');

    if (!(select instanceof HTMLSelectElement)) {
      throw new Error('Field [name="max_bookable_offset"] is not a select element.');
    }

    const alreadyNoLimit = select.value === "";
    if (alreadyNoLimit) {
      console.log(`${LOG_PREFIX} Rolling Availability already set to No Limit.`);
      return;
    }

    const hasNoLimitOption = Array.from(select.options).some((option) => option.value === "");
    if (!hasNoLimitOption) {
      throw new Error('Could not find No Limit option (value="") for [name="max_bookable_offset"].');
    }

    console.log(`${LOG_PREFIX} Setting Rolling Availability to No Limit.`);
    select.value = "";
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async function clickSaveAndWaitForCompletion(staffId) {
    const saveButton = await waitFor(findSaveButton, "Save button not found.");

    if (saveButton.disabled) {
      await waitFor(() => {
        const freshSaveButton = findSaveButton();
        return freshSaveButton && !freshSaveButton.disabled;
      }, "Save button stayed disabled and never became clickable.");
    }

    console.log(`${LOG_PREFIX} Clicking Save.`);
    clickElement(saveButton);

    await waitForSaveCompletion(staffId);
    console.log(`${LOG_PREFIX} Save completed for staff ${staffId}.`);
  }

  async function waitForSaveCompletion(staffId) {
    const startHash = window.location.hash;

    await waitFor(() => {
      const currentHash = window.location.hash;

      if (currentHash !== startHash && /^#staff\/\d+$/.test(currentHash)) {
        return true;
      }

      const saveButton = findSaveButton();
      if (!saveButton) return false;

      if (saveButton.disabled) return false;

      const stillOnEdit = currentHash === `#staff/${staffId}/edit`;
      return stillOnEdit;
    }, "Timed out waiting for save completion signal.", DEFAULT_TIMEOUT_MS);
  }

  function findSaveButton() {
    const buttons = Array.from(document.querySelectorAll('button[type="button"], button[type="submit"], button'));
    return buttons.find((button) => normalizeText(button.textContent) === "save") || null;
  }

  async function waitForRoute(expectedHash, timeoutMs = DEFAULT_TIMEOUT_MS) {
    await waitFor(() => window.location.hash === expectedHash,
      `Timed out waiting for route ${expectedHash}.`, timeoutMs);
  }

  async function waitForDocumentReady(timeoutMs = DEFAULT_TIMEOUT_MS) {
    await waitFor(() => document.readyState === "interactive" || document.readyState === "complete",
      "Document did not reach interactive/complete readyState in time.", timeoutMs);
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
    const existing = getter();
    if (existing) return existing;

    return new Promise((resolve, reject) => {
      const start = Date.now();
      let observer;
      let interval;

      const finish = (result, error) => {
        if (observer) observer.disconnect();
        if (interval) clearInterval(interval);

        if (error) {
          reject(error);
        } else {
          resolve(result);
        }
      };

      const check = () => {
        try {
          const result = getter();
          if (result) {
            finish(result, null);
            return;
          }

          if (Date.now() - start >= timeoutMs) {
            finish(null, new Error(errorMessage));
          }
        } catch (error) {
          finish(null, error);
        }
      };

      observer = new MutationObserver(check);
      observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true
      });

      interval = setInterval(check, POLL_INTERVAL_MS);
      check();
    });
  }
})();
