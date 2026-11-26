/**
 * Installation wizard entry point.
 * Initializes the Bitrix24 SDK and waits for server-side installation.
 */

document.addEventListener("DOMContentLoaded", function () {
    const statusElement = document.getElementById("installation-status");

    // Stop initialization if the status element is missing.
    if (!statusElement) {
        console.error("Installation status element was not found.");
        return;
    }

    // Check that the Bitrix24 SDK is available.
    if (typeof BX24 === "undefined" || !BX24) {
        statusElement.textContent =
            "Не удалось загрузить библиотеку Bitrix24. Обновите страницу.";
        return;
    }

    // Pause execution between installation status checks.
    function sleep(milliseconds) {
        return new Promise(function (resolve) {
            setTimeout(resolve, milliseconds);
        });
    }

    // Wait until the backend confirms that installation is complete.
    async function waitForInstallation(memberId) {
        const timeout = 60_000;
        const deadline = Date.now() + timeout;
        let delay = 1_000;

        // Build the status endpoint using the current application path.
        const statusUrl = new URL(window.location.href);
        statusUrl.pathname = statusUrl.pathname.replace(
            /\/install\/?$/,
            "/install/status"
        );
        statusUrl.search = "";
        statusUrl.searchParams.set("member_id", memberId);

        statusElement.textContent =
            "Регистрация приложения на портале Bitrix24...";

        while (Date.now() < deadline) {
            try {
                // Request the current installation status from the backend.
                const response = await fetch(statusUrl, {
                    method: "GET",
                    headers: {
                        Accept: "application/json",
                    },
                    cache: "no-store",
                });

                if (!response.ok) {
                    throw new Error(
                        "Installation status request failed: " +
                        response.status
                    );
                }

                const result = await response.json();

                // Complete installation only after backend confirmation.
                if (result.ready === true) {
                    if (typeof BX24.installFinish !== "function") {
                        throw new Error(
                            "BX24.installFinish is not available."
                        );
                    }

                    statusElement.textContent =
                        "Установка завершена. Завершаем подключение...";

                    BX24.installFinish();
                    return;
                }
            } catch (error) {
                // Retry temporary network and server errors until timeout.
                console.warn(
                    "Installation status check failed. Retrying..."
                );
            }

            await sleep(delay);
            delay = Math.min(delay + 1_000, 5_000);
        }

        // Do not finish installation if the backend did not confirm readiness.
        statusElement.textContent =
            "Не удалось завершить установку за отведённое время. " +
            "Обновите страницу или попробуйте установить приложение ещё раз.";
    }

    statusElement.textContent = "Подключение к порталу Bitrix24...";

    try {
        // Wait until the SDK has received portal data.
        BX24.init(function () {
            try {
                // Retrieve authorization data only after SDK initialization.
                const authInfo = BX24.getAuth();

                // The installation cannot continue without a portal identifier.
                if (!authInfo || !authInfo.member_id) {
                    statusElement.textContent =
                        "Не удалось получить идентификатор портала. " +
                        "Обновите страницу.";
                    return;
                }

                // Use only the portal identifier; do not expose OAuth tokens.
                waitForInstallation(authInfo.member_id);
            } catch (error) {
                console.error("Installation initialization failed.", error);
                statusElement.textContent =
                    "Ошибка инициализации установки. Обновите страницу.";
            }
        });
    } catch (error) {
        console.error("Bitrix24 initialization failed.", error);
        statusElement.textContent =
            "Ошибка инициализации Bitrix24. Обновите страницу.";
    }
});
