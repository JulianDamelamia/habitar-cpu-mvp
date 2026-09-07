document.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("carrera-select");
  const tagsContainer = document.getElementById("carreras-tags-container");
  const hiddenInputsContainer = document.getElementById("carreras-hidden-inputs");
  const emptyMsg = document.getElementById("carreras-empty-msg");

  if (!select || !tagsContainer || !hiddenInputsContainer) return;

  const selectedValues = new Set();

  function updateEmptyMessage() {
    if (emptyMsg) {
      emptyMsg.style.display = selectedValues.size === 0 ? "block" : "none";
    }
  }

  function addTag(value, labelText) {
    if (selectedValues.has(value)) return;

    // Lógica para opcón "todas" vs individuales
    if (value === "todas") {
      Array.from(selectedValues).forEach((v) => removeTag(v));
    } else if (selectedValues.has("todas")) {
      removeTag("todas");
    }

    selectedValues.add(value);

    // Ocultar la opción en el select
    const optionToHide = select.querySelector(`option[value="${value}"]`);
    if (optionToHide) optionToHide.hidden = true;

    // 1. Crear el elemento visual (Tag)
    const tag = document.createElement("span");
    tag.id = `tag-${value}`;
    tag.className = "inline-flex items-center gap-1.5 bg-blue-100 text-blue-800 text-xs font-semibold px-3 py-1.5 rounded-full cursor-pointer hover:bg-red-100 hover:text-red-800 transition-colors";
    
    // Icono SVG
    tag.innerHTML = `
      <span>${labelText}</span>
      <svg class="w-3.5 h-3.5 opacity-70 hover:opacity-100" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
      </svg>
    `;

    // Evento de eliminación al hacer clic
    tag.addEventListener("click", () => removeTag(value));
    tagsContainer.appendChild(tag);

    // 2. Crear input oculto para enviarlo por POST
    const hiddenInput = document.createElement("input");
    hiddenInput.type = "hidden";
    hiddenInput.name = "carreras";
    hiddenInput.value = value;
    hiddenInput.id = `input-${value}`;
    hiddenInputsContainer.appendChild(hiddenInput);

    updateEmptyMessage();
    select.value = ""; // Reiniciar select
  }

  function removeTag(value) {
    selectedValues.delete(value);

    const optionToShow = select.querySelector(`option[value="${value}"]`);
    if (optionToShow) optionToShow.hidden = false;

    const tagElem = document.getElementById(`tag-${value}`);
    const inputElem = document.getElementById(`input-${value}`);

    if (tagElem) tagElem.remove();
    if (inputElem) inputElem.remove();

    updateEmptyMessage();
  }

  // Escuchar cambio en el select
  select.addEventListener("change", (e) => {
    const val = e.target.value;
    if (!val) return;

    const selectedOption = e.target.options[e.target.selectedIndex];
    const label = val === "todas" 
      ? "TODAS LAS CARRERAS" 
      : (selectedOption.getAttribute("data-nombre") || selectedOption.text);

    addTag(val, label);
  });

  // Precargar elementos en modo EDICIÓN
  const preselected = document.querySelectorAll(".preselected-carrera");
  preselected.forEach((el) => {
    const id = el.getAttribute("data-id");
    const nombre = el.getAttribute("data-nombre");
    if (id && nombre) {
      addTag(id, nombre);
    }
  });
});