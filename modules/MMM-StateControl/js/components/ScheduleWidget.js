/**
 * ====================================================================
 *   SCHEDULE WIDGET (AGENDA / TIMETABLE WIDGET AT BOTTOM_RIGHT)
 *   Hiển thị lịch trình / lịch học / thời khóa biểu ở góc dưới bên phải
 *   màn hình (phía trên thanh bottom_bar) khi người dùng hỏi lịch hôm nay
 *   hoặc các ngày khác.
 * ====================================================================
 */
class ScheduleWidget {
    constructor() {
        this.widgetEl = null;
        this.titleEl = null;
        this.countBadgeEl = null;
        this.listContainer = null;
        this._hideTimer = null;
    }

    createDom() {
        const widget = document.createElement("div");
        widget.id = "nlu-schedule-widget";
        widget.className = "nlu-schedule-widget";
        widget.innerHTML = `
            <div class="schedule-header">
                <div class="schedule-header-left">
                    <span class="schedule-icon">📅</span>
                    <span class="schedule-title" id="nlu-schedule-date-title">Lịch trình</span>
                </div>
                <span class="schedule-badge-count" id="nlu-schedule-count" style="display:none;">0 lịch học</span>
            </div>
            <div class="schedule-list" id="nlu-schedule-list"></div>
        `;
        return widget;
    }

    bindDom() {
        this.widgetEl = document.getElementById("nlu-schedule-widget");
        this.titleEl = document.getElementById("nlu-schedule-date-title");
        this.countBadgeEl = document.getElementById("nlu-schedule-count");
        this.listContainer = document.getElementById("nlu-schedule-list");
    }

    update(data) {
        if (!this.widgetEl) return;

        // Xóa timer ẩn cũ nếu đang chạy
        if (this._hideTimer) {
            clearTimeout(this._hideTimer);
            this._hideTimer = null;
        }

        // 1. Cập nhật tiêu đề ngày (ví dụ: "Hôm nay • Thứ năm (08/10)")
        if (this.titleEl) {
            this.titleEl.textContent = data.date_label || "Lịch trình";
        }

        // 2. Cập nhật danh sách sự kiện / môn học
        const events = Array.isArray(data.events) ? data.events : [];
        if (this.listContainer) {
            this.listContainer.innerHTML = "";

            if (events.length > 0) {
                if (this.countBadgeEl) {
                    this.countBadgeEl.textContent = `${events.length} lịch học`;
                    this.countBadgeEl.style.display = "inline-block";
                }

                events.forEach((ev) => {
                    const item = document.createElement("div");
                    item.className = "schedule-item";

                    const locHtml = ev.location
                        ? `<span class="schedule-item-loc">📍 ${ev.location}</span>`
                        : "";
                    const codeHtml = ev.code
                        ? `<span class="schedule-code">${ev.code}</span>`
                        : "";
                    const noteHtml = ev.note
                        ? `<span class="schedule-note">${ev.note}</span>`
                        : "";

                    item.innerHTML = `
                        <div class="schedule-item-top">
                            <div class="schedule-time-group">
                                <span class="schedule-time">⏰ ${ev.time || "Cả ngày"}</span>
                                ${noteHtml}
                            </div>
                            ${codeHtml}
                        </div>
                        <div class="schedule-item-title">${ev.title || "Sự kiện"}</div>
                        ${locHtml ? `<div class="schedule-item-meta">${locHtml}</div>` : ""}
                    `;
                    this.listContainer.appendChild(item);
                });
            } else {
                // Không có lịch trong ngày
                if (this.countBadgeEl) {
                    this.countBadgeEl.style.display = "none";
                }

                const emptyState = document.createElement("div");
                emptyState.className = "schedule-empty-state";
                emptyState.innerHTML = `
                    <span class="schedule-empty-icon">✨</span>
                    <span class="schedule-empty-text">Không có lịch học nào trong ngày này</span>
                `;
                this.listContainer.appendChild(emptyState);
            }
        }

        // 3. Hiển thị widget trượt lên mượt mà
        this.widgetEl.classList.add("visible");

        // 4. Tự động ẩn widget sau 14 giây để giữ màn hình thoáng đãng
        this._hideTimer = setTimeout(() => {
            this.hide();
        }, 14000);
    }

    hide() {
        if (this._hideTimer) {
            clearTimeout(this._hideTimer);
            this._hideTimer = null;
        }
        if (this.widgetEl) {
            this.widgetEl.classList.remove("visible");
        }
    }
}

if (typeof window !== "undefined") {
    window.ScheduleWidget = ScheduleWidget;
}
