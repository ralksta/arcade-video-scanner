import React, {useState, useEffect, useCallback, useMemo} from 'react';
import {serverUrl, thumbnailUrl} from '../serverConfig';
import PropTypes from 'prop-types';
import {Panel, Header} from '@enact/limestone/Panels';
import TabLayout, {Tab} from '@enact/limestone/TabLayout';
import {VirtualGridList} from '@enact/limestone/VirtualList';
import ImageItem from '@enact/limestone/ImageItem';
import Button from '@enact/limestone/Button';
import {InputField} from '@enact/limestone/Input';
import ri from '@enact/ui/resolution';

const SORT_OPTIONS = [
	{key: 'newest', label: '🕐 Neueste'},
	{key: 'name_az', label: '🔤 A → Z'},
	{key: 'name_za', label: '🔤 Z → A'},
	{key: 'size_desc', label: '📦 Größte'},
	{key: 'size_asc', label: '📦 Kleinste'}
];

// Datum eines Eintrags, in Sekunden. Gleiche Quelle wie im Browser-Client,
// der für seine 'date'-Sortierung `b.mtime - a.mtime` rechnet.
const mtimeOf = (v) => v.mtime || 0;

const sortVideos = (list, sortKey) => {
	const sorted = [...list];
	switch (sortKey) {
		case 'name_az':
			return sorted.sort((a, b) => (a._fileName || '').localeCompare(b._fileName || ''));
		case 'name_za':
			return sorted.sort((a, b) => (b._fileName || '').localeCompare(a._fileName || ''));
		case 'size_desc':
			return sorted.sort((a, b) => (b.Size_MB || 0) - (a.Size_MB || 0));
		case 'size_asc':
			return sorted.sort((a, b) => (a.Size_MB || 0) - (b.Size_MB || 0));
		case 'newest':
		default:
			// Hier stand `sorted.reverse()`. Das dreht die Reihenfolge um, in
			// der /api/videos liefert — und das ist `SELECT * FROM media` ohne
			// ORDER BY, also die Einfügereihenfolge des ersten Scans. Mit dem
			// Alter der Dateien hat sie nichts zu tun.
			//
			// An der echten Bibliothek nachgemessen: Unter „newest" standen
			// Aufnahmen vom Oktober 2025, während die tatsächlich neuesten vom
			// August 2026 waren — null Überschneidung in den ersten zehn.
			return sorted.sort((a, b) => mtimeOf(b) - mtimeOf(a));
	}
};

// Muss dieselben Verdikte liefern wie evaluateCollectionMatch() im
// Browser-Client (arcade_scanner/server/static/collections.js) und wie der
// Python-Port in arcade_scanner/core/criteria_eval.py. Ein Differenztest
// (tests/test_tv_collection_parity.py) hält die drei gegeneinander.
//
// Bewusst NICHT unterstützt, weil die TV-Oberfläche diese Dimensionen nicht
// anbietet: media_type, format, resolution, orientation, Größen- und
// Dauergrenzen. Sammlungen, die darauf beruhen, zeigen auf dem Fernseher mehr
// Treffer als im Browser — dokumentiert statt still abweichend.
const matchesCollectionCriteria = (v, criteria) => {
	if (!criteria) return true;
	const inc = criteria.include || {};
	const exc = criteria.exclude || {};

	// Die API liefert das Feld als `Status` mit großem S. Hier stand `v.status`:
	// immer undefined, womit 'optimized' nie und 'pending' immer traf — auf dem
	// Fernseher zeigte dieselbe Sammlung also nichts oder alles.
	const status = v.Status || '';
	const codec = (v.codec || '').toLowerCase();

	// Vault-Videos gehören in keine Sammlung — gleiche Regel wie im Browser.
	// Der TV-Client filtert sie zwar beim Laden schon heraus, aber die Regel
	// gehört in den Matcher: sonst hängt die Korrektheit daran, dass jeder
	// künftige Aufrufer daran denkt.
	if (v.hidden) return false;

	// Status
	if (inc.status && inc.status.length) {
		const match = inc.status.some(s => {
			// Gleiche Sonderregel wie im Browser: '_opt' im Dateinamen.
			if (s === 'optimized_files') return (v.FilePath || '').includes('_opt');
			return status === s;
		});
		if (!match) return false;
	}
	if (exc.status && exc.status.length) {
		if (exc.status.some(s => status.toLowerCase().includes(s.toLowerCase()) || status === s)) {
			return false;
		}
	}

	// Codec — Teilstring wie im Browser: die API liefert auch Werte wie
	// "hevc (Main 10)", ein exakter Vergleich verfehlt die.
	if (inc.codec && inc.codec.length) {
		if (!inc.codec.some(c => codec.includes(c.toLowerCase()))) return false;
	}
	if (exc.codec && exc.codec.length) {
		if (exc.codec.some(c => codec.includes(c.toLowerCase()))) return false;
	}

	// Tags
	if (inc.tags && inc.tags.length) {
		const videoTags = v.tags || [];
		if (criteria.tagLogic === 'all') {
			if (!inc.tags.every(t => videoTags.includes(t))) return false;
		} else {
			if (!inc.tags.some(t => videoTags.includes(t))) return false;
		}
	}
	if (exc.tags && exc.tags.length) {
		const videoTags = v.tags || [];
		if (exc.tags.some(t => videoTags.includes(t))) return false;
	}

	// Search
	if (criteria.search) {
		const q = criteria.search.toLowerCase();
		if (!v.FilePath.toLowerCase().includes(q)) return false;
	}

	// Favorites — der Browser kennt beide Richtungen: true = nur Favoriten,
	// false = Favoriten ausschließen. Letzteres fehlte hier.
	const wantOnlyFavorites = criteria.favorites === true || criteria.favorites === 'true';
	const wantExcludeFavorites = criteria.favorites === false || criteria.favorites === 'false';
	if (wantOnlyFavorites && !v.favorite) return false;
	if (wantExcludeFavorites && v.favorite) return false;

	return true;
};

// Die API liefert Width und Height, kein Feld `resolution` — hier stand
// `v.resolution || ''`, also immer ein leerer String: die Auflösung fehlte im
// Label, ohne dass etwas kaputt aussah. Schwellwerte wie getVideoResolution()
// im Browser-Client.
const resolutionLabel = (v) => {
	const maxDim = Math.max(v.Width || 0, v.Height || 0);
	if (maxDim >= 3840) return '4K';
	if (maxDim >= 1920) return '1080p';
	if (maxDim >= 1280) return '720p';
	if (maxDim > 0) return 'SD';
	return '';
};

const formatSize = (mb) => {
	if (!mb) return '';
	if (mb >= 1024) {
		return `${(mb / 1024).toFixed(1)} GB`;
	}
	return `${mb.toFixed(0)} MB`;
};

const formatDuration = (seconds) => {
	if (!seconds) return '';
	const mins = Math.round(seconds / 60);
	if (mins < 1) return `${Math.round(seconds)} Sek`;
	return `${mins} Min`;
};

const MainPanel = ({onSelectVideo, onAuthFailed, ...props}) => {
	const [allVideos, setAllVideos] = useState([]);
	const [smartCollections, setSmartCollections] = useState([]);
	const [recommendations, setRecommendations] = useState([]);
	const [selectedCollectionId, setSelectedCollectionId] = useState(null);
	const [tabIndex, setTabIndex] = useState(0);
	const [loading, setLoading] = useState(true);
	// Ohne die Nutzerdaten ist unbekannt, welche Einträge im Vault liegen —
	// dann wird nichts angezeigt statt alles. Siehe den Kommentar bei
	// setUserDataFailed unten.
	const [userDataFailed, setUserDataFailed] = useState(false);
	const [sortKey, setSortKey] = useState('newest');
	const [filterText, setFilterText] = useState('');

	// Daten und Collections laden
	useEffect(() => {
		const token = localStorage.getItem('arcade_session_token');
		const headers = {
			'Content-Type': 'application/json'
		};
		if (token) {
			headers['Authorization'] = `Bearer ${token}`;
		}

		// Videos abrufen
		const videosPromise = fetch(serverUrl('/api/videos'), { headers })
			.then(res => {
				if (res.status === 401) {
					localStorage.removeItem('arcade_session_token');
					if (onAuthFailed) onAuthFailed();
					throw new Error('Unauthorized');
				}
				if (!res.ok) throw new Error('Network error');
				return res.json();
			})
			.then(data => {
				data.forEach(v => {
					const path = v.FilePath;
					const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
					v._fileName = path.substring(lastIdx + 1);
				});
				return data;
			});

		// User-Daten für Smart Collections und Favoriten abrufen
		const userDataPromise = fetch(serverUrl('/api/user/data'), { headers })
			.then(res => {
				if (res.ok) return res.json();
				return null;
			})
			.catch(err => {
				console.warn('Error fetching collections/userdata:', err);
				return null;
			});

		Promise.all([videosPromise, userDataPromise])
			.then(([videosData, userData]) => {
				// Mapping von Favoriten, Vault-Status und Tags aus den User-Daten auf die Videos
				if (userData) {
					const favSet = new Set(userData.favorites || []);
					const vaultSet = new Set(userData.vaulted || []);
					const tagMap = userData.tags || {};
					videosData.forEach(v => {
						v.favorite = favSet.has(v.FilePath);
						v.hidden = vaultSet.has(v.FilePath);
						v.tags = tagMap[v.FilePath] || [];
					});
				}

				// `userData` ist null, wenn /api/user/data nicht erreichbar war.
				// Dann bleibt `v.hidden` auf jedem Eintrag undefined, und jeder
				// Filter unten prüft `!v.hidden` — undefined ist falsy, also
				// stünde der gesamte Vault im Raster. Auf einem Fernseher im
				// Wohnzimmer ist das die denkbar falscheste Richtung.
				//
				// Derselbe Fehler steckte im Browser-Client; dort ist er in
				// filter_engine.js behoben.
				if (!userData) {
					setUserDataFailed(true);
					setLoading(false);
					return;
				}

				setAllVideos(videosData);

				if (userData && userData.smart_collections) {
					setSmartCollections(userData.smart_collections);
				}

				// Zufällige Empfehlungen generieren (nur sichtbare Videos)
				const videoOnly = videosData.filter(v => (v.media_type || 'video') === 'video' && !v.hidden);
				const shuffled = [...videoOnly].sort(() => 0.5 - Math.random());
				setRecommendations(shuffled.slice(0, 5));

				setLoading(false);
			})
			.catch(err => {
				console.error('Fetch error:', err);
				setLoading(false);
			});
	}, [onAuthFailed]);

	const handleFilterChange = useCallback((ev) => {
		setFilterText(ev.value || '');
	}, []);

	// Filtergruppen erstellen + sortieren
	const filterAndSort = useCallback((list) => {
		let result = list;
		if (filterText.trim()) {
			const q = filterText.trim().toLowerCase();
			result = result.filter(v => (v._fileName || '').toLowerCase().includes(q));
		}
		return sortVideos(result, sortKey);
	}, [filterText, sortKey]);

	const videos = useMemo(() =>
		filterAndSort(allVideos.filter(v => (v.media_type || 'video') === 'video' && !v.hidden)),
	[allVideos, filterAndSort]);

	const favorites = useMemo(() =>
		filterAndSort(allVideos.filter(v => v.favorite && !v.hidden)),
	[allVideos, filterAndSort]);

	// „Zuletzt hinzugefügt": ebenfalls nach Datum, nicht nach den letzten 48
	// Zeilen der Datenbank. `slice(-48)` nahm das Ende der Einfügereihenfolge —
	// dieselbe Verwechslung wie beim „newest"-Sortierschlüssel oben.
	const recent = useMemo(() =>
		filterAndSort(
			[...allVideos]
				.filter(v => !v.hidden)
				.sort((a, b) => mtimeOf(b) - mtimeOf(a))
				.slice(0, 48)
		),
	[allVideos, filterAndSort]);

	const images = useMemo(() =>
		filterAndSort(allVideos.filter(v => v.media_type === 'image' && !v.hidden)),
	[allVideos, filterAndSort]);

	const vault = useMemo(() =>
		filterAndSort(allVideos.filter(v => v.hidden)),
	[allVideos, filterAndSort]);

	// Aktive Collection ermitteln
	const selectedCollection = useMemo(() => {
		return smartCollections.find(c => c.id === selectedCollectionId);
	}, [smartCollections, selectedCollectionId]);

	// Videos der aktiven Collection filtern
	const collectionVideos = useMemo(() => {
		if (!selectedCollection) return [];
		const filtered = allVideos.filter(v => matchesCollectionCriteria(v, selectedCollection.criteria));
		return filterAndSort(filtered);
	}, [allVideos, selectedCollection, filterAndSort]);

	// Collections nach Kategorie gruppieren
	const collectionsByCategory = useMemo(() => {
		const groups = {};
		smartCollections.forEach(col => {
			const cat = col.category || 'Uncategorized';
			if (!groups[cat]) groups[cat] = [];
			groups[cat].push(col);
		});
		return groups;
	}, [smartCollections]);

	// Item Renderer Factory
	const makeRenderer = useCallback((list) => ({index, ...itemProps}) => {
		const v = list[index];
		if (!v) return null;

		const isImage = v.media_type === 'image';
		const sizeStr = formatSize(v.Size_MB);
		const durationStr = formatDuration(v.Duration_Sec);
		const resStr = resolutionLabel(v);

		const labelText = [
			sizeStr,
			durationStr,
			resStr
		].filter(Boolean).join(' | ');

		return (
			<ImageItem
				{...itemProps}
				src={thumbnailUrl(v.thumb)}
				label={labelText}
				onClick={() => onSelectVideo(v)}
				wideImage={!isImage}
			>
				{v._fileName}
			</ImageItem>
		);
	}, [onSelectVideo]);

	const handleTabSelect = useCallback((ev) => {
		setTabIndex(ev.index);
	}, []);

	const subtitle = userDataFailed
		? 'Nutzerdaten nicht abrufbar'
		: loading
		? 'Lade Mediathek...'
		: filterText
			? `${videos.length} Treffer für "${filterText}"`
			: `${videos.length} Videos`;

	return (
		<Panel {...props}>
			<Header
				title="Arcade Scanner TV"
				subtitle={subtitle}
			/>

			{/* Sortier- und Filterleiste */}
			<div style={{display: 'flex', alignItems: 'center', gap: ri.scale(16) + 'px', padding: `${ri.scale(8)}px ${ri.scale(24)}px`, flexWrap: 'wrap'}}>
				<InputField
					placeholder="🔍 Suche nach Name..."
					value={filterText}
					onChange={handleFilterChange}
					style={{minWidth: ri.scale(320) + 'px'}}
				/>
				{SORT_OPTIONS.map(opt => (
					<Button
						key={opt.key}
						size="small"
						selected={sortKey === opt.key}
						onClick={() => setSortKey(opt.key)}
					>
						{opt.label}
					</Button>
				))}
			</div>

			{userDataFailed && (
				<div style={{padding: ri.scale(48) + 'px', textAlign: 'center'}}>
					<div style={{fontSize: ri.scale(24) + 'px', color: '#ff0090'}}>
						Deine Nutzerdaten konnten nicht geladen werden.
					</div>
					<div style={{fontSize: ri.scale(16) + 'px', color: 'gray', marginTop: ri.scale(12) + 'px'}}>
						Die Mediathek wird nicht angezeigt, weil sonst auch Einträge aus dem Vault sichtbar wären.
					</div>
				</div>
			)}

			{!loading && !userDataFailed && (
				<TabLayout index={tabIndex} onSelect={handleTabSelect}>
					<Tab title="Home" icon="home">
						<div style={{overflowY: 'auto', height: '100%', padding: `${ri.scale(16)}px ${ri.scale(24)}px`, display: 'flex', flexDirection: 'column', gap: ri.scale(32) + 'px'}}>
							
							{/* Begrüßung */}
							<div>
								<h2 style={{fontSize: ri.scale(28) + 'px', fontWeight: 'bold', color: '#ff0090'}}>Moin Ralf! ⚓</h2>
								<p style={{color: 'gray', fontSize: ri.scale(16) + 'px'}}>Willkommen auf dem Arcade-Kutter. Hier ist deine heutige Auswahl:</p>
							</div>

							{/* Reihe 1: Favoriten */}
							{favorites.length > 0 ? (
								<div>
									<h3 style={{fontSize: ri.scale(20) + 'px', fontWeight: 'bold', color: '#00f5e4', marginBottom: ri.scale(12) + 'px'}}>⭐ Deine Favoriten</h3>
									<div style={{display: 'flex', gap: ri.scale(16) + 'px', overflowX: 'auto', paddingBottom: ri.scale(8) + 'px'}}>
										{favorites.slice(0, 6).map(v => (
											<div key={v.FilePath} style={{width: ri.scale(280) + 'px', flexShrink: 0}}>
												<ImageItem
													src={thumbnailUrl(v.thumb)}
													label={v.Size_MB ? `${v.Size_MB.toFixed(1)} MB` : ''}
													onClick={() => onSelectVideo(v)}
													wideImage
												>
													{v._fileName}
												</ImageItem>
											</div>
										))}
									</div>
								</div>
							) : (
								<div>
									<h3 style={{fontSize: ri.scale(20) + 'px', fontWeight: 'bold', color: '#00f5e4', marginBottom: ri.scale(12) + 'px'}}>⭐ Deine Favoriten</h3>
									<p style={{color: 'gray', fontSize: ri.scale(14) + 'px', fontStyle: 'italic', paddingLeft: ri.scale(8) + 'px'}}>Noch keine Favoriten hinzugefügt. Markiere Videos in der Web-App als Favorit, um sie hier zu sehen!</p>
								</div>
							)}

							{/* Reihe 2: Empfehlungen */}
							{recommendations.length > 0 && (
								<div>
									<h3 style={{fontSize: ri.scale(20) + 'px', fontWeight: 'bold', color: '#f4b342', marginBottom: ri.scale(12) + 'px'}}>🎲 Zufällige Entdeckungen</h3>
									<div style={{display: 'flex', gap: ri.scale(16) + 'px', overflowX: 'auto', paddingBottom: ri.scale(8) + 'px'}}>
										{recommendations.map(v => (
											<div key={v.FilePath} style={{width: ri.scale(280) + 'px', flexShrink: 0}}>
												<ImageItem
													src={thumbnailUrl(v.thumb)}
													label={v.Size_MB ? `${v.Size_MB.toFixed(1)} MB` : ''}
													onClick={() => onSelectVideo(v)}
													wideImage
												>
													{v._fileName}
												</ImageItem>
											</div>
										))}
									</div>
								</div>
							)}

							{/* Reihe 3: Letzte Importe */}
							{recent.length > 0 && (
								<div>
									<h3 style={{fontSize: ri.scale(20) + 'px', fontWeight: 'bold', color: '#8b5cf6', marginBottom: ri.scale(12) + 'px'}}>🕐 Letzte Importe</h3>
									<div style={{display: 'flex', gap: ri.scale(16) + 'px', overflowX: 'auto', paddingBottom: ri.scale(8) + 'px'}}>
										{recent.slice(0, 6).map(v => (
											<div key={v.FilePath} style={{width: ri.scale(280) + 'px', flexShrink: 0}}>
												<ImageItem
													src={thumbnailUrl(v.thumb)}
													label={v.Size_MB ? `${v.Size_MB.toFixed(1)} MB` : ''}
													onClick={() => onSelectVideo(v)}
													wideImage
												>
													{v._fileName}
												</ImageItem>
											</div>
										))}
									</div>
								</div>
							)}
						</div>
					</Tab>
					<Tab title="Alle Videos" icon="movies">
						<VirtualGridList
							dataSize={videos.length}
							itemRenderer={makeRenderer(videos)}
							itemSize={{
								minWidth: ri.scale(600),
								minHeight: ri.scale(450)
							}}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Favoriten" icon="star">
						<VirtualGridList
							dataSize={favorites.length}
							itemRenderer={makeRenderer(favorites)}
							itemSize={{
								minWidth: ri.scale(600),
								minHeight: ri.scale(450)
							}}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Letzte Importe" icon="history">
						<VirtualGridList
							dataSize={recent.length}
							itemRenderer={makeRenderer(recent)}
							itemSize={{
								minWidth: ri.scale(600),
								minHeight: ri.scale(450)
							}}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Bilder" icon="picture">
						<VirtualGridList
							dataSize={images.length}
							itemRenderer={makeRenderer(images)}
							itemSize={{
								minWidth: ri.scale(500),
								minHeight: ri.scale(500)
							}}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Collections" icon="folder">
						<div style={{display: 'flex', height: '100%', width: '100%', gap: '24px', padding: '16px', overflow: 'hidden'}}>
							{/* Linke Spalte: Ordner/Collections */}
							<div style={{width: '480px', flexShrink: 0, overflowY: 'auto', borderRight: '1px solid rgba(255,255,255,0.1)', paddingRight: '16px', display: 'flex', flexDirection: 'column', gap: '16px'}}>
								{Object.keys(collectionsByCategory).length === 0 ? (
									<div style={{color: 'gray', fontStyle: 'italic', padding: ri.scale(16) + 'px'}}>Keine Collections vorhanden</div>
								) : (
									Object.keys(collectionsByCategory).sort().map(category => {
										const cols = collectionsByCategory[category];
										return (
											<div key={category} style={{display: 'flex', flexDirection: 'column', gap: ri.scale(8) + 'px'}}>
												<div style={{fontSize: ri.scale(14) + 'px', fontWeight: 'bold', color: '#ff0090', textTransform: 'uppercase', paddingLeft: ri.scale(8) + 'px'}}>
													📁 {category}
												</div>
												{cols.map(col => (
													<Button
														key={col.id}
														size="small"
														selected={selectedCollectionId === col.id}
														onClick={() => setSelectedCollectionId(col.id)}
														style={{justifyContent: 'flex-start', textAlign: 'left', width: '100%'}}
													>
														<span style={{color: col.color || '#00f5e4', marginRight: ri.scale(8) + 'px'}}>●</span>
														{col.name}
													</Button>
												))}
											</div>
										);
									})
								)}
							</div>

							{/* Rechte Spalte: Video-Grid */}
							<div style={{flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0, overflow: 'hidden'}}>
								{selectedCollection ? (
									collectionVideos.length === 0 ? (
										<div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'gray'}}>
											Keine Medien in dieser Collection gefunden.
										</div>
									) : (
										<VirtualGridList
											dataSize={collectionVideos.length}
											itemRenderer={makeRenderer(collectionVideos)}
											itemSize={{
												minWidth: ri.scale(600),
												minHeight: ri.scale(450)
											}}
											direction="vertical"
										/>
									)
								) : (
									<div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'gray'}}>
										Bitte wähle eine Collection aus der linken Liste.
									</div>
								)}
							</div>
						</div>
					</Tab>
					<Tab title="Archiv" icon="files">
						<VirtualGridList
							dataSize={vault.length}
							itemRenderer={makeRenderer(vault)}
							itemSize={{
								minWidth: ri.scale(600),
								minHeight: ri.scale(450)
							}}
							direction="vertical"
						/>
					</Tab>
				</TabLayout>
			)}
		</Panel>
	);
};

MainPanel.propTypes = {
	onSelectVideo: PropTypes.func.isRequired,
	onAuthFailed: PropTypes.func
};

export default MainPanel;
