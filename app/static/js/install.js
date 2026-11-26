/**
 * Installation wizard entry point.
 *
 * The installation is not completed here yet.
 * We will add the server readiness check before calling BX24.installFinish().
 */

document.addEventListener("DOMContentLoaded", function () {
    const statusElement = document.getElementById("installation-status");

    if (!statusElement) {
        console.error("Installation status element was not found.");
        return;
    }

    statusElement.textContent = "Инициализация приложения...";
});