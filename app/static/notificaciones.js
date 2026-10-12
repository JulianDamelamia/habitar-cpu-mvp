(() => {
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));

  function activateTab(tab) {
    tabs.forEach((item) => {
      const active = item === tab;
      item.setAttribute("aria-selected", String(active));
      item.tabIndex = active ? 0 : -1;
      item.classList.toggle("border-indigo-600", active);
      item.classList.toggle("text-indigo-700", active);
      item.classList.toggle("font-medium", active);
      item.classList.toggle("border-transparent", !active);
      item.classList.toggle("text-slate-500", !active);
    });
    panels.forEach((panel) => {
      panel.classList.toggle("hidden", panel.id !== tab.getAttribute("aria-controls"));
    });
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const offset = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(index + offset + tabs.length) % tabs.length];
      activateTab(next);
      next.focus();
    });
  });

  document.querySelectorAll(".message-item").forEach((item) => {
    item.addEventListener("toggle", async () => {
      if (!item.open || item.dataset.read === "true") return;
      const response = await fetch(item.dataset.readUrl, {
        method: "POST",
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) {
        console.error(`Could not mark message read: HTTP ${response.status}`);
        return;
      }
      item.dataset.read = "true";
      item.classList.remove("bg-indigo-50/50");
      item.querySelector(".message-unread")?.classList.add("hidden");
      const unreadBadge = document.querySelector("#mensajes-no-leidos");
      if (unreadBadge) {
        unreadBadge.textContent = String(Math.max(0, Number(unreadBadge.textContent) - 1));
      }
      item.querySelector("summary > span.min-w-0 > span > span")?.classList.replace(
        "text-slate-900",
        "text-slate-700",
      );
    });
  });
})();
