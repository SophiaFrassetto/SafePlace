"use strict";

const diarySheet = document.querySelector("[data-diary-sheet]");
const diaryEntryForm = document.querySelector("[data-diary-entry-form]");
const diarySaveStatus = document.querySelector("[data-diary-save-status]");
let pageTransitionInProgress = false;
let allowNavigationSubmit = false;

const finishPageTransition = (button, form) => {
    if (pageTransitionInProgress) {
        return;
    }
    pageTransitionInProgress = true;

    const direction = button.matches("[data-page-next]") ? "next" : "previous";
    const turnClass = `is-turning-${direction}`;
    const animationName = `diary-page-roll-${direction}`;
    const submitNavigation = () => {
        if (!form.isConnected) {
            return;
        }
        allowNavigationSubmit = true;
        form.requestSubmit(button);
    };

    if (
        !(diarySheet instanceof HTMLElement) ||
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
        submitNavigation();
        return;
    }

    let fallbackTimer = 0;
    const finishTurn = (event) => {
        if (
            event.target !== diarySheet ||
            event.animationName !== animationName
        ) {
            return;
        }

        diarySheet.removeEventListener("animationend", finishTurn);
        window.clearTimeout(fallbackTimer);
        submitNavigation();
    };
    diarySheet.addEventListener("animationend", finishTurn);
    fallbackTimer = window.setTimeout(() => {
        diarySheet.removeEventListener("animationend", finishTurn);
        submitNavigation();
    }, 1400);
    requestAnimationFrame(() => {
        diarySheet.classList.remove(
            "is-turning-next",
            "is-turning-previous",
        );
        void diarySheet.offsetWidth;
        diarySheet.classList.add(turnClass);
    });
};

document.querySelectorAll("[data-page-transition-form]").forEach((form) => {
    if (!(form instanceof HTMLFormElement)) {
        return;
    }
    form.addEventListener("submit", (event) => {
        if (allowNavigationSubmit) {
            allowNavigationSubmit = false;
            return;
        }
        const submitter = event.submitter;
        if (
            !(submitter instanceof HTMLButtonElement) ||
            submitter.disabled
        ) {
            return;
        }
        event.preventDefault();
        finishPageTransition(submitter, form);
    });
});

if (diaryEntryForm instanceof HTMLFormElement) {
    const navigationButtons = Array.from(
        document.querySelectorAll("[data-page-previous], [data-page-next]"),
    ).filter((button) => button instanceof HTMLButtonElement);
    const markPageAsUnsaved = () => {
        navigationButtons.forEach((button) => {
            button.disabled = true;
        });
        if (diarySaveStatus instanceof HTMLElement) {
            diarySaveStatus.textContent =
                "Você tem alterações sem salvar. Salve a página antes de navegar.";
        }
    };

    diaryEntryForm.addEventListener("input", markPageAsUnsaved);
    diaryEntryForm.addEventListener("change", markPageAsUnsaved);
}

const deleteDialog = document.querySelector("[data-delete-dialog]");
const deleteDialogOpenButton = document.querySelector(
    "[data-delete-dialog-open]",
);
const deleteDialogCloseButton = document.querySelector(
    "[data-delete-dialog-close]",
);

if (
    deleteDialog instanceof HTMLDialogElement &&
    deleteDialogOpenButton instanceof HTMLButtonElement
) {
    deleteDialogOpenButton.addEventListener("click", () => {
        deleteDialog.showModal();
    });

    deleteDialogCloseButton?.addEventListener("click", () => {
        deleteDialog.close();
    });
}
