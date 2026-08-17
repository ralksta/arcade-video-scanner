// safeStorage.js — localStorage, das nicht wirft
//
// Der Client weiß das an einer Stelle längst. In `serverConfig.js` steht seit
// jeher ein try/catch mit der Begründung: „webOS kann localStorage je nach
// Kontext sperren — dann eben der Default."
//
// An sechs anderen Stellen stand der Zugriff ungeschützt, und zwei davon sind
// die schlimmstmöglichen:
//
//     App.js:12    im Rumpf der App-Komponente, beim ersten Rendern
//     App.js:67    ebenda, bei jedem Rendern
//     MainPanel.js beim Laden der Bibliothek
//
// Eine Ausnahme im Rumpf einer React-Komponente bedeutet keinen halb
// aufgebauten Bildschirm, sondern gar keinen — und auf einem Fernseher gibt es
// keine Entwicklerkonsole, in der man nachsähe. Der Nutzer sieht schwarz und
// hat keinen Anhaltspunkt.
//
// Derselbe Weg wie im Browser-Client, wo `safe_storage.js` aus demselben Grund
// als erstes Skript geladen wird.

/**
 * Liest einen Wert. Gibt `fallback` zurück, wenn der Speicher gesperrt ist
 * oder der Schlüssel fehlt.
 *
 * @param {string} key
 * @param {*} [fallback]
 * @returns {*}
 */
export const getItem = (key, fallback = null) => {
	try {
		if (typeof window === 'undefined' || !window.localStorage) return fallback;
		const value = window.localStorage.getItem(key);
		return value === null ? fallback : value;
	} catch (e) {
		return fallback;
	}
};

/**
 * Schreibt einen Wert. Meldet über den Rückgabewert, ob es geklappt hat —
 * werfen darf es nicht.
 *
 * @param {string} key
 * @param {string} value
 * @returns {boolean}
 */
export const setItem = (key, value) => {
	try {
		if (typeof window === 'undefined' || !window.localStorage) return false;
		window.localStorage.setItem(key, value);
		return true;
	} catch (e) {
		return false;
	}
};

/**
 * Entfernt einen Wert.
 *
 * @param {string} key
 * @returns {boolean}
 */
export const removeItem = (key) => {
	try {
		if (typeof window === 'undefined' || !window.localStorage) return false;
		window.localStorage.removeItem(key);
		return true;
	} catch (e) {
		return false;
	}
};

export default {getItem, setItem, removeItem};
