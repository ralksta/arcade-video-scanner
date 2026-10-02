// watchProgress.js — wo man in einem Video aufgehört hat („Weiterschauen“).
//
// Pro Gerät in localStorage, nicht auf dem Server: Der Fernseher ist das
// Gerät, auf dem man weiterschaut, und es braucht dafür keine neue Route.

import {getItem, setItem} from './safeStorage';

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

const write = (all) => setItem(KEY, JSON.stringify(all));

/**
 * Merkt sich die Position. Am Anfang wird nichts gespeichert, kurz vor dem
 * Ende wird der Eintrag gelöscht — ein fertig gesehenes Video gehört nicht in
 * „Weiterschauen“.
 */
export const saveProgress = (path, seconds, duration) => {
	if (!path || !(duration > 0)) return;
	const all = read();
	if (seconds / duration >= FINISHED_RATIO) {
		delete all[path];
	} else if (seconds >= MIN_SECONDS) {
		all[path] = {t: Math.floor(seconds), d: Math.floor(duration), at: Date.now()};
		const paths = Object.keys(all);
		if (paths.length > MAX_ENTRIES) {
			paths.sort((a, b) => all[a].at - all[b].at)
				.slice(0, paths.length - MAX_ENTRIES)
				.forEach(p => delete all[p]);
		}
	} else {
		return;
	}
	write(all);
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
