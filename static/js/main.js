const users = window.APP_USERS || [];

document.addEventListener("DOMContentLoaded", () => {
  syncUserInterests();
  bindEvents();
  fetchDailyFlash();
});

function bindEvents() {
  const userSelect = document.getElementById("userSelect");
  const recommendBtn = document.getElementById("recommendBtn");
  userSelect.addEventListener("change", () => {
    syncUserInterests();
  });
  recommendBtn.addEventListener("click", () => {
    requestRecommendations();
  });
}

function syncUserInterests() {
  const user = getCurrentUser();
  const interests = (user && user.interests) || [];
  document.querySelectorAll(".interest-checkbox").forEach((checkbox) => {
    checkbox.checked = interests.includes(checkbox.value);
  });
}

function getCurrentUser() {
  const userSelect = document.getElementById("userSelect");
  if (!userSelect) return null;
  return users.find((u) => u.user_id === userSelect.value) || null;
}

function fetchDailyFlash() {
  fetch("/api/daily_flash")
    .then((res) => res.json())
    .then((data) => {
      renderTypewriter(data.message || "AI 还在睡懒觉，稍后再来看看~");
    })
    .catch(() => {
      renderTypewriter("网络开小差了，早报稍后送达 🚧");
    });
}

function renderTypewriter(text) {
  const container = document.getElementById("dailyFlash");
  if (!container) return;
  container.textContent = "";
  const cursor = document.createElement("span");
  cursor.className = "typing-cursor";
  container.appendChild(cursor);

  let index = 0;
  const interval = setInterval(() => {
    if (index >= text.length) {
      clearInterval(interval);
      cursor.remove();
      container.textContent = text;
      return;
    }
    cursor.before(document.createTextNode(text[index]));
    index += 1;
  }, 40);
}

function requestRecommendations() {
  const user = getCurrentUser();
  if (!user) {
    showToast("请先创建用户", "warning");
    return;
  }
  const recommendBtn = document.getElementById("recommendBtn");
  recommendBtn.disabled = true;
  recommendBtn.textContent = "AI 正在思考...";
  const selectedTags = Array.from(
    document.querySelectorAll(".interest-checkbox:checked")
  ).map((input) => input.value);
  fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: user.user_id, interests: selectedTags }),
  })
    .then((res) => res.json())
    .then((data) => {
      renderCards(data.items || []);
      if (data.message) {
        showToast(data.message, "warning");
      }
    })
    .catch(() => {
      showToast("推荐失败，请稍后再试", "danger");
    })
    .finally(() => {
      recommendBtn.disabled = false;
      recommendBtn.textContent = "看点有意思的 🤓";
    });
}

function renderCards(items) {
  const cardsRow = document.getElementById("cardsRow");
  const emptyState = document.getElementById("emptyState");
  cardsRow.innerHTML = "";
  if (!items.length) {
    emptyState.classList.remove("d-none");
    return;
  }
  emptyState.classList.add("d-none");
  items.forEach((item) => {
    const col = document.createElement("div");
    col.className = "col-md-4";
    col.innerHTML = createCardTemplate(item);
    cardsRow.appendChild(col);
  });
  bindLikeButtons();
}

function createCardTemplate(item) {
  const imageBlock = item.top_image
    ? `<img src="${item.top_image}" alt="${item.title}" />`
    : `<div class="placeholder-image d-flex align-items-center justify-content-center bg-light text-secondary">
        <span>暂无头图</span>
      </div>`;
  return `
    <div class="news-card h-100">
      ${imageBlock}
      <div class="p-3 d-flex flex-column flex-grow-1">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h3 class="h6 mb-0">${item.title}</h3>
        </div>
        <blockquote class="mb-3">${item.ai_comment || "AI 已经被调侃笑翻，稍后补上"}</blockquote>
        <div class="mt-auto">
          <div class="d-flex gap-2">
            <a class="btn btn-link px-0" href="${item.url}" target="_blank" rel="noopener">
              🔗 原文
            </a>
            <button class="btn btn-outline-danger btn-sm ms-auto like-btn" data-url="${item.url}" data-title="${item.title}">
              ❤️ 挺有意思
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function bindLikeButtons() {
  document.querySelectorAll(".like-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const user = getCurrentUser();
      if (!user) return;
      fetch("/api/log_action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: user.user_id,
          url: btn.dataset.url,
          title: btn.dataset.title,
          action: "like",
        }),
      })
        .then(() => {
          showToast("已记录偏好", "success");
        })
        .catch(() => showToast("记录失败，请稍后再试", "danger"));
    });
  });
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const wrapper = document.createElement("div");
  wrapper.className = `toast align-items-center text-bg-${type} border-0`;
  wrapper.role = "alert";
  wrapper.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  `;
  container.appendChild(wrapper);
  const toast = new bootstrap.Toast(wrapper, { delay: 2500 });
  toast.show();
  toast._element.addEventListener("hidden.bs.toast", () => {
    wrapper.remove();
  });
}
