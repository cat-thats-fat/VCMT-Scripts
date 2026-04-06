
async function runStaffBioPaste() {
  function processBio(rawText, staffId) {
    console.log('processBio called with rawText length:', rawText.length, 'staffId:', staffId);
    let text = rawText.trim();

    if (text.length >= 2 && text.startsWith('"') && text.endsWith('"')) {
      text = text.slice(1, -1);
      console.log('Removed surrounding quotes');
    }

    text = text.replace(/""/g, '"');
    console.log('Replaced double quotes');
    
    const result = text.replace(/\{STAFFID\}/g, staffId);
    console.log('processBio returning text with length:', result.length);
    return result;
  }

  function isEditableElement(el) {
    if (!el) return false;

    if (el instanceof HTMLTextAreaElement) return true;

    if (el instanceof HTMLInputElement) {
      const nonTextTypes = new Set([
        "button",
        "checkbox",
        "color",
        "file",
        "hidden",
        "image",
        "radio",
        "range",
        "reset",
        "submit"
      ]);

      return !nonTextTypes.has((el.type || "text").toLowerCase());
    }

    return el.isContentEditable;
  }

  function pasteIntoFocusedField(text) {
    console.log('pasteIntoFocusedField called with text length:', text.length);
    const target = document.activeElement;
    console.log('Active element:', target);
    console.log('Active element tag:', target?.tagName);
    console.log('Active element type:', target?.type);

    if (!isEditableElement(target)) {
      console.log('No editable element found');
      alert("No focused editable field found. Click into the bio field first, then click the extension again.");
      return;
    }

    if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) {
      console.log('Pasting into input/textarea element');
      const start = target.selectionStart ?? target.value.length;
      const end = target.selectionEnd ?? target.value.length;
      console.log('Selection range:', start, 'to', end);
      console.log('Current value length:', target.value.length);

      target.setRangeText(text, start, end, "end");
      console.log('Text set, new value length:', target.value.length);
      
      target.dispatchEvent(new Event("input", { bubbles: true }));
      target.dispatchEvent(new Event("change", { bubbles: true }));
      console.log('Events dispatched for input/textarea');
      return;
    }

    if (target.isContentEditable) {
      console.log('Pasting into contentEditable element');
      const selection = window.getSelection();
      console.log('Selection:', selection);
      console.log('Range count:', selection?.rangeCount);

      if (!selection || selection.rangeCount === 0) {
        console.log('No selection, appending to textContent');
        const oldContent = target.textContent || "";
        target.textContent = `${oldContent}${text}`;
        console.log('New textContent length:', target.textContent.length);
      } else {
        console.log('Using selection range');
        const range = selection.getRangeAt(0);
        range.deleteContents();
        range.insertNode(document.createTextNode(text));
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
        console.log('Text inserted via selection range');
      }

      target.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
      target.dispatchEvent(new Event("change", { bubbles: true }));
      console.log('Events dispatched for contentEditable');
    }
  }

  try {
    console.log('runStaffBioPaste started');
    console.log('Current URL:', window.location.href);
    console.log('Current hash:', window.location.hash);
  
  const match = window.location.hash.match(/^#staff\/(\d+)(?:\/|$)/);
  if (!match) {
    console.log('No staff ID match found in hash');
    alert("Could not find a valid staff ID in the URL. Open a Jane staff page like #staff/1567/edit and try again.");
    return;
  }

  const staffId = match[1];
  console.log('Found staff ID:', staffId);

  let clipboardText;
  try {
    clipboardText = await navigator.clipboard.readText();
    console.log('Clipboard text read:', clipboardText.substring(0, 100) + '...');
  } catch (error) {
    console.error('Clipboard access failed:', error);
    alert("Clipboard access failed. Copy the bio text first, then click the extension again.");
    return;
  }

  console.log('About to process bio text...');
  let processedText;
  try {
    processedText = processBio(clipboardText, staffId);
    console.log('Processed text:', processedText.substring(0, 100) + '...');
  } catch (error) {
    console.error('Error in processBio:', error);
    alert('Error processing bio text: ' + error.message);
    return;
  }
  
  console.log('About to call pasteIntoFocusedField...');
  try {
    pasteIntoFocusedField(processedText);
    console.log('pasteIntoFocusedField call completed');
  } catch (error) {
    console.error('Error in pasteIntoFocusedField:', error);
    alert('Error pasting text: ' + error.message);
  }
  } catch (error) {
    console.error('Error in runStaffBioPaste:', error);
    alert('Extension error: ' + error.message);
  }
}

chrome.action.onClicked.addListener(async (tab) => {
  console.log('Extension clicked, tab:', tab);
  
  if (!tab.id || !tab.url) {
    console.log('No tab ID or URL found');
    return;
  }

  try {
    console.log('Injecting script into tab:', tab.id);
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: runStaffBioPaste
    });
    console.log('Script injection completed');
  } catch (error) {
    console.error('Script injection failed:', error);
  }
});
