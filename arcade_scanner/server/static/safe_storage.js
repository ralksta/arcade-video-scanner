// safe_storage.js — muss als ERSTES Skript geladen werden.
//
// Eigene Datei, weil store.js, utils.js, workspace.js, collections.js und
// settings.js es alle brauchen. In store.js untergebracht hätte es eine
// stillschweigende Ladereihenfolge-Abhängigkeit erzeugt: Zur Laufzeit hätte
// sie gehalten (store.js steht vorn), aber die Tests laden einzelne Dateien
// bewusst für sich — und genau daran ist der erste Versuch gescheitert.

/**
 * Gutmütiger Zugriff auf localStorage.
 *
 * `localStorage` ist nicht überall benutzbar: Manche Browser sperren es bei
 * blockierten Cookies oder im privaten Modus, und der Zugriff wirft dann
 * bereits beim *Lesen*. Das Projekt weiss das an anderer Stelle schon —
 * `tv_client/src/serverConfig.js` fängt es ausdrücklich ab („webOS kann
 * localStorage je nach Kontext sperren").
 *
 * Im Browser-Client wurde es ungeschützt gelesen, und zwar in drei Dateien
 * beim Laden: hier ganz oben, in `initTheme()` (utils.js) und in
 * `initGridScale()` (workspace.js). Diese Datei ist das **erste** Skript der
 * Seite — eine Ausnahme hier bedeutet keine halb geladene Oberfläche, sondern
 * gar keine.
 *
 * `getJSON` fängt zusätzlich kaputten Inhalt ab: In collections.js stand ein
 * `JSON.parse(localStorage.getItem(...) || '{}')`, das bei einem beschädigten
 * Wert die gesamte Sammlungsansicht dauerhaft lahmgelegt hätte.
 */
window.safeStorage = {
    get(key, fallback = null) {
        try {
            const value = window.localStorage.getItem(key);
            return value === null ? fallback : value;
        } catch (e) {
            return fallback;
        }
    },
    set(key, value) {
        try {
            window.localStorage.setItem(key, value);
            return true;
        } catch (e) {
            return false;
        }
    },
    getJSON(key, fallback) {
        const raw = window.safeStorage.get(key, null);
        if (raw === null) return fallback;
        try {
            return JSON.parse(raw);
        } catch (e) {
            console.warn(`Verworfen: ${key} enthält kein gültiges JSON`);
            return fallback;
        }
    },
};
