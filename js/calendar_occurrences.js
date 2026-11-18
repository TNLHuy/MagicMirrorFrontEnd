const ical = require("node-ical");

/** Expand actual calendar occurrences within a bounded date range. */
function getCalendarOccurrences (content, from, to) {
	const calendar = ical.sync.parseICS(content);
	const occurrences = [];
	for (const event of Object.values(calendar)) {
		if (event.type !== "VEVENT" || !event.start || event.status === "CANCELLED") continue;
		for (const instance of ical.expandRecurringEvent(event, { from, to })) {
			if (instance.event.status === "CANCELLED") continue;
			occurrences.push({
				id: `${event.uid}:${instance.start.toISOString()}`,
				title: instance.summary || "Lịch trình",
				start: instance.start.toISOString(),
				end: instance.end.toISOString(),
				isAllDay: instance.isFullDay,
				location: instance.event.location || "",
				description: instance.event.description || ""
			});
		}
	}
	return occurrences.sort((a, b) => new Date(a.start) - new Date(b.start));
}

module.exports = { getCalendarOccurrences };
