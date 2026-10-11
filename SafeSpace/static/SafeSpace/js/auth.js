"use strict";

const passwordInput = document.querySelector("[data-password-input]");

if (passwordInput instanceof HTMLInputElement) {
    const confirmationInput = document.querySelector(
        "[data-password-confirmation]",
    );
    const confirmationHint = document.querySelector(
        "[data-password-confirmation-hint]",
    );

    if (
        confirmationInput instanceof HTMLInputElement &&
        confirmationHint instanceof HTMLElement
    ) {
        const validatePasswordConfirmation = () => {
            const passwordsMismatch =
                confirmationInput.value.length > 0 &&
                confirmationInput.value !== passwordInput.value;
            const validationMessage = passwordsMismatch
                ? "As senhas não coincidem."
                : "";

            confirmationInput.setCustomValidity(validationMessage);
            confirmationInput.setAttribute(
                "aria-invalid",
                String(passwordsMismatch),
            );
            confirmationHint.textContent = validationMessage;
        };

        passwordInput.addEventListener("input", validatePasswordConfirmation);
        confirmationInput.addEventListener(
            "input",
            validatePasswordConfirmation,
        );
        confirmationInput.form?.addEventListener("submit", (event) => {
            validatePasswordConfirmation();

            if (!confirmationInput.validity.valid) {
                event.preventDefault();
                confirmationInput.reportValidity();
            }
        });
    }

    const strengthMeter = document.querySelector("[data-strength-meter]");
    const strengthFill = document.querySelector("[data-strength-fill]");
    const strengthLabel = document.querySelector("[data-strength-label]");
    const passwordRules = Array.from(
        document.querySelectorAll("[data-password-rule]"),
    );

    if (
        strengthMeter instanceof HTMLElement &&
        strengthFill instanceof HTMLElement &&
        strengthLabel instanceof HTMLElement
    ) {
        const updatePasswordStrength = () => {
            const password = passwordInput.value;
            const checks = {
                length: password.length >= 8,
                uppercase: /[A-Z]/.test(password),
                lowercase: /[a-z]/.test(password),
                special: /[^A-Za-z0-9\s]/.test(password),
            };
            const score = Object.values(checks).filter(Boolean).length;
            const percentage = score * 25;
            const strength = ["", "weak", "medium", "good", "strong"][score];
            const labels = [
                "ainda não informada",
                "fraca",
                "razoável",
                "boa",
                "forte",
            ];

            strengthMeter.setAttribute("aria-valuenow", String(percentage));
            strengthFill.style.width = `${percentage}%`;
            strengthFill.dataset.strength = strength;
            strengthLabel.textContent = `Nível da senha: ${labels[score]}`;

            for (const rule of passwordRules) {
                const ruleName = rule.dataset.passwordRule;

                if (ruleName && Object.prototype.hasOwnProperty.call(checks, ruleName)) {
                    rule.dataset.valid = String(checks[ruleName]);
                }
            }
        };

        passwordInput.addEventListener("input", updatePasswordStrength);
        updatePasswordStrength();
    }
}
