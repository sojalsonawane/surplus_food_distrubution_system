/**
 * Surplus Food Distribution System
 * Client-side validation, UI utilities, and alert handling.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Enable Bootstrap form validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // 2. Auto-dismiss flash alerts after 6 seconds
    const flashAlerts = document.querySelectorAll('.alert-dismissible');
    flashAlerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 6000);
    });

    // 3. Confirm action dialogs (e.g. for cancellations/deletions)
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            const msg = btn.getAttribute('data-confirm') || 'Are you sure you want to perform this action?';
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });
});

/**
 * Validates Indian 10-digit mobile numbers starting with 6, 7, 8, or 9.
 */
function isValidIndianMobile(mobile) {
    const regex = /^[6-9]\d{9}$/;
    return regex.test(mobile.trim());
}

/**
 * Validates 6-digit Indian PIN code.
 */
function isValidPincode(pincode) {
    const regex = /^[1-9]\d{5}$/;
    return regex.test(pincode.trim());
}

/**
 * Validates password strength:
 * Minimum 8 characters, at least 1 uppercase, 1 lowercase, 1 number, 1 special char.
 */
function isStrongPassword(password) {
    const hasMinLen = password.length >= 8;
    const hasUpper = /[A-Z]/.test(password);
    const hasLower = /[a-z]/.test(password);
    const hasDigit = /\d/.test(password);
    const hasSpecial = /[@$!%*?&#^()_+={}\[\]:;"'<>,.?\/\\|`~-]/.test(password);

    return {
        isValid: hasMinLen && hasUpper && hasLower && hasDigit && hasSpecial,
        hasMinLen: hasMinLen,
        hasUpper: hasUpper,
        hasLower: hasLower,
        hasDigit: hasDigit,
        hasSpecial: hasSpecial
    };
}

/**
 * Validates food donation dates.
 * Best before must be later than preparation date and later than current time.
 */
function validateFoodDates(prepDateStr, bestBeforeStr) {
    const prepDate = new Date(prepDateStr);
    const bestBefore = new Date(bestBeforeStr);
    const now = new Date();

    if (isNaN(prepDate.getTime()) || isNaN(bestBefore.getTime())) {
        return { isValid: false, message: 'Invalid date/time format.' };
    }

    if (bestBefore <= prepDate) {
        return { isValid: false, message: 'Best-before date and time must be later than preparation date and time.' };
    }

    if (bestBefore <= now) {
        return { isValid: false, message: 'Best-before date and time must be in the future. Expired food cannot be accepted.' };
    }

    return { isValid: true, message: 'Dates are valid.' };
}

/**
 * Validates file upload size and MIME/extension.
 * Default max 5MB (5242880 bytes).
 */
function validateFileUpload(fileInput, allowedTypes = ['image/jpeg', 'image/png', 'application/pdf'], maxBytes = 5242880) {
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        return { isValid: true }; // optional file
    }
    const file = fileInput.files[0];
    if (file.size > maxBytes) {
        return { isValid: false, message: `File size exceeds limit of ${(maxBytes / (1024 * 1024)).toFixed(0)}MB.` };
    }
    if (!allowedTypes.includes(file.type)) {
        return { isValid: false, message: 'Selected file type is not allowed. Only JPG, PNG, and PDF are accepted.' };
    }
    return { isValid: true };
}
