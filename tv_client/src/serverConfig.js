// serverConfig.js — eine Stelle für die Server-Adresse
//
// Die Adresse stand an acht Stellen in MainPanel.js und LoginPanel.js fest
// verdrahtet. Der Client funktionierte damit nur in genau einem Netz mit genau
// dieser IP: vergibt der Router eine andere, laden weder Bibliothek noch
// Vorschaubilder — und die Ursache steht an acht Stellen statt an einer.
//
// Nächster Schritt (bewusst noch offen): die Adresse im Login-Bildschirm
// abfragen und speichern, wie es der iOS-Client mit seinem serverUrl-Feld tut.
// Bis dahin ist sie wenigstens an einer Stelle änderbar.

import {getItem} from './safeStorage';

const DEFAULT_SERVER_URL = 'http://192.168.2.183:8000';

const STORAGE_KEY = 'arcade.serverUrl';

/**
 * Basis-URL des Servers, ohne abschließenden Schrägstrich.
 *
 * Liest einen gespeicherten Wert, falls vorhanden — damit lässt sich die
 * Adresse ohne neuen Build umstellen, sobald der Login-Bildschirm sie abfragt.
 *
 * @returns {string}
 */
export const getServerUrl = () => {
	try {
		const stored = window.localStorage.getItem(STORAGE_KEY);
		if (stored) return stored.replace(/\/+$/, '');
	} catch (e) {
		// webOS kann localStorage je nach Kontext sperren — dann eben der Default.
	}
	return DEFAULT_SERVER_URL;
};

/**
 * Vollständige URL zu einem Server-Pfad.
 *
 * @param {string} path - Pfad mit führendem Schrägstrich, z. B. '/api/videos'
 * @returns {string}
 */
export const serverUrl = (path) => `${getServerUrl()}${path}`;

/**
 * URL eines Vorschaubilds — mit Sitzungs-Token.
 *
 * Seit UMSETZUNGSPLAN Phase 6 verlangt /thumbnails eine Sitzung. Ein <img>
 * kann keinen Authorization-Header setzen, und der Fernseher hat kein
 * Server-Cookie; das Token geht deshalb als Query-Parameter mit, genauso wie
 * bei /stream (App.js). Der Server maskiert es im Log.
 *
 * @param {string} thumb - Dateiname aus dem Feld `thumb` der API
 * @returns {string}
 */
export const thumbnailUrl = (thumb) => {
	const token = getItem('arcade_session_token', '');
	const query = token ? `?token=${encodeURIComponent(token)}` : '';
	return serverUrl(`/thumbnails/${encodeURIComponent(thumb || '')}${query}`);
};

export {DEFAULT_SERVER_URL, STORAGE_KEY};
