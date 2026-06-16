const statusEl = document.getElementById("status");
const cookiesEl = document.getElementById("cookies");
const refreshBtn = document.getElementById("refreshBtn");

async function update() {
  const resp = await chrome.runtime.sendMessage({ type: "getStatus" });
  if (!resp) {
    statusEl.textContent = "服务器未运行";
    statusEl.style.color = "red";
    return;
  }
  statusEl.textContent = "服务器已连接";
  statusEl.style.color = "green";
  const c = resp.cookies || {};
  const names = Object.keys(c);
  if (names.length === 0) {
    cookiesEl.textContent = "未找到 Cookie（请先登录 zhipin.com）";
  } else {
    cookiesEl.innerHTML = names.map(n => {
      const v = c[n];
      const masked = v.length > 16 ? v.slice(0, 8) + "..." + v.slice(-4) : v;
      return `<div><b>${n}</b>: ${masked}</div>`;
    }).join("");
  }
}

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  refreshBtn.textContent = "推送中...";
  await chrome.runtime.sendMessage({ type: "refreshNow" });
  await update();
  refreshBtn.disabled = false;
  refreshBtn.textContent = "立即推送";
});

update();
