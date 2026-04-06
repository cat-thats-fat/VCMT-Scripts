chrome.action.onClicked.addListener(async (tab) => {
  try {
    if (!tab.id || !tab.url) {
      console.log("Missing tab id or URL");
      return;
    }

    await chrome.tabs.sendMessage(tab.id, { type: "RUN_BOOKING_HELPER" });
  } catch (error) {
    console.error("Failed to start helper:", error);
  }
});
