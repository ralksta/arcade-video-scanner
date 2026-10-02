/**
 * Anzeigename eines Eintrags: Dateiname ohne Endung, Unterstriche als
 * Leerzeichen. Auf dem Fernseher liest niemand „.mp4“, und Unterstriche
 * brechen nicht um. Gemeinsam für Kacheln (MainPanel) und Player (App).
 *
 * @param {Object} v - Eintrag aus /api/videos (mit `_fileName`)
 * @returns {string}
 */
const displayName = (v) => {
	const name = (v && v._fileName) || '';
	const dot = name.lastIndexOf('.');
	return (dot > 0 ? name.slice(0, dot) : name).replace(/_/g, ' ');
};

export default displayName;
