function pad(n) {
  return String(n).padStart(2, '0');
}

function addDaysToYmd(ymd, days) {
  const match = ymd.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);

  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);

  return [
    date.getUTCFullYear(),
    pad(date.getUTCMonth() + 1),
    pad(date.getUTCDate())
  ].join('-');
}

chrome.action.onClicked.addListener((tab) => {
  if (!tab.id || !tab.url) return;

  const url = new URL(tab.url);
  const hash = url.hash;

  let match;
  let keepShifts = false;

  // #schedule/staff/1782-1783-1784/2026-06-29
  match = hash.match(/^#schedule\/staff\/[\d-]+\/(\d{4}-\d{2}-\d{2})$/);
  if (match) {
    keepShifts = false;
  }

  // #schedule/staff/1782-1783-1784/shifts/2026-06-29
  if (!match) {
    match = hash.match(/^#schedule\/staff\/[\d-]+\/shifts\/(\d{4}-\d{2}-\d{2})$/);
    if (match) keepShifts = true;
  }

  // Also support already-clean hashes:
  // #schedule/2026-06-29
  if (!match) {
    match = hash.match(/^#schedule\/(\d{4}-\d{2}-\d{2})$/);
    if (match) keepShifts = false;
  }

  // #schedule/shifts/2026-06-29
  if (!match) {
    match = hash.match(/^#schedule\/shifts\/(\d{4}-\d{2}-\d{2})$/);
    if (match) keepShifts = true;
  }

  if (!match) return;

  const currentDate = match[1];
  const nextDate = addDaysToYmd(currentDate, 7);
  if (!nextDate) return;

  url.hash = keepShifts
  ? `#schedule/shifts/${nextDate}`
  : `#schedule/${nextDate}`;

  chrome.tabs.update(tab.id, { url: url.toString() });
});
