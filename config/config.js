/* Config Sample
 *
 * For more information on how you can configure this file
 * see https://docs.magicmirror.builders/configuration/introduction.html
 * and https://docs.magicmirror.builders/modules/configuration.html
 *
 * You can use environment variables using a `config.js.template` file instead of `config.js`
 * which will be converted to `config.js` while starting. For more information
 * see https://docs.magicmirror.builders/configuration/introduction.html#enviromnent-variables
 */
const fs = require("node:fs");
const path = require("node:path");

// Tự động nạp danh sách lịch Google Calendar do người dùng cấu hình từ Web Hub
let dynamicCalendars = [
	{
		fetchInterval: 7 * 24 * 60 * 60 * 1000,
		symbol: "calendar-check",
		url: "https://calendar.google.com/calendar/ical/vi.vietnamese%23holiday%40group.v.calendar.google.com/public/basic.ics"
	}
];

try {
	const calJsonPath = path.resolve(__dirname + "/../data/calendars.json");
	if (fs.existsSync(calJsonPath)) {
		const raw = JSON.parse(fs.readFileSync(calJsonPath, "utf-8"));
		if (Array.isArray(raw)) {
			const active = raw.filter((c) => c.enabled !== false && c.url && c.url.trim());
			if (active.length > 0) {
				dynamicCalendars = active.map((c) => ({
					fetchInterval: 15 * 60 * 1000,
					symbol: "calendar-check",
					url: c.url.trim(),
					name: c.name || "Lịch cá nhân",
					color: c.color
				}));
			}
		}
	}
} catch (e) {
	// Fallback giữ nguyên
}

let config = {
	address: "0.0.0.0",	// Cho phép truy cập từ cả máy tính và điện thoại/máy tính bảng qua mạng LAN/Hotspot
	port: 8080,
	basePath: "/",	// The URL path where MagicMirror² is hosted. If you are using a Reverse proxy
									// you must set the sub path here. basePath must end with a /
	ipWhitelist: [],	// [] cho phép mọi thiết bị trong mạng nội bộ truy cập Web Hub & Mirror
	cors: "allowWhitelist",
	corsDomainWhitelist: ["calendar.google.com"],

	useHttps: false,			// Support HTTPS or not, default "false" will use HTTP
	httpsPrivateKey: "",	// HTTPS private key path, only require when useHttps is true
	httpsCertificate: "",	// HTTPS Certificate path, only require when useHttps is true

	language: "vi",
	locale: "vi-VN",   // this variable is provided as a consistent location
			   // it is currently only used by 3rd party modules. no MagicMirror code uses this value
			   // as we have no usage, we  have no constraints on what this field holds
			   // see https://en.wikipedia.org/wiki/Locale_(computer_software) for the possibilities

	logLevel: ["INFO", "LOG", "WARN", "ERROR"], // Add "DEBUG" for even more logging
	timeFormat: 24,
	units: "metric",
	electronSwitches: ["--autoplay-policy=no-user-gesture-required"],

	modules: [
		{
            module: "MMM-StateControl",
            position: "middle_center",
            config: {
                websocketUrl: "ws://localhost:8085",
                style: "siri-wave",          // Phong cách animation AI: "siri-wave" | "google-wave" | "shader-ring"
                autoHideDelay: 9000,         // Thời gian tự động ẩn bong bóng chat (ms) sau khi AI trả lời xong
                enableTypewriter: true,      // Bật hiệu ứng gõ chữ (typewriter effect) trong bong bóng chat
                enableChime: true,           // Bật âm thanh wake chime khi AI thức dậy
                assistantName: "Trợ lý AI"   // Tên hiển thị trên đầu bong bóng chat
            }
        },
		{
			module: "alert",
		},
		{
			module: "updatenotification",
			position: "top_bar"
		},
		{
			module: "clock",
			position: "top_left",
			config: {
                timeFormat: 24,
                dateFormat: "dddd, [ngày] D MMMM, YYYY", // Định dạng ngày tháng kiểu Việt Nam
                timezone: "Asia/Ho_Chi_Minh"
            }
		},
		{
			module: "calendar",
			header: "Lịch trình",
			position: "bottom_left",
			config: {
				calendars: dynamicCalendars
			}
		},
		/* Compliments ẩn đi để nhường toàn bộ MIDDLE_CENTER cho khu vực hiển thị tương tác (Popup / Overlay) */
		/*{
			module: "compliments",
			position: "lower_third",
			config: {
                compliments: {
                    anytime: ["Chúc bạn một ngày tốt lành!"]
				}
			}
		},*/
		{
			module: "weather",
			position: "top_right",
			config: {
				weatherProvider: "openmeteo",
				type: "current",
				lat: 10.8231,
				lon: 106.6297,
				location: "TP. Hồ Chí Minh",
                locationLabel: "TP. Hồ Chí Minh"
			}
		},
		{
			module: "weather",
			position: "top_right",
			header: "Weather Forecast",
			config: {
				weatherProvider: "openmeteo",
				type: "forecast",
				lat: 10.8231,
				lon: 106.6297,
				location: "TP. Hồ Chí Minh",
                locationLabel: "TP. Hồ Chí Minh"
			}
		},
		/*{
			module: "newsfeed",
			position: "bottom_bar",
			config: {
				feeds: [
					{
						title: "New York Times",
						url: "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
					}
				],
				showSourceTitle: true,
				showPublishDate: true,
				broadcastNewsFeeds: true,
				broadcastNewsUpdates: true
			}
		},*/
	]
};

/*************** DO NOT EDIT THE LINE BELOW ***************/
if (typeof module !== "undefined") { module.exports = config; }
