chrome.action.onClicked.addListener(async (tab) => {
  try {
    if (!tab.id || !tab.url) {
      console.error("[JaneBookingOn] Missing tab.id or tab.url.");
      return;
    }

    await chrome.tabs.sendMessage(tab.id, { type: "RUN_JANE_BOOKING_ON" });
  } catch (error) {
    console.error("[JaneBookingOn] Failed to trigger content script:", error);
  }
});
