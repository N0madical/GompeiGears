self.addEventListener("push", e => {
    const message = e.data.json()

    e.waitUntil(self.registration.showNotification(message.title, {
        body: message.body,
        icon: "/static/images/icon512.png"
    }));
});

self.addEventListener("notificationclick", e => {
    e.notification.close();

    e.waitUntil(
        clients
            .matchAll({
                type: "window",
            })
            .then((clientList) => {
                for (const client of clientList) {
                    if ("focus" in client) return client.focus();
                }
                if (clients.openWindow) return clients.openWindow("/");
            }),
    );
})