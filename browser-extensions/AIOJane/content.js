(() => {
  const OFFSET_VALUE = "2628000";
  const TIMEOUT_MS = 15000;

  let isRunning = false;

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "RUN_BOOKING_HELPER") {
      run().catch((error) => {
        console.error("JaneApp helper failed:", error);
        alert(`JaneApp helper failed: ${error.message}`);
      });
    }
  });

  async function run() {
    if (isRunning) {
      console.log("JaneApp helper is already running on this tab.");
      return;
    }

    isRunning = true;

    try {
      const parsed = parseStaffUrl(window.location.href);
      if (!parsed) {
        throw new Error("Current URL is not a supported Jane staff page.");
      }

      const { baseUrl, staffId } = parsed;
      const editUrl = `${baseUrl}#staff/${staffId}/edit`;

      // Go to edit page if not already there
      if (window.location.href !== editUrl) {
        window.location.href = editUrl;
        await waitForLocation(editUrl);
      }

      await clickOnlineBooking();
      await setMaxBookableOffset(OFFSET_VALUE);
      await clickSave();

      // Wait for Jane to finish saving and leave edit mode
      await waitFor(
        () => window.location.hash === `#staff/${staffId}`,
                    `Timed out waiting for save to finish for staff ${staffId}`,
                    10000
      );

      // Then move to the next staff
      const nextUrl = `${baseUrl}#staff/${staffId + 1}`;
      window.location.href = nextUrl;
    } finally {
      isRunning = false;
    }
  }

  function parseStaffUrl(urlString) {
    const url = new URL(urlString);
    const match = url.hash.match(/^#staff\/(\d+)(?:\/edit)?$/);
    if (!match) return null;

    return {
      baseUrl: `${url.origin}${url.pathname}`,
      staffId: Number(match[1]),
    };
  }

  async function clickOnlineBooking() {
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
      return document.querySelector('[name="max_bookable_offset"]');
    }, 'Field [name="max_bookable_offset"] did not appear after clicking Online Booking');
  }

  async function setMaxBookableOffset(value) {
    const field = await waitFor(() => {
      return document.querySelector('[name="max_bookable_offset"]');
    }, 'Field [name="max_bookable_offset"] not found');

    field.focus();
    field.value = value;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    field.blur();

    await wait(250);
  }

  async function clickSave() {
    const saveButton = await waitFor(() => {
      const buttons = Array.from(document.querySelectorAll("button"));
      return buttons.find((btn) => normalizeText(btn.textContent) === "save");
    }, "Save button not found");

    clickElement(saveButton);
    await wait(300);
  }

  function clickElement(element) {
    const clickable = element.querySelector("a, button") || element;
    clickable.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
    clickable.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
    clickable.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    clickable.click();
  }

  function normalizeText(text) {
    return (text || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  async function waitFor(getter, errorMessage, timeoutMs = TIMEOUT_MS) {
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
      const result = getter();
      if (result) return result;
      await wait(150);
    }

    throw new Error(errorMessage);
  }

  async function waitForLocation(expectedUrl, timeoutMs = TIMEOUT_MS) {
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
})();
