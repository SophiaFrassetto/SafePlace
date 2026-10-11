"use strict";

const formatBrazilianPhoneNumber = (value) => {
    const digits = value.replace(/\D/g, "");
    const hasCountryCode =
        value.trimStart().startsWith("+55") ||
        (digits.startsWith("55") && digits.length > 11);
    const nationalNumber = (hasCountryCode ? digits.slice(2) : digits).slice(
        0,
        11,
    );
    if (!nationalNumber) {
        return hasCountryCode ? "+55" : "";
    }

    const areaCode = nationalNumber.slice(0, 2);
    const subscriberNumber = nationalNumber.slice(2);
    const prefixLength = subscriberNumber.length > 8 ? 5 : 4;
    const prefix = subscriberNumber.slice(0, prefixLength);
    const suffix = subscriberNumber.slice(prefixLength);
    const formattedNumber =
        `(${areaCode}${nationalNumber.length > 1 ? ") " : ""}` +
        prefix +
        (suffix ? `-${suffix}` : "");
    return hasCountryCode ? `+55 ${formattedNumber}` : formattedNumber;
};

const positionAfterPhoneDigits = (value, digitsBeforeCursor) => {
    if (digitsBeforeCursor === 0) {
        return value.startsWith("+55 ") ? 4 : 0;
    }

    let digitsFound = 0;
    for (let index = 0; index < value.length; index += 1) {
        if (/\d/.test(value[index])) {
            digitsFound += 1;
            if (digitsFound === digitsBeforeCursor) {
                return index + 1;
            }
        }
    }
    return value.length;
};

for (const phoneInput of document.querySelectorAll("[data-phone-mask='br']")) {
    if (phoneInput instanceof HTMLInputElement) {
        phoneInput.value = formatBrazilianPhoneNumber(phoneInput.value);
    }
}

document.addEventListener("input", (event) => {
    if (
        !(event.target instanceof HTMLInputElement) ||
        event.target.dataset.phoneMask !== "br"
    ) {
        return;
    }

    const input = event.target;
    const selectionStart = input.selectionStart ?? input.value.length;
    const digitsBeforeCursor = input.value
        .slice(0, selectionStart)
        .replace(/\D/g, "").length;
    input.value = formatBrazilianPhoneNumber(input.value);
    const caretPosition = positionAfterPhoneDigits(
        input.value,
        digitsBeforeCursor,
    );
    input.setSelectionRange(caretPosition, caretPosition);
});

for (const toast of document.querySelectorAll("[data-toast]")) {
    if (!(toast instanceof HTMLElement)) {
        continue;
    }

    const dismissButton = toast.querySelector("[data-toast-dismiss]");
    const dismissToast = () => toast.remove();

    if (dismissButton instanceof HTMLButtonElement) {
        dismissButton.addEventListener("click", dismissToast);
    }

    window.setTimeout(dismissToast, 8000);
}

const menuToggle = document.querySelector("[data-menu-toggle]");
const mainMenu = document.querySelector("[data-main-menu]");
const menuBackdrop = document.querySelector("[data-menu-backdrop]");
const notificationToggle = document.querySelector(
    "[data-notification-toggle]",
);
const notificationPanel = document.querySelector(
    "[data-notification-panel]",
);
const profileMenu = document.querySelector(".app-profile-menu");

if (
    menuToggle instanceof HTMLButtonElement &&
    mainMenu instanceof HTMLElement &&
    menuBackdrop instanceof HTMLButtonElement
) {
    const setMenuOpen = (isOpen) => {
        mainMenu.hidden = !isOpen;
        menuBackdrop.hidden = !isOpen;
        menuToggle.setAttribute("aria-expanded", String(isOpen));
        menuToggle.setAttribute(
            "aria-label",
            isOpen ? "Fechar menu" : "Abrir menu",
        );
    };

    menuToggle.addEventListener("click", () => setMenuOpen(mainMenu.hidden));
    menuBackdrop.addEventListener("click", () => setMenuOpen(false));
    mainMenu.addEventListener("click", (event) => {
        if (event.target instanceof Element && event.target.closest("a")) {
            setMenuOpen(false);
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !mainMenu.hidden) {
            setMenuOpen(false);
            menuToggle.focus();
        }
    });
}

if (
    notificationToggle instanceof HTMLButtonElement &&
    notificationPanel instanceof HTMLElement
) {
    const setNotificationsOpen = (isOpen) => {
        notificationPanel.hidden = !isOpen;
        notificationToggle.setAttribute("aria-expanded", String(isOpen));
    };

    notificationToggle.addEventListener("click", () => {
        setNotificationsOpen(notificationPanel.hidden);
    });
    document.addEventListener("click", (event) => {
        if (
            event.target instanceof Node &&
            !notificationPanel.contains(event.target) &&
            !notificationToggle.contains(event.target)
        ) {
            setNotificationsOpen(false);
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !notificationPanel.hidden) {
            setNotificationsOpen(false);
            notificationToggle.focus();
        }
    });
}

if (profileMenu instanceof HTMLDetailsElement) {
    document.addEventListener("click", (event) => {
        if (event.target instanceof Node && !profileMenu.contains(event.target)) {
            profileMenu.open = false;
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && profileMenu.open) {
            profileMenu.open = false;
            profileMenu.querySelector("summary")?.focus();
        }
    });
}
