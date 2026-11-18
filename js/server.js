const fs = require("node:fs");
const http = require("node:http");
const https = require("node:https");
const path = require("node:path");
const express = require("express");
const helmet = require("helmet");
const socketio = require("socket.io");
const Log = require("logger");

const { ipAccessControl, socketIpAccessControl } = require("./ip_access_control");
const { getCalendarOccurrences } = require("./calendar_occurrences");

const vendor = require("./vendor");

const { getHtml, getVersion, getEnvVars, cors } = require("#server_functions");

/**
 * Server
 * @param {object} configObj The MM config full and redacted
 * @class
 */
function Server (configObj) {
	const config = configObj.fullConf;
	const app = express();
	const port = process.env.MM_PORT || config.port;
	const serverSockets = new Set();
	let server = null;

	/**
	 * Opens the server for incoming connections
	 * @returns {Promise} A promise that is resolved when the server listens to connections
	 */
	this.open = function () {
		return new Promise((resolve) => {
			if (config.useHttps) {
				const options = {
					key: fs.readFileSync(config.httpsPrivateKey),
					cert: fs.readFileSync(config.httpsCertificate)
				};
				server = https.Server(options, app);
			} else {
				server = http.Server(app);
			}
			const io = socketio(server, {
				allowRequest: socketIpAccessControl(config.ipWhitelist),
				cors: {
					origin: /.*$/,
					credentials: true
				},
				allowEIO3: true,
				pingInterval: 120000, // server → client ping every 2 mins
				pingTimeout: 120000 // wait up to 2 mins for client pong
			});

			server.on("connection", (socket) => {
				serverSockets.add(socket);
				socket.on("close", () => {
					serverSockets.delete(socket);
				});
			});

			Log.log(`Starting server on port ${port} ... `);

			// Add explicit error handling BEFORE calling listen so we can give user-friendly feedback
			server.once("error", (err) => {
				if (err && err.code === "EADDRINUSE") {
					const bindAddr = config.address || "localhost";
					const portInUseMessage = [
						"",
						"────────────────────────────────────────────────────────────────",
						` PORT IN USE: ${bindAddr}:${port}`,
						"",
						" Another process (most likely another MagicMirror instance)",
						" is already using this port.",
						"",
						" Stop the other process (free the port) or use a different port.",
						"────────────────────────────────────────────────────────────────"
					].join("\n");
					Log.error(portInUseMessage);
					return;
				}

				Log.error("Failed to start server:", err);
			});

			server.listen(port, config.address || "localhost");

			if (config.ipWhitelist instanceof Array && config.ipWhitelist.length === 0) {
				Log.warn("You're using a full whitelist configuration to allow for all IPs");
			}

			app.use(ipAccessControl(config.ipWhitelist));
			app.use(helmet(config.httpHeaders));
			app.use(express.json());
			app.use("/js", express.static(__dirname));

			if (config.hideConfigSecrets) {
				app.get("/config/config.env", (req, res) => {
					res.status(404).send("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<title>Error</title>\n</head>\n<body>\n<pre>Cannot GET /config/config.env</pre>\n</body>\n</html>");
				});
			}

			let directories = ["/config", "/css", "/favicon.svg", "/defaultmodules", "/modules", "/node_modules/animate.css", "/node_modules/@fontsource", "/node_modules/@fortawesome", "/node_modules/suncalc", "/translations", "/tests/configs", "/tests/mocks"];
			for (const value of Object.values(vendor)) {
				const dirArr = value.split("/");
				if (dirArr[0] === "node_modules") directories.push(`/${dirArr[0]}/${dirArr[1]}`);
			}
			const uniqDirs = [...new Set(directories)];

			for (const directory of uniqDirs) {
				app.use(directory, express.static(path.resolve(global.root_path + directory)));
			}

			// Mount Companion Web App (Vite React Hub) & Real Camera Captures
			const webDistPath = path.resolve(global.root_path + "/web/dist");
			if (fs.existsSync(webDistPath)) {
				app.use("/web", express.static(webDistPath));
				app.use("/hub", express.static(webDistPath));
				Log.info("Companion Web Hub is mounted at /web and /hub");
			}

			const screenShotPath = path.resolve(global.root_path + "/screen_shot");
			if (fs.existsSync(screenShotPath)) {
				app.use("/screen_shot", express.static(screenShotPath));
				app.use("/captures", express.static(screenShotPath));
				Log.info("Screen shots are mounted at /screen_shot and /captures");
			}

			// Real-time Dynamic Photo Gallery API (Synced with screen_shot directory)
			app.get("/api/photos", (req, res) => {
				const scPath = path.resolve(global.root_path + "/screen_shot");
				if (!fs.existsSync(scPath)) {
					return res.json([]);
				}
				try {
					const files = fs.readdirSync(scPath);
					const photos = files
						.filter((f) => f.startsWith("photo_") && (f.endsWith(".jpg") || f.endsWith(".png") || f.endsWith(".jpeg")))
						.sort()
						.reverse()
						.map((fileName) => {
							const filePath = path.join(scPath, fileName);
							const stats = fs.statSync(filePath);
							const base = path.parse(fileName).name;
							const qrName = `qr_${base}.png`;
							const hasQr = fs.existsSync(path.join(scPath, qrName));

							let formattedDate = new Date(stats.mtime).toLocaleString("vi-VN");
							const match = fileName.match(/photo_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
							if (match) {
								const [, y, m, d, h, min, s] = match;
								formattedDate = `${d}/${m}/${y} ${h}:${min}:${s}`;
							}

							return {
								id: base,
								fileName,
								url: `/screen_shot/${fileName}`,
								qrUrl: hasQr ? `/screen_shot/${qrName}` : null,
								formattedDate,
								size: `${Math.round(stats.size / 1024)} KB`,
								tag: "Webcam Selfie"
							};
						});
					res.json(photos);
				} catch (err) {
					res.status(500).json({ error: err.message });
				}
			});

			app.delete("/api/photos/:filename", (req, res) => {
				const scPath = path.resolve(global.root_path + "/screen_shot");
				const filename = path.basename(req.params.filename);
				const filePath = path.join(scPath, filename);
				const base = path.parse(filename).name;
				const qrPath = path.join(scPath, `qr_${base}.png`);

				let deleted = false;
				if (fs.existsSync(filePath)) {
					fs.unlinkSync(filePath);
					deleted = true;
				}
				if (fs.existsSync(qrPath)) {
					fs.unlinkSync(qrPath);
				}

				if (deleted) {
					return res.json({ success: true, message: `Deleted ${filename}` });
				}
				return res.status(404).json({ error: "File not found" });
			});

			// Dynamic Calendar API: sync calendars from Web Hub to Mirror & Backend
			const calendarsFilePath = path.resolve(global.root_path + "/data/calendars.json");

			app.get("/api/calendars", (req, res) => {
				try {
					if (fs.existsSync(calendarsFilePath)) {
						const raw = fs.readFileSync(calendarsFilePath, "utf8");
						return res.json(JSON.parse(raw));
					}
					return res.json([]);
				} catch (err) {
					res.status(500).json({ error: err.message });
				}
			});

			const handleSaveCalendars = (req, res) => {
				try {
					const data = req.body;
					let listToSave = [];
					if (Array.isArray(data)) {
						listToSave = data;
					} else if (data && Array.isArray(data.calendars)) {
						listToSave = data.calendars;
					}
					const dataDir = path.dirname(calendarsFilePath);
					if (!fs.existsSync(dataDir)) {
						fs.mkdirSync(dataDir, { recursive: true });
					}
					fs.writeFileSync(calendarsFilePath, JSON.stringify(listToSave, null, 2), "utf8");
					Log.info(`[Calendar API] Saved ${listToSave.length} calendars from Web Hub. Notifying clients to reload...`);
					io.emit("RELOAD");
					return res.json({ success: true, count: listToSave.length });
				} catch (err) {
					Log.error("[Calendar API] Error saving calendars:", err);
					res.status(500).json({ error: err.message });
				}
			};

			app.post("/api/calendars", handleSaveCalendars);
			app.post("/api/calendar/sync", handleSaveCalendars);
			app.post("/api/calendar/occurrences", (req, res) => {
				const { ics, from, to } = req.body || {};
				const start = new Date(from);
				const end = new Date(to);
				if (typeof ics !== "string" || !ics.includes("BEGIN:VCALENDAR") ||
					!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) ||
					end < start || end - start > 31 * 86400000) {
					return res.status(400).json({ error: "Invalid calendar or date range (maximum 31 days)" });
				}
				try {
					return res.json(getCalendarOccurrences(ics, start, end));
				} catch {
					return res.status(422).json({ error: "Unable to read calendar occurrences" });
				}
			});

			const startUp = new Date();
			const getStartup = (req, res) => res.send(startUp);

			const getConfig = (req, res) => {
				const obj = config.hideConfigSecrets ? configObj.redactedConf : configObj.fullConf;
				// Functions can't survive JSON.stringify, so we wrap them in a
				// tagged object { __mmFunction: "<source>" }. The client-side
				// JSON reviver in main.js recognises this tag and reconstructs
				// the live function from the source string.
				const jsonString = JSON.stringify(obj, (key, value) => {
					if (typeof value === "function") {
						return { __mmFunction: value.toString() };
					}
					return value;
				});
				res.set("Content-Type", "application/json");
				res.send(jsonString);
			};

			app.get("/config", (req, res) => getConfig(req, res));

			app.get("/cors", async (req, res) => await cors(req, res));

			app.get("/version", (req, res) => getVersion(req, res));

			app.get("/startup", (req, res) => getStartup(req, res));

			app.get("/env", (req, res) => getEnvVars(req, res));

			app.get("/", (req, res) => getHtml(req, res));

			// Reload endpoint for watch mode - triggers browser reload
			app.get("/reload", (req, res) => {
				Log.info("Reload request received, notifying all clients");
				io.emit("RELOAD");
				res.status(200).send("OK");
			});

			server.on("listening", () => {
				resolve({
					app,
					io
				});
			});
		});
	};

	/**
	 * Closes the server and destroys all lingering connections to it.
	 * @returns {Promise} A promise that resolves when server has successfully shut down
	 */
	this.close = function () {
		return new Promise((resolve) => {
			for (const socket of serverSockets.values()) {
				socket.destroy();
			}
			server.close(resolve);
		});
	};
}

module.exports = Server;
