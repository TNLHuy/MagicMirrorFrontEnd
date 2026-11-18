const { test } = require("node:test");
const assert = require("node:assert/strict");
const { getCalendarOccurrences } = require("../js/calendar_occurrences");

const from = new Date("2026-11-15T17:00:00Z");
const to = new Date("2026-12-15T16:59:59Z");
const calendar = (...events) => `BEGIN:VCALENDAR\r\nVERSION:2.0\r\n${events.join("\r\n")}\r\nEND:VCALENDAR`;
const event = (uid, start, extra = "") => `BEGIN:VEVENT\r\nUID:${uid}\r\nDTSTART;TZID=Asia/Ho_Chi_Minh:${start}\r\nDURATION:PT1H\r\nSUMMARY:${uid}\r\n${extra}\r\nEND:VEVENT`;

test("weekly classes use current occurrences, timezone, ordering and UNTIL", () => {
	const result = getCalendarOccurrences(calendar(
		event("friday", "20260911T073000", "RRULE:FREQ=WEEKLY;UNTIL=20261129T075959Z"),
		event("monday-late", "20260907T130000", "RRULE:FREQ=WEEKLY;UNTIL=20261129T075959Z"),
		event("monday", "20260907T073000", "RRULE:FREQ=WEEKLY;UNTIL=20261129T075959Z")
	), from, to);
	assert.equal(result.length, 6);
	assert.equal(result[0].start, "2026-11-16T00:30:00.000Z");
	assert.equal(result[1].title, "monday-late");
	assert.equal(result[2].start, "2026-11-20T00:30:00.000Z");
	assert.ok(result.every((item, i) => !i || item.start >= result[i - 1].start));
});

test("expired recurrences and past single events disappear", () => {
	assert.deepEqual(getCalendarOccurrences(calendar(
		event("11 TIN", "20210918T063000", "RRULE:FREQ=MONTHLY;UNTIL=20230516T233000Z;INTERVAL=2;BYMONTHDAY=18"),
		event("10 TIN", "20211118T063000")
	), from, to), []);
});

test("alternating weeks respect exceptions, changed classes and cancellation", () => {
	const result = getCalendarOccurrences(calendar(
		event("lab", "20261002T130000", "RRULE:FREQ=WEEKLY;INTERVAL=2;UNTIL=20261213T075959Z\r\nEXDATE;TZID=Asia/Ho_Chi_Minh:20261127T130000"),
		event("lab", "20261212T140000", "RECURRENCE-ID;TZID=Asia/Ho_Chi_Minh:20261211T130000"),
		event("cancelled", "20261117T073000", "STATUS:CANCELLED")
	), from, to);
	assert.equal(result.length, 1);
	assert.equal(result[0].start, "2026-12-12T07:00:00.000Z");
	assert.equal(result[0].end, "2026-12-12T08:00:00.000Z");
});

test("includes today's and future single events, with distinct occurrence IDs", () => {
	const result = getCalendarOccurrences(calendar(
		event("future", "20261117T073000"),
		event("today", "20261116T073000")
	), from, to);
	assert.deepEqual(result.map((item) => item.title), ["today", "future"]);
	assert.equal(new Set(result.map((item) => item.id)).size, 2);
});
