// displayName.js — Anzeigetitel eines Eintrags.
//
// Auf dem Fernseher liest niemand „.mp4“ oder „VID_20251025_121813_115“.
// Gemeinsam für Kacheln (MainPanel) und Player (App).
//
// Dieselbe Logik steht im Browser-Client (static/formatters.js,
// titleFromFileName). Beide werden in tests/test_media_titles.py gegen
// dieselben Beispiele geprüft — Änderungen immer an beiden Stellen.
//
// Bewusst ohne Imports: Der Test lädt die Datei als Skript.

const TITLE_MONTHS = ['Jan.', 'Feb.', 'März', 'Apr.', 'Mai', 'Juni', 'Juli', 'Aug.',
	'Sept.', 'Okt.', 'Nov.', 'Dez.'];

// Was der Optimierer anhängt: film_opt.mp4, film__h265__h265_0.mp4, …
const TITLE_ENCODE_SUFFIX = /(?:[ _.-]+(?:opt|optimized|h265|hevc|x265|av1|trim|trimmed)(?:[_-]\d+)?)+$/i;

// Kamera- und Handy-Namen: VID_20251025_121813_115, PXL_20240512_131415123,
// IMG_20240512_131415, 20251025_121813, 2025-10-25 12.18.13 (1), …
const TITLE_CAMERA = new RegExp(
	'^(?:(?:VID|IMG|PXL|MVIMG|MOV|DSC|DJI|PANO|LV|signal|video|Screen[ _-]?Recording|Screenrecorder)[ _-]*)?' +
	'(\\d{4})[-_.]?(\\d{2})[-_.]?(\\d{2})' +
	'(?:[-_ T.]*(\\d{2})[-_.:]?(\\d{2})(?:[-_.:]?(\\d{2}))?)?' +
	'(?:[-_ .~]*(?:WA)?\\(?\\d+\\)?)*$', 'i');

/**
 * Lesbarer Titel aus einem Dateinamen (siehe Kopf der Datei).
 *
 * @param {string} fileName - Dateiname mit oder ohne Endung
 * @returns {string}
 */
const titleFromFileName = (fileName) => {
	const original = String(fileName || '');
	const dot = original.lastIndexOf('.');
	let name = dot > 0 ? original.slice(0, dot) : original;
	name = name.replace(TITLE_ENCODE_SUFFIX, '');

	const m = TITLE_CAMERA.exec(name);
	if (m) {
		const year = +m[1], month = +m[2], day = +m[3];
		const hasTime = m[4] !== undefined;
		const hour = +m[4], minute = +m[5];
		const plausible = year >= 1990 && year <= 2100 && month >= 1 && month <= 12 &&
			day >= 1 && day <= 31 && (!hasTime || (hour <= 23 && minute <= 59));
		if (plausible) {
			const date = `${day}. ${TITLE_MONTHS[month - 1]} ${year}`;
			return hasTime ? `${date} · ${m[4]}:${m[5]}` : date;
		}
	}

	let title = name.replace(/_+/g, ' ');
	if (!/\s/.test(title)) title = title.replace(/\.+/g, ' ');
	title = title.replace(/\s+/g, ' ').replace(/^[\s.-]+|[\s.-]+$/g, '');
	return title || original;
};

/**
 * @param {Object} v - Eintrag aus /api/videos (mit `_fileName`)
 * @returns {string}
 */
const displayName = (v) => titleFromFileName((v && v._fileName) || '');

export {titleFromFileName};
export default displayName;
