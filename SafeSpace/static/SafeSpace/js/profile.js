"use strict";

const profileTabs = Array.from(
    document.querySelectorAll("[data-profile-tab]"),
);
const profilePanels = Array.from(
    document.querySelectorAll("[data-profile-panel]"),
);

const activateProfileTab = (selectedTab) => {
    const selectedSection = selectedTab.dataset.profileTab;

    for (const tab of profileTabs) {
        const isSelected = tab === selectedTab;
        tab.setAttribute("aria-selected", String(isSelected));
        tab.tabIndex = isSelected ? 0 : -1;
        tab.classList.toggle("is-active", isSelected);
    }

    for (const panel of profilePanels) {
        panel.hidden = panel.dataset.profilePanel !== selectedSection;
    }
};

const profileLayout = document.querySelector(".profile-layout");
const tabFromHash = window.location.hash.replace("#panel-", "");
const requestedProfileTab =
    tabFromHash ||
    (profileLayout instanceof HTMLElement
        ? profileLayout.dataset.activeProfileTab
        : "");
const initialProfileTab = profileTabs.find(
    (tab) => tab.dataset.profileTab === requestedProfileTab,
);
if (initialProfileTab instanceof HTMLButtonElement) {
    activateProfileTab(initialProfileTab);
}

for (const tab of profileTabs) {
    if (!(tab instanceof HTMLButtonElement)) {
        continue;
    }

    tab.addEventListener("click", () => activateProfileTab(tab));
    tab.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            return;
        }

        event.preventDefault();
        const currentIndex = profileTabs.indexOf(tab);
        const nextIndex =
            event.key === "Home"
                ? 0
                : event.key === "End"
                  ? profileTabs.length - 1
                  : (currentIndex +
                        (event.key === "ArrowRight" ? 1 : -1) +
                        profileTabs.length) %
                    profileTabs.length;
        const nextTab = profileTabs[nextIndex];

        if (nextTab instanceof HTMLButtonElement) {
            activateProfileTab(nextTab);
            nextTab.focus();
        }
    });
}

const photoInput = document.querySelector("[data-profile-photo]");
const photoPreview = document.querySelector("[data-photo-preview]");
const photoStatus = document.querySelector("[data-photo-status]");
const cropDialog = document.querySelector("[data-photo-crop-dialog]");
const cropViewport = document.querySelector("[data-photo-crop-viewport]");
const cropImage = document.querySelector("[data-photo-crop-image]");
const zoomInput = document.querySelector("[data-photo-zoom]");
const cropConfirm = document.querySelector("[data-photo-crop-confirm]");
const cropCancelButtons = document.querySelectorAll("[data-photo-crop-cancel]");

if (
    photoInput instanceof HTMLInputElement &&
    photoPreview instanceof HTMLElement &&
    photoStatus instanceof HTMLElement &&
    cropDialog instanceof HTMLDialogElement &&
    cropViewport instanceof HTMLElement &&
    cropImage instanceof HTMLImageElement &&
    zoomInput instanceof HTMLInputElement &&
    cropConfirm instanceof HTMLButtonElement
) {
    const initialPreview = photoPreview.cloneNode(true);
    let sourceUrl = "";
    let previewUrl = "";
    let cropTranslationX = 0;
    let cropTranslationY = 0;
    let dragStartX = 0;
    let dragStartY = 0;
    let pointerStartX = 0;
    let pointerStartY = 0;
    let cropConfirmed = false;

    const updateCropImage = () => {
        if (!cropImage.complete || !cropImage.naturalWidth) {
            return;
        }

        const size = cropViewport.clientWidth;
        const coverScale = Math.max(
            size / cropImage.naturalWidth,
            size / cropImage.naturalHeight,
        );
        const scale = coverScale * Number(zoomInput.value);
        const width = cropImage.naturalWidth * scale;
        const height = cropImage.naturalHeight * scale;
        cropTranslationX = Math.max(
            (size - width) / 2,
            Math.min((width - size) / 2, cropTranslationX),
        );
        cropTranslationY = Math.max(
            (size - height) / 2,
            Math.min((height - size) / 2, cropTranslationY),
        );
        cropImage.style.width = `${width}px`;
        cropImage.style.height = `${height}px`;
        cropImage.style.left = `${(size - width) / 2 + cropTranslationX}px`;
        cropImage.style.top = `${(size - height) / 2 + cropTranslationY}px`;
    };

    const restoreInitialPreview = () => {
        photoPreview.replaceChildren(
            ...Array.from(initialPreview.childNodes, (node) => node.cloneNode(true)),
        );
    };

    const closeCropDialog = () => {
        cropConfirmed = false;
        if (cropDialog.open) {
            cropDialog.close();
        }
        if (sourceUrl) {
            URL.revokeObjectURL(sourceUrl);
            sourceUrl = "";
        }
        cropImage.removeAttribute("src");
    };

    photoInput.addEventListener("change", () => {
        const [file] = photoInput.files ?? [];
        if (!file) {
            return;
        }
        if (
            !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
            file.size > 5_000_000
        ) {
            photoInput.value = "";
            photoStatus.textContent =
                file.size > 5_000_000
                    ? "A imagem precisa ter no máximo 5 MB."
                    : "Use uma imagem JPEG, PNG ou WebP.";
            return;
        }

        photoStatus.textContent = "";
        if (sourceUrl) {
            URL.revokeObjectURL(sourceUrl);
        }
        cropConfirm.disabled = true;
        sourceUrl = URL.createObjectURL(file);
        cropTranslationX = 0;
        cropTranslationY = 0;
        zoomInput.value = "1";
        cropConfirmed = false;
        cropImage.addEventListener("load", () => {
            cropDialog.showModal();
            updateCropImage();
            cropConfirm.disabled = false;
        }, { once: true });
        cropImage.addEventListener("error", () => {
            cropConfirm.disabled = true;
            photoStatus.textContent = "Não foi possível carregar a prévia da imagem.";
            photoInput.value = "";
            restoreInitialPreview();
            closeCropDialog();
        }, { once: true });
        cropImage.src = sourceUrl;
    });

    zoomInput.addEventListener("input", updateCropImage);
    cropViewport.addEventListener("pointerdown", (event) => {
        if (!(event instanceof PointerEvent)) {
            return;
        }
        cropViewport.setPointerCapture(event.pointerId);
        pointerStartX = event.clientX;
        pointerStartY = event.clientY;
        dragStartX = cropTranslationX;
        dragStartY = cropTranslationY;
    });
    cropViewport.addEventListener("pointermove", (event) => {
        if (
            !(event instanceof PointerEvent) ||
            !cropViewport.hasPointerCapture(event.pointerId)
        ) {
            return;
        }
        cropTranslationX = dragStartX + event.clientX - pointerStartX;
        cropTranslationY = dragStartY + event.clientY - pointerStartY;
        updateCropImage();
    });
    cropViewport.addEventListener("pointerup", (event) => {
        if (
            event instanceof PointerEvent &&
            cropViewport.hasPointerCapture(event.pointerId)
        ) {
            cropViewport.releasePointerCapture(event.pointerId);
        }
    });

    cropConfirm.addEventListener("click", () => {
        const size = cropViewport.clientWidth;
        const coverScale = Math.max(
            size / cropImage.naturalWidth,
            size / cropImage.naturalHeight,
        );
        const scale = coverScale * Number(zoomInput.value);
        const renderedWidth = cropImage.naturalWidth * scale;
        const renderedHeight = cropImage.naturalHeight * scale;
        const left = (size - renderedWidth) / 2 + cropTranslationX;
        const top = (size - renderedHeight) / 2 + cropTranslationY;
        const sourceX = Math.max(0, -left / scale);
        const sourceY = Math.max(0, -top / scale);
        const sourceSize = Math.min(
            size / scale,
            cropImage.naturalWidth - sourceX,
            cropImage.naturalHeight - sourceY,
        );
        const canvas = document.createElement("canvas");
        canvas.width = 512;
        canvas.height = 512;
        const context = canvas.getContext("2d");
        if (!context || sourceSize <= 0) {
            photoStatus.textContent = "Não foi possível recortar esta imagem.";
            return;
        }

        context.drawImage(
            cropImage,
            sourceX,
            sourceY,
            sourceSize,
            sourceSize,
            0,
            0,
            canvas.width,
            canvas.height,
        );
        canvas.toBlob((blob) => {
            if (!cropDialog.open) {
                return;
            }
            if (!blob) {
                photoStatus.textContent = "Não foi possível preparar esta foto.";
                return;
            }
            const croppedFile = new File(
                [blob],
                "profile-photo.jpg",
                { type: "image/jpeg" },
            );
            const transfer = new DataTransfer();
            transfer.items.add(croppedFile);
            photoInput.files = transfer.files;

            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
            }
            previewUrl = URL.createObjectURL(blob);
            const image = document.createElement("img");
            image.src = previewUrl;
            image.alt = "";
            image.className = "profile-photo-image";
            photoPreview.replaceChildren(image);
            photoStatus.textContent = "A foto será salva ao atualizar as informações.";
            cropConfirmed = true;
            cropDialog.close();
        }, "image/jpeg", 0.9);
    });

    for (const cancelButton of cropCancelButtons) {
        if (cancelButton instanceof HTMLButtonElement) {
            cancelButton.addEventListener("click", () => {
                photoInput.value = "";
                restoreInitialPreview();
                closeCropDialog();
            });
        }
    }

    cropDialog.addEventListener("click", (event) => {
        if (event.target === cropDialog) {
            photoInput.value = "";
            restoreInitialPreview();
            closeCropDialog();
        }
    });
    cropDialog.addEventListener("close", () => {
        if (!cropConfirmed) {
            photoInput.value = "";
            restoreInitialPreview();
        }
        closeCropDialog();
    });
    window.addEventListener("beforeunload", () => {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }
    });
}

const setupIncrementalFields = ({
    list,
    addButton,
    idPrefix,
    fields,
    rowClass = "",
    removeLabel,
    maxRows = Number.POSITIVE_INFINITY,
}) => {
    if (!(list instanceof HTMLElement) || !(addButton instanceof HTMLButtonElement)) {
        return;
    }

    let nextId = list.querySelectorAll(".incremental-row").length + 1;
    const updateAddButton = () => {
        addButton.disabled = list.querySelectorAll(".incremental-row").length >= maxRows;
    };

    const bindRemoveButton = (row, button) => {
        button.addEventListener("click", () => {
            const rows = list.querySelectorAll(".incremental-row");
            if (rows.length > 1) {
                row.remove();
                updateAddButton();
                return;
            }

            for (const input of row.querySelectorAll("input")) {
                if (input instanceof HTMLInputElement) {
                    input.value = "";
                }
            }
        });
    };

    for (const row of list.querySelectorAll(".incremental-row")) {
        const removeButton = row.querySelector("button");
        if (removeButton instanceof HTMLButtonElement) {
            removeButton.disabled = false;
            bindRemoveButton(row, removeButton);
        }
    }
    updateAddButton();

    addButton.addEventListener("click", () => {
        if (list.querySelectorAll(".incremental-row").length >= maxRows) {
            updateAddButton();
            return;
        }

        const rowIndex = nextId;
        nextId += 1;
        const row = document.createElement("div");
        row.className = `incremental-row ${rowClass}`.trim();

        for (const field of fields) {
            const wrapper = document.createElement("div");
            const input = document.createElement("input");
            const label = document.createElement("label");
            const fieldId = `${idPrefix}-${field.key}-${rowIndex}`;

            input.id = fieldId;
            input.name = field.name;
            input.type = field.type ?? "text";
            input.placeholder = field.placeholder;
            if (field.autocomplete) {
                input.autocomplete = field.autocomplete;
            }
            if (field.maxLength) {
                input.maxLength = field.maxLength;
            }
            if (field.mask) {
                input.dataset.phoneMask = field.mask;
                input.inputMode = "tel";
            }
            label.htmlFor = fieldId;
            label.className = "visually-hidden";
            label.textContent = field.label;
            wrapper.append(label, input);
            row.append(wrapper);
        }

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "remove-row";
        removeButton.setAttribute("aria-label", removeLabel);
        removeButton.textContent = "×";
        bindRemoveButton(row, removeButton);
        row.append(removeButton);
        list.append(row);
        updateAddButton();
        row.querySelector("input")?.focus();
    });
};

setupIncrementalFields({
    list: document.querySelector("[data-medication-list]"),
    addButton: document.querySelector("[data-add-medication]"),
    idPrefix: "medication",
    rowClass: "medication-row",
    removeLabel: "Remover medicamento",
    fields: [
        {
            key: "name",
            name: "medication[]",
            label: "Medicamento",
            placeholder: "Nome do medicamento",
            maxLength: 160,
        },
        {
            key: "dosage",
            name: "medication_dosage[]",
            label: "Dose",
            placeholder: "Dose",
            maxLength: 120,
        },
        {
            key: "instructions",
            name: "medication_instructions[]",
            label: "Instruções",
            placeholder: "Instruções",
            maxLength: 240,
        },
    ],
});

setupIncrementalFields({
    list: document.querySelector("[data-emergency-contact-list]"),
    addButton: document.querySelector("[data-add-emergency-contact]"),
    idPrefix: "emergency-contact",
    rowClass: "emergency-contact-row",
    removeLabel: "Remover contato de emergência",
    maxRows: 3,
    fields: [
        {
            key: "name",
            name: "emergency_contact_name[]",
            label: "Nome do contato",
            placeholder: "Nome do contato",
            autocomplete: "name",
        },
        {
            key: "relationship",
            name: "emergency_contact_relationship[]",
            label: "Vínculo",
            placeholder: "Vínculo",
        },
        {
            key: "phone",
            name: "emergency_contact_phone[]",
            label: "Telefone de emergência",
            placeholder: "Telefone",
            type: "tel",
            mask: "br",
            autocomplete: "tel",
        },
    ],
});
