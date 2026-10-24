// watchProgress.js — wo man in einem Video aufgehört hat („Weiterschauen“).
//
// Maßgeblich ist der Server (/api/progress, pro Konto): Was man am Fernseher
// anfängt, setzt man im Browser fort und umgekehrt. localStorage bleibt als
// Zwischenspeicher, weil Player und Detailansicht die Position synchron
// brauchen und der Fernseher auch ohne Netz weiß, wo er war.
//
// Die Schwellen (20 s, 95 %) gelten auf dem Server genauso; hier stehen sie
// nur, damit der Zwischenspeicher dasselbe zeigt, bevor der Server antwortet.

import {getItem, setItem} from './safeStorage';
import {serverUrl} from './serverConfig';

const KEY = 'arcade_watch_progress';
const MAX_ENTRIES = 50;
const MIN_SECONDS = 20;        // darunter lohnt kein Fortsetzen
const FINISHED_RATIO = 0.95;   // ab hier gilt das Video als gesehen

const read = () => {
	try {
		const parsed = JSON.parse(getItem(KEY, '{}'));
		return parsed && typeof parsed === 'object' ? parsed : {};
	} catch (e) {
		return {};
	}
};

const write = (all) => {
	const paths = Object.keys(all);
	if (paths.length > MAX_ENTRIES) {
		paths.sort((a, b) => all[a].at - all[b].at)
			.slice(0, paths.length - MAX_ENTRIES)
			.forEach(p => delete all[p]);
	}
	setItem(KEY, JSON.stringify(all));
};

const headers = () => {
	const token = getItem('arcade_session_token', '');
	const h = {'Content-Type': 'application/json'};
	if (token) h.Authorization = `Bearer ${token}`;
	return h;
};

const push = (path, seconds, duration) =>
	fetch(serverUrl('/api/progress'), {
		method: 'POST',
		headers: headers(),
		body: JSON.stringify({path, position: seconds, duration}),
		keepalive: true
	}).catch(() => {
		// Offline: Der Zwischenspeicher hat den Stand, syncProgress() reicht
		// ihn beim nächsten Laden nach.
	});

/**
 * Merkt sich die Position — lokal und auf dem Server. Am Anfang wird nichts
 * gespeichert, kurz vor dem Ende fällt das Video aus „Weiterschauen“.
 */
export const saveProgress = (path, seconds, duration) => {
	if (!path || !(duration > 0)) return;
	const all = read();
	if (seconds / duration >= FINISHED_RATIO) {
		delete all[path];
	} else if (seconds >= MIN_SECONDS) {
		all[path] = {t: Math.floor(seconds), d: Math.floor(duration), at: Date.now()};
	} else {
		return;
	}
	write(all);
	push(path, seconds, duration);
};

/** Gespeicherte Position in Sekunden, oder 0. */
export const getProgress = (path) => {
	const entry = read()[path];
	return entry ? entry.t : 0;
};

/** Alle angefangenen Videos, zuletzt gesehenes zuerst: [{path, t, d, at}] */
export const listProgress = () => {
	const all = read();
	return Object.keys(all)
		.map(path => ({path, ...all[path]}))
		.sort((a, b) => b.at - a.at);
};

/**
 * Gleicht den Zwischenspeicher mit dem Server ab. Der jüngere Stand gewinnt:
 * Was der Server neuer kennt, wird übernommen; was nur hier liegt oder hier
 * neuer ist — etwa aus der Zeit vor dem Server-Fortschritt —, wird
 * hochgeladen.
 *
 * @returns {Promise<boolean>} true, wenn sich der Zwischenspeicher geändert hat
 */
export const syncProgress = () =>
	fetch(serverUrl('/api/progress'), {headers: headers()})
		.then(res => (res.ok ? res.json() : null))
		.then(data => {
			if (!data || !Array.isArray(data.items)) return false;
			const all = read();
			const seen = new Set();
			let changed = false;
			data.items.forEach(item => {
				seen.add(item.path);
				const local = all[item.path];
				const at = item.updated_at * 1000;
				if (local && local.at > at) {
					push(item.path, local.t, local.d);
				} else if (item.position > 0) {
					all[item.path] = {t: Math.floor(item.position), d: Math.floor(item.duration), at};
					changed = true;
				} else if (local) {
					// Auf einem anderen Gerät zu Ende gesehen
					delete all[item.path];
					changed = true;
				}
			});
			Object.keys(all)
				.filter(path => !seen.has(path))
				.forEach(path => push(path, all[path].t, all[path].d));
			if (changed) write(all);
			return changed;
		})
		.catch(() => false);
