/**
 * ====================================================================
 *   SMART HOME WIDGET (IOT HOME AUTOMATION STATUS)
 *   Widget trạng thái thiết bị nhà thông minh tại góc dưới bên phải (BOTTOM_RIGHT)
 *   - Danh sách thiết bị (Đèn, máy lạnh, rèm cửa, khóa thông minh)
 *   - Huy hiệu trạng thái động (ON, OFF, 24°C, LOCKED)
 * ====================================================================
 */
class SmartHomeWidget {
    constructor() {
        this.widgetEl = null;
        this.listContainer = null;
    }

    createDom() {
        const widget = document.createElement("div");
        widget.id = "nlu-smarthome-widget";
        widget.className = "nlu-smarthome-widget";
        widget.innerHTML = `
            <div class="smarthome-header">🏠 Nhà Thông Minh</div>
            <div class="smarthome-list" id="nlu-smarthome-list">
                <div class="smarthome-item">
                    <span class="device-name">Đèn phòng</span>
                    <span class="device-status status-on">ON</span>
                </div>
                <div class="smarthome-item">
                    <span class="device-name">Máy lạnh</span>
                    <span class="device-status status-on">24°C</span>
                </div>
            </div>
        `;
        return widget;
    }

    bindDom() {
        this.widgetEl = document.getElementById("nlu-smarthome-widget");
        this.listContainer = document.getElementById("nlu-smarthome-list");
    }

    update(data) {
        if (!this.widgetEl) return;

        if (this.listContainer && data.devices) {
            this.listContainer.innerHTML = "";
            data.devices.forEach((dev) => {
                const item = document.createElement("div");
                item.className = "smarthome-item";
                const isOnline = dev.status && (dev.status === "ON" || dev.status === "LOCKED" || dev.status.includes("°"));
                item.innerHTML = `
                    <span class="device-name">${dev.name}</span>
                    <span class="device-status ${isOnline ? 'status-on' : 'status-off'}">${dev.status}</span>
                `;
                this.listContainer.appendChild(item);
            });
        }

        this.widgetEl.classList.add("visible");
    }

    hide() {
        if (this.widgetEl) {
            this.widgetEl.classList.remove("visible");
        }
    }
}

if (typeof window !== "undefined") {
    window.SmartHomeWidget = SmartHomeWidget;
}
