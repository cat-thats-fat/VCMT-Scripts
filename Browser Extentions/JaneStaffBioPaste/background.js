function processBio(rawText, staffId) {
  let text = rawText.trim();

  if (text.length >= 2 && text.startsWith('"') && text.endsWith('"')) {
    text = text.slice(1, -1);
  }

  text = text.replace(/""/g, '"');
  return text.replace(/\{STAFFID\}/g, staffId);
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
  const target = document.activeElement;

  if (!isEditableElement(target)) {
    alert("No focused editable field found. Click into the bio field first, then click the extension again.");
    return;
  }

  if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) {
    const start = target.selectionStart ?? target.value.length;
    const end = target.selectionEnd ?? target.value.length;

    target.setRangeText(text, start, end, "end");
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
    return;
  }

  if (target.isContentEditable) {
    const selection = window.getSelection();

    if (!selection || selection.rangeCount === 0) {
      target.textContent = `${target.textContent || ""}${text}`;
    } else {
      const range = selection.getRangeAt(0);
      range.deleteContents();
      range.insertNode(document.createTextNode(text));
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    target.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

async function runStaffBioPaste() {
  const match = window.location.hash.match(/^#staff\/(\d+)(?:\/|$)/);
  if (!match) {
    alert("Could not find a valid staff ID in the URL. Open a Jane staff page like #staff/1567/edit and try again.");
    return;
  }

  const staffId = match[1];

  let clipboardText;
  try {
    clipboardText = await navigator.clipboard.readText();
  } catch (error) {
    alert("Clipboard access failed. Copy the bio text first, then click the extension again.");
    return;
  }

  const processedText = processBio(clipboardText, staffId);
  pasteIntoFocusedField(processedText);
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id || !tab.url) return;

  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: runStaffBioPaste
  });
});
