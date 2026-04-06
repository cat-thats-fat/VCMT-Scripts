chrome.action.onClicked.addListener(async (tab) => {
  try {
    if (!tab.id || !tab.url) {
      console.error("[JaneBookingOn] Missing tab.id or tab.url.");
      return;
    }

    // Check if we're on a Jane admin page
    if (!tab.url.includes('vcmt.janeapp.com/admin')) {
      console.error("[JaneBookingOn] Not on a Jane admin page. Current URL:", tab.url);
      return;
    }

    // Try to send message to existing content script first
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "RUN_JANE_BOOKING_ON" });
      console.log("[JaneBookingOn] Message sent to existing content script.");
    } catch (messageError) {
      console.log("[JaneBookingOn] No content script found, injecting...", messageError.message);
      
      // Only inject if message failed (no content script exists)
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content.js']
        });
        console.log("[JaneBookingOn] Content script injected successfully.");
        
        // Wait for initialization and try message again
        await new Promise(resolve => setTimeout(resolve, 1000));
        await chrome.tabs.sendMessage(tab.id, { type: "RUN_JANE_BOOKING_ON" });
      } catch (injectError) {
        throw new Error(`Failed to inject content script: ${injectError.message}`);
      }
    }
  } catch (error) {
    console.error("[JaneBookingOn] Failed to trigger content script:", error);
    
    // Show user-friendly error
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (errorMsg) => {
          alert(`JaneBookingOn Error: ${errorMsg}\n\nPlease make sure you're on a Jane staff admin page.`);
        },
        args: [error.message]
      });
    } catch (alertError) {
      console.error("[JaneBookingOn] Could not show error alert:", alertError);
    }
  }
});
