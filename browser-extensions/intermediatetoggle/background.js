chrome.action.onClicked.addListener(async (tab) => {
  try {
    if (!tab.id || !tab.url) {
      console.error("[IntermediateToggle] Missing tab.id or tab.url.");
      return;
    }

    // Check if we're on a Jane admin page
    if (!tab.url.includes('vcmt.janeapp.com/admin')) {
      console.error("[IntermediateToggle] Not on a Jane admin page. Current URL:", tab.url);
      return;
    }

    // Try to send message to existing content script first
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "RUN_INTERMEDIATE_TOGGLE" });
      console.log("[IntermediateToggle] Message sent to existing content script.");
    } catch (messageError) {
      console.log("[IntermediateToggle] No content script found, injecting...", messageError.message);
      
      // Only inject if message failed (no content script exists)
      try {
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content.js']
        });
        console.log("[IntermediateToggle] Content script injected successfully.");
        
        // Wait for initialization and try message again
        await new Promise(resolve => setTimeout(resolve, 1000));
        await chrome.tabs.sendMessage(tab.id, { type: "RUN_INTERMEDIATE_TOGGLE" });
      } catch (injectError) {
        throw new Error(`Failed to inject content script: ${injectError.message}`);
      }
    }
  } catch (error) {
    console.error("[IntermediateToggle] Failed to trigger content script:", error);
    
    // Show user-friendly error
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (errorMsg) => {
          alert(`IntermediateToggle Error: ${errorMsg}\n\nPlease make sure you're on a Jane staff admin page.`);
        },
        args: [error.message]
      });
    } catch (alertError) {
      console.error("[IntermediateToggle] Could not show error alert:", alertError);
    }
  }
});