chrome.action.onClicked.addListener((tab) => {
  if (!tab.id || !tab.url) return;

  const url = new URL(tab.url);
  const match = url.hash.match(/^#staff\/(\d+)(\/edit)?$/);
  if (!match) return;

  const nextId = Number(match[1]) + 1;
  const newUrl = `${url.origin}${url.pathname}#staff/${nextId}/edit`;

  const listener = async (updatedTabId, changeInfo) => {
    if (updatedTabId !== tab.id || changeInfo.status !== "complete") return;

    chrome.tabs.onUpdated.removeListener(listener);

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        let tries = 0;

        const timer = setInterval(() => {
          tries++;

          const items = Array.from(
            document.querySelectorAll('li[role="menuitem"].nav-pill')
          );

          const onlineBooking = items.find((el) =>
          (el.textContent || "").trim().includes("Online Booking")
          );

          if (onlineBooking) {
            onlineBooking.click();
            clearInterval(timer);
          }

          if (tries > 40) {
            clearInterval(timer);
          }
        }, 250);
      }
    });
  };

  chrome.tabs.onUpdated.addListener(listener);
  chrome.tabs.update(tab.id, { url: newUrl });
});
