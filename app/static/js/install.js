/**
 * Installation wizard entry point.
 * Registers application event handlers and completes installation.
 */

document.addEventListener("DOMContentLoaded", function () {
    const statusElement = document.getElementById("installation-status");

    if (!statusElement) {
        console.error("Installation status element was not found.");
        return;
    }

    if (typeof BX24 === "undefined" || !BX24) {
        statusElement.textContent =
            "Не удалось загрузить библиотеку Bitrix24. Обновите страницу.";
        return;
    }

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
        const handlers = await callBitrixMethod("event.get", {});

        const alreadyRegistered = handlers.some(function (handler) {
            return (
                handler.event === eventName &&
                handler.handler === handlerUrl
            );
        });

        if (alreadyRegistered) {
            return;
        }

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

    // Handle the first application launch and complete installation.
    BX24.install(async function () {
        try {
            statusElement.textContent =
                "Регистрация обработчиков событий Bitrix24...";

            const handlerUrl = getEventHandlerUrl();

            await ensureEventHandler("ONAPPINSTALL", handlerUrl);
            await ensureEventHandler("ONAPPUNINSTALL", handlerUrl);

            if (installationFinished) {
                return;
            }

            installationFinished = true;

            statusElement.textContent =
                "Обработчики зарегистрированы. Завершение установки...";

            BX24.installFinish();
        } catch (error) {
            console.error("Application installation failed.", error);

            statusElement.textContent =
                "Не удалось завершить установку приложения. " +
                "Проверьте подключение и попробуйте обновить страницу.";
        }
    });
});
