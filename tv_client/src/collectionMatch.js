// collectionMatch.js — wertet Smart-Collection-Kriterien aus, wie der Browser.
//
// Übertragung von evaluateCollectionMatch() und seinen Helfern aus
// arcade_scanner/server/static/collections.js (und entryDate() aus utils.js).
// tests/test_tv_collection_parity.py verlangt für jede Fixture dasselbe
// Urteil wie der Browser.
//
// Bis 2026-10-02 übersprang der TV-Client Medientyp, Format, Auflösung,
// Ausrichtung, Größe, Dauer und Datum — mit der Begründung, seine Oberfläche
// biete diese Auswahl nicht an. Die Collections werden aber im Browser
// definiert und hier nur ausgewertet: Auf dem Fernseher zeigte „All Photos“,
// „Large Files (>1GB)“ und jede andere Standard-Collection einfach alles.
//
// Keine Imports: Der Test lädt die Datei direkt in Node (export-Zeilen
// werden dort entfernt).

const RELATIVE_SECONDS = {
	'1d': 24 * 60 * 60,
	'7d': 7 * 24 * 60 * 60,
	'30d': 30 * 24 * 60 * 60,
	'90d': 90 * 24 * 60 * 60,
	'1y': 365 * 24 * 60 * 60
};

function videoResolution (video) {
	const maxDim = Math.max(video.width || video.Width || 0, video.height || video.Height || 0);
	if (maxDim >= 3840) return '4k';
	if (maxDim >= 1920) return '1080p';
	if (maxDim >= 1280) return '720p';
	return 'sd';
}

function videoOrientation (video) {
	const width = video.width || video.Width || 0;
	const height = video.height || video.Height || 0;
	if (width === 0 || height === 0) return 'unknown';
	const ratio = width / height;
	if (ratio > 1.1) return 'landscape';
	if (ratio < 0.9) return 'portrait';
	return 'square';
}

// Importzeitpunkt, sonst Änderungszeit — dieselbe Regel wie entryDate() im Browser.
function entryDate (video) {
	if (!video) return 0;
	const imported = Number(video.imported_at) || 0;
	if (imported > 0) return imported;
	return Number(video.mtime) || 0;
}

function matchesDateFilter (video, dateFilter, nowSeconds) {
	if (!dateFilter || dateFilter === 'all' || (dateFilter.type && dateFilter.type === 'all')) return true;
	const timestamp = entryDate(video);
	if (timestamp === 0) return false;
	const relativeKey = typeof dateFilter === 'string' ? dateFilter : dateFilter.relative;
	if (relativeKey) {
		return timestamp >= nowSeconds - (RELATIVE_SECONDS[relativeKey] || 0);
	}
	return true;
}

// Suchsprache — dieselbe Regel wie static/search_query.js und
// core/criteria_eval.py: Begriffe sind UND-verknüpft, -Wort schließt aus,
// Pfade (mit / oder \) gelten auf Ordnergrenze, Umlaute werden gefaltet.
function foldSearchText (value) {
	return String(value == null ? '' : value)
		.toLowerCase()
		.normalize('NFD')
		.replace(/[̀-ͯ]/g, '')
		.replace(/ß/g, 'ss');
}

function parseSearchQuery (text) {
	const raw = String(text == null ? '' : text);
	const terms = [];
	let i = 0;

	while (i < raw.length) {
		while (i < raw.length && /\s/.test(raw[i])) i++;
		if (i >= raw.length) break;

		let negated = false;
		if (raw[i] === '-') {
			negated = true;
			i++;
		}

		let value = '';
		if (raw[i] === '"') {
			i++;
			while (i < raw.length) {
				const ch = raw[i];
				if (ch === '\\' && (raw[i + 1] === '"' || raw[i + 1] === '\\')) {
					value += raw[i + 1];
					i += 2;
					continue;
				}
				if (ch === '"') {
					i++;
					break;
				}
				value += ch;
				i++;
			}
		} else {
			const start = i;
			while (i < raw.length && !/\s/.test(raw[i])) i++;
			value = raw.slice(start, i);
		}

		if (!value) continue;

		// "#tag" — ein einzelnes "#" bleibt ein normaler Suchbegriff.
		let isTag = value.charAt(0) === '#';
		let searchValue = isTag ? value.slice(1) : value;
		if (isTag && !searchValue) {
			isTag = false;
			searchValue = value;
		}

		terms.push({
			value: searchValue,
			folded: foldSearchText(searchValue),
			negated: negated,
			isTag: isTag,
			isPath: !isTag && (searchValue.indexOf('/') !== -1 || searchValue.indexOf('\\') !== -1)
		});
	}

	return {raw: raw, terms: terms, noTerms: terms.length === 0};
}

function foldedPathMatches (foldedFile, foldedPrefix) {
	const file = foldedFile.replace(/\\/g, '/');
	let prefix = foldedPrefix.replace(/\\/g, '/');
	while (prefix.length > 1 && prefix.endsWith('/')) prefix = prefix.slice(0, -1);
	if (!prefix || prefix === '/') return true;

	let from = 0;
	while (from <= file.length) {
		const idx = file.indexOf(prefix, from);
		if (idx === -1) return false;
		const beforeOk = idx === 0 || file[idx - 1] === '/';
		const after = idx + prefix.length;
		const afterOk = after === file.length || file[after] === '/';
		if (beforeOk && afterOk) return true;
		from = idx + 1;
	}
	return false;
}

function searchMatches (filePath, text, tags) {
	const parsed = parseSearchQuery(text);
	const foldedPath = foldSearchText(filePath);
	const foldedName = foldSearchText(filePath.replace(/\\/g, '/').split('/').pop() || '');
	const foldedTags = (Array.isArray(tags) ? tags : []).map(foldSearchText);

	if (parsed.noTerms) {
		if (!parsed.raw) return true;
		const literal = foldSearchText(parsed.raw);
		return foldedPath.indexOf(literal) !== -1 || foldedName.indexOf(literal) !== -1;
	}

	// Positive Pfade sind eine ODER-Gruppe (wie im Browser).
	const hasPositivePath = parsed.terms.some(t => t.isPath && !t.negated);
	let pathHit = !hasPositivePath;

	for (let i = 0; i < parsed.terms.length; i++) {
		const term = parsed.terms[i];
		let hit;
		if (term.isTag) {
			hit = foldedTags.indexOf(term.folded) !== -1;
		} else if (term.isPath) {
			hit = foldedPathMatches(foldedPath, term.folded);
		} else {
			hit = foldedName.indexOf(term.folded) !== -1 || foldedPath.indexOf(term.folded) !== -1;
		}

		if (term.negated) {
			if (hit) return false;
		} else if (term.isPath) {
			if (hit) pathHit = true;
		} else if (!hit) {
			return false;
		}
	}
	return pathHit;
}

/**
 * Passt `video` (Eintrag aus /api/videos, mit favorite/tags aus den
 * Nutzerdaten) auf die Kriterien einer Smart Collection?
 *
 * @param {Object} video
 * @param {Object} criteria
 * @returns {boolean}
 */
function matchesCollectionCriteria (video, criteria) {
	if (!criteria) return true;

	const matchesAny = (videoVal, arr) => arr.length === 0 || arr.some(v =>
		(videoVal && videoVal.toLowerCase && videoVal.toLowerCase().includes(v.toLowerCase())) || videoVal === v
	);
	const isExcluded = (videoVal, arr) => arr.length > 0 && arr.some(v =>
		(videoVal && videoVal.toLowerCase && videoVal.toLowerCase().includes(v.toLowerCase())) || videoVal === v
	);
	const has = (arr) => Array.isArray(arr) && arr.length > 0;

	// Die API liefert das Feld als `Status` mit großem S (früher las der TV
	// `v.status` — immer undefined).
	const status = video.Status || '';
	const codec = (video.codec || '').toLowerCase();
	const videoTags = video.tags || [];
	const resolution = videoResolution(video);
	const orientation = videoOrientation(video);
	const duration = video.Duration_Sec || 0;
	const sizeMB = video.Size_MB || 0;
	const mediaType = video.media_type || 'video';

	let format = '';
	if (video.format) {
		format = video.format.toLowerCase();
	} else if (video.FilePath) {
		format = video.FilePath.split('.').pop().toLowerCase();
	}

	// --- Ausschlüsse ---
	const exc = criteria.exclude || {};
	if (has(exc.media_type) && exc.media_type.includes(mediaType)) return false;
	if (has(exc.format) && isExcluded(format, exc.format)) return false;
	if (has(exc.status) && isExcluded(status, exc.status)) return false;
	// Codec als Teilstring: die API liefert auch „hevc (Main 10)“.
	if (has(exc.codec) && exc.codec.some(c => codec.includes(c.toLowerCase()))) return false;
	if (has(exc.tags) && exc.tags.some(t => videoTags.includes(t))) return false;
	if (has(exc.resolution) && exc.resolution.includes(resolution)) return false;
	if (has(exc.orientation) && exc.orientation.includes(orientation)) return false;

	// --- Einschlüsse ---
	const inc = criteria.include || {};
	if (has(inc.media_type) && !inc.media_type.includes(mediaType)) return false;
	if (has(inc.format) && !matchesAny(format, inc.format)) return false;
	if (has(inc.status)) {
		const statusMatch = inc.status.some(s => {
			if (s === 'optimized_files') return (video.FilePath || '').includes('_opt');
			return status === s;
		});
		if (!statusMatch) return false;
	}
	if (has(inc.codec) && !inc.codec.some(c => codec.includes(c.toLowerCase()))) return false;
	if (has(inc.tags)) {
		if (criteria.tagLogic === 'all') {
			if (!inc.tags.every(t => videoTags.includes(t))) return false;
		} else if (!inc.tags.some(t => videoTags.includes(t))) {
			return false;
		}
	}
	if (has(inc.resolution) && !inc.resolution.includes(resolution)) return false;
	if (has(inc.orientation) && !inc.orientation.includes(orientation)) return false;

	// --- Favoriten (beide Richtungen) ---
	const wantOnlyFavorites = criteria.favorites === true || criteria.favorites === 'true';
	const wantExcludeFavorites = criteria.favorites === false || criteria.favorites === 'false';
	if (wantOnlyFavorites || wantExcludeFavorites) {
		const isFav = !!(video.favorite || video.Favorite || video.isFavorite || video.IsFavorite);
		if (wantOnlyFavorites && !isFav) return false;
		if (wantExcludeFavorites && isFav) return false;
	}

	// --- Datum, Dauer, Größe ---
	if (criteria.date && !matchesDateFilter(video, criteria.date, Math.floor(Date.now() / 1000))) return false;
	if (criteria.duration) {
		if (criteria.duration.min !== null && criteria.duration.min !== undefined && duration < criteria.duration.min) return false;
		if (criteria.duration.max !== null && criteria.duration.max !== undefined && duration > criteria.duration.max) return false;
	}
	if (criteria.size) {
		if (criteria.size.min !== null && criteria.size.min !== undefined && sizeMB < criteria.size.min) return false;
		if (criteria.size.max !== null && criteria.size.max !== undefined && sizeMB > criteria.size.max) return false;
	}

	// --- Suche ---
	if (criteria.search && !searchMatches(video.FilePath || '', criteria.search, videoTags)) return false;

	return true;
}

export {matchesCollectionCriteria, videoResolution, entryDate};
