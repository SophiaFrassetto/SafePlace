"use strict";

const printCardButton = document.querySelector("[data-print-card-button]");

if (printCardButton instanceof HTMLButtonElement) {
    printCardButton.addEventListener("click", () => window.print());
}
