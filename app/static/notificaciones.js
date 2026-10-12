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
      document.querySelectorAll("#mensajes-no-leidos, #consultas-no-leidos").forEach((badge) => {
        badge.textContent = String(Math.max(0, Number(badge.textContent) - 1));
      });
      item.querySelector("summary > span.min-w-0 > span > span")?.classList.replace(
        "text-slate-900",
        "text-slate-700",
      );
    });
  });
  document.addEventListener("DOMContentLoaded", () => {
  const checkboxTodos = document.getElementById("enviar_a_todos");
  const seccionDestinatarios = document.getElementById("seccion-destinatarios");
  const inputBuscador = document.getElementById("buscador-destinatarios");
  const dropdownResultados = document.getElementById("dropdown-resultados");
  const chipsContainer = document.getElementById("chips-container");
  const placeholderChips = document.getElementById("placeholder-chips");
  const inputsOcultos = document.getElementById("inputs-ocultos");

  if (
    !checkboxTodos ||
    !seccionDestinatarios ||
    !inputBuscador ||
    !dropdownResultados ||
    !chipsContainer ||
    !placeholderChips ||
    !inputsOcultos
  ) {
    return;
  }

  let seleccionados = new Map(); // Almacena id -> { id, tipo, texto }

  // Toggle sección si se marca "Enviar a todos"
  checkboxTodos.addEventListener("change", (e) => {
    if (e.target.checked) {
      seccionDestinatarios.classList.add("opacity-50", "pointer-events-none");
    } else {
      seccionDestinatarios.classList.remove("opacity-50", "pointer-events-none");
    }
  });

  // Combinar todos los datos disponibles en una sola lista enriquecida
  const { estudiantes, carreras, actividades } = window.DATOS_DISPONIBLES || { estudiantes: [], carreras: [], actividades: [] };
  const todosLosElementos = [...estudiantes, ...carreras, ...actividades];

  // Filtrar al escribir en el buscador
  inputBuscador.addEventListener("input", (e) => {
    const query = e.target.value.toLowerCase().trim();
    if (query.length === 0) {
      dropdownResultados.classList.add("hidden");
      return;
    }

    const filtrados = todosLosElementos.filter(item =>
      item.texto.toLocaleLowerCase().includes(query) && !seleccionados.has(item.id)
    ).slice(0, 10); // Limitar a 10 resultados para rendimiento

    dropdownResultados.replaceChildren();
    if (filtrados.length === 0) {
      const empty = document.createElement("div");
      empty.className = "p-3 text-xs text-slate-400";
      empty.textContent = "No se encontraron resultados";
      dropdownResultados.appendChild(empty);
    } else {
      filtrados.forEach((item) => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "w-full p-2.5 text-sm hover:bg-slate-100 cursor-pointer flex justify-between items-center border-b border-slate-100 last:border-none text-left";
        option.dataset.id = item.id;
        option.dataset.tipo = item.tipo;
        option.dataset.texto = item.texto;

        const label = document.createElement("span");
        label.textContent = item.texto;
        const kind = document.createElement("span");
        kind.className = "text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium uppercase";
        kind.textContent = item.tipo;
        option.append(label, kind);
        dropdownResultados.appendChild(option);
      });
    }
    dropdownResultados.classList.remove("hidden");
  });

  // Seleccionar un elemento del dropdown
  dropdownResultados.addEventListener("click", (e) => {
    const target = e.target.closest("button[data-id]");
    if (!target) return;

    const id = target.dataset.id;
    const tipo = target.dataset.tipo;
    const texto = target.dataset.texto;

    seleccionados.set(id, { id, tipo, texto });
    inputBuscador.value = "";
    dropdownResultados.classList.add("hidden");
    actualizarUI();
  });

  // Renderizar chips e inputs ocultos
  function actualizarUI() {
    chipsContainer.innerHTML = "";
    inputsOcultos.innerHTML = "";

    if (seleccionados.size === 0) {
      chipsContainer.appendChild(placeholderChips);
      return;
    }

    seleccionados.forEach((item) => {
      // Crear Chip visual
      const chip = document.createElement("span");
      chip.className = "inline-flex items-center gap-1.5 bg-indigo-50 text-indigo-700 text-xs font-medium px-2.5 py-1 rounded-full border border-indigo-100";
      const label = document.createElement("span");
      label.className = "opacity-70 font-semibold";
      label.textContent = `[${item.tipo}]`;
      const text = document.createElement("span");
      text.textContent = item.texto;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "hover:text-indigo-900 font-bold ml-0.5";
      remove.dataset.remove = item.id;
      remove.setAttribute("aria-label", `Quitar ${item.texto}`);
      remove.textContent = "×";
      chip.append(label, text, remove);
      chipsContainer.appendChild(chip);

      // Crear input oculto para enviar al backend
      const inputOculto = document.createElement("input");
      inputOculto.type = "hidden";
      inputOculto.name = "destinatarios_seleccionados"; // O puedes separarlos por tipo si tu backend lo prefiere
      inputOculto.value = item.id;
      inputsOcultos.appendChild(inputOculto);
    });
  }

  // Quitar elemento al hacer clic en la "×" del chip
  chipsContainer.addEventListener("click", (e) => {
    const remove = e.target.closest("button[data-remove]");
    if (remove) {
      seleccionados.delete(remove.dataset.remove);
      actualizarUI();
    }
  });

  // Cerrar dropdown si se hace clic fuera
  document.addEventListener("click", (e) => {
    if (!inputBuscador.contains(e.target) && !dropdownResultados.contains(e.target)) {
      dropdownResultados.classList.add("hidden");
    }
  });
});
})();
