const SERVER_URL = "http://127.0.0.1:9876";
const TARGET_COOKIES = ["__zp_stoken__", "wt2", "wbg", "zp_at", "bst"];

let lastSyncTime = 0;
let debounceTimer = null;

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("pollCookies", { periodInMinutes: 1 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "pollCookies") pushCookies();
});

chrome.cookies.onChanged.addListener(({ cookie }) => {
  if (!cookie.domain.includes("zhipin.com")) return;
  if (!TARGET_COOKIES.includes(cookie.name)) return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(pushCookies, 2000);
});

async function pushCookies() {
  const all = await chrome.cookies.getAll({ domain: ".zhipin.com" });
  const cookies = {};
  for (const c of all) {
    if (TARGET_COOKIES.includes(c.name)) cookies[c.name] = c.value;
  }
  if (Object.keys(cookies).length === 0) return;

  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch(`${SERVER_URL}/cookies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cookies, source: "edge-extension", timestamp: Date.now() }),
      });
      if (r.ok) { lastSyncTime = Date.now(); return; }
    } catch {}
    await new Promise(r => setTimeout(r, 1000));
  }
}

async function getStatus() {
  try {
    const r = await fetch(`${SERVER_URL}/status`);
    if (r.ok) return await r.json();
  } catch {}
  return null;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "getStatus") {
    getStatus().then(sendResponse);
    return true;
  }
  if (msg.type === "refreshNow") {
    pushCookies().then(() => {
      getStatus().then(sendResponse);
    });
    return true;
  }
});
