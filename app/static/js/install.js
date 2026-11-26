/**
 * Installation wizard entry point.
 * Registers application event handlers and completes installation.
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

    // Prevent multiple installation completion attempts.
    let installationFinished = false;

    // Build the absolute URL of the application event handler.
    function getEventHandlerUrl() {
        const applicationPath = window.location.pathname.replace(
            /\/install\/?$/,
            ""
        );

        return new URL(
            applicationPath + "/events/bitrix24",
            window.location.origin
        ).toString();
    }

    // Call a Bitrix24 REST method and return its result as a Promise.
    function callBitrixMethod(method, params) {
        return new Promise(function (resolve, reject) {
            BX24.callMethod(method, params, function (result) {
                // Reject the promise if Bitrix24 returned an API error.
                if (result.error()) {
                    reject(
                        new Error(
                            method + ": " + result.error_description()
                        )
                    );
                    return;
                }

                resolve(result.data());
            });
        });
    }

    // Register an event handler only if it does not exist yet.
    async function ensureEventHandler(eventName, handlerUrl) {
        // Retrieve handlers already registered by this application.
        const handlers = await callBitrixMethod("event.get", {});

        // Check whether the required event and URL are already registered.
        const alreadyRegistered = handlers.some(function (handler) {
            return (
                handler.event === eventName &&
                handler.handler === handlerUrl
            );
        });

        if (alreadyRegistered) {
            return;
        }

        // Register the missing event handler.
        const registered = await callBitrixMethod("event.bind", {
            event: eventName,
            handler: handlerUrl,
        });

        if (registered !== true) {
            throw new Error(
                "Bitrix24 did not confirm registration of " + eventName
            );
        }
    }

    // Initialize the SDK and perform the installation sequence.
    BX24.init(async function () {
        try {
            statusElement.textContent =
                "Регистрация обработчиков событий Bitrix24...";

            const handlerUrl = getEventHandlerUrl();

            // Register the installation event handler first.
            await ensureEventHandler("ONAPPINSTALL", handlerUrl);

            // Register the application removal event handler.
            await ensureEventHandler("ONAPPUNINSTALL", handlerUrl);

            // Do not finish installation more than once.
            if (installationFinished) {
                return;
            }

            installationFinished = true;

            statusElement.textContent =
                "Обработчики зарегистрированы. Завершение установки...";

            // Notify Bitrix24 that the installation wizard has completed.
            BX24.installFinish();
        } catch (error) {
            console.error("Application installation failed.", error);

            statusElement.textContent =
                "Не удалось завершить установку приложения. " +
                "Проверьте подключение и попробуйте обновить страницу.";
        }
    });
});
