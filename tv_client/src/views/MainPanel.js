import React, {useState, useEffect, useCallback, useMemo} from 'react';
import {serverUrl, thumbnailUrl} from '../serverConfig';
import {getItem, removeItem} from '../safeStorage';
import PropTypes from 'prop-types';
import {Panel, Header} from '@enact/limestone/Panels';
import TabLayout, {Tab} from '@enact/limestone/TabLayout';
import {VirtualGridList} from '@enact/limestone/VirtualList';
import Button from '@enact/limestone/Button';
import {InputField} from '@enact/limestone/Input';
import ri from '@enact/ui/resolution';

import MediaCard from '../components/MediaCard';
import MediaRow from '../components/MediaRow';
import HeroBanner from '../components/HeroBanner';
import homeCss from '../components/Home.module.less';
import displayName from '../displayName';

// Rasterzelle in 4K-Pixeln: 680 breit, 16:9-Bild (382) plus 36 Rand für den
// Fokus. Ergibt auf Full HD fünf Spalten à 340 px.
const GRID_ITEM = {minWidth: ri.scale(680), minHeight: ri.scale(418)};

const SORT_OPTIONS = [
	{key: 'newest', label: '🕐 Neueste'},
	{key: 'name_az', label: '🔤 A → Z'},
	{key: 'name_za', label: '🔤 Z → A'},
	{key: 'size_desc', label: '📦 Größte'},
	{key: 'size_asc', label: '📦 Kleinste'}
];

// Datum eines Eintrags, in Sekunden — dieselbe Regel wie entryDate() im
// Browser-Client (arcade_scanner/server/static/utils.js) und wie
// matches_date_filter() in arcade_scanner/core/criteria_eval.py.
//
// `imported_at` ist der Zeitpunkt des ersten Scans, `mtime` der der letzten
// Änderung der Datei. „Neueste" meint das erste: wann das hier in der
// Bibliothek aufgetaucht ist. `mtime` bleibt der Ersatz für Einträge aus der
// Zeit vor dem Feld.
//
// Vorher stand hier nur `v.mtime`. Damit schob jedes Optimieren einen alten
// Film nach oben, weil die Datei dabei neu geschrieben wird.
const entryDate = (v) => (Number(v && v.imported_at) || 0) || (Number(v && v.mtime) || 0);

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
			return sorted.sort((a, b) => entryDate(b) - entryDate(a));
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
	// Ohne die Nutzerdaten fehlen Favoriten, Tags und Sammlungen; die
	// Mediathek wird trotzdem gezeigt (bis Phase 1 verhinderte das der Vault).
	const [userDataFailed, setUserDataFailed] = useState(false);
	const [sortKey, setSortKey] = useState('newest');
	const [filterText, setFilterText] = useState('');

	// Daten und Collections laden
	useEffect(() => {
		const token = getItem('arcade_session_token');
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
					removeItem('arcade_session_token');
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
				// Mapping von Favoriten und Tags aus den User-Daten auf die Videos
				if (userData) {
					const favSet = new Set(userData.favorites || []);
					const tagMap = userData.tags || {};
					videosData.forEach(v => {
						v.favorite = favSet.has(v.FilePath);
						v.tags = tagMap[v.FilePath] || [];
					});
				}

				// `userData` ist null, wenn /api/user/data nicht erreichbar war.
				// Bis Phase 1 blieb das Raster dann leer, weil sonst der Vault
				// sichtbar gewesen wäre. Den gibt es nicht mehr, und der TV kennt
				// keinen abgesicherten Modus — also zeigen, nur ohne Favoriten
				// und Tags, und im Untertitel sagen, warum.
				if (!userData) {
					setUserDataFailed(true);
				}

				setAllVideos(videosData);

				if (userData && userData.smart_collections) {
					setSmartCollections(userData.smart_collections);
				}

				// Zufällige Empfehlungen generieren (nur sichtbare Videos)
				const videoOnly = videosData.filter(v => (v.media_type || 'video') === 'video');
				const shuffled = [...videoOnly].sort(() => 0.5 - Math.random());
				setRecommendations(shuffled.slice(0, 16));

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
		filterAndSort(allVideos.filter(v => (v.media_type || 'video') === 'video')),
	[allVideos, filterAndSort]);

	const favorites = useMemo(() =>
		filterAndSort(allVideos.filter(v => v.favorite)),
	[allVideos, filterAndSort]);

	// „Zuletzt hinzugefügt": ebenfalls nach Datum, nicht nach den letzten 48
	// Zeilen der Datenbank. `slice(-48)` nahm das Ende der Einfügereihenfolge —
	// dieselbe Verwechslung wie beim „newest"-Sortierschlüssel oben.
	const recent = useMemo(() =>
		filterAndSort(
			[...allVideos]
				.sort((a, b) => entryDate(b) - entryDate(a))
				.slice(0, 48)
		),
	[allVideos, filterAndSort]);

	const images = useMemo(() =>
		filterAndSort(allVideos.filter(v => v.media_type === 'image')),
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
	// Titel, Vorschaubild und Metazeile einer Kachel — eine Stelle für Home
	// und die Raster-Reiter.
	const cardProps = useCallback((v) => ({
		src: thumbnailUrl(v.thumb),
		title: displayName(v),
		meta: [formatDuration(v.Duration_Sec), resolutionLabel(v), formatSize(v.Size_MB)]
			.filter(Boolean).join('  ·  ')
	}), []);

	// eslint-disable-next-line no-unused-vars
	const makeRenderer = useCallback((list) => ({index, ...itemProps}) => {
		const v = list[index];
		if (!v) return null;
		return (
			<MediaCard
				{...itemProps}
				{...cardProps(v)}
				onSelect={() => onSelectVideo(v)}
			/>
		);
	}, [onSelectVideo, cardProps]);

	const handleTabSelect = useCallback((ev) => {
		setTabIndex(ev.index);
	}, []);

	const baseSubtitle = loading
		? 'Lade Mediathek...'
		: filterText
			? `${videos.length} Treffer für "${filterText}"`
			: `${videos.length} Videos`;
	const subtitle = userDataFailed
		? `${baseSubtitle} · Nutzerdaten fehlen (Favoriten, Tags)`
		: baseSubtitle;

	return (
		<Panel {...props}>
			<Header
				title="Arcade Scanner TV"
				subtitle={subtitle}
			/>

			{/* Sortier- und Filterleiste — nur in den Raster-Reitern; Home ist
			    eine kuratierte Ansicht und braucht sie nicht. */}
			{tabIndex !== 0 && <div style={{display: 'flex', alignItems: 'center', gap: ri.scale(16) + 'px', padding: `${ri.scale(8)}px ${ri.scale(24)}px`, flexWrap: 'wrap'}}>
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
			</div>}


			{!loading && (
				<TabLayout index={tabIndex} onSelect={handleTabSelect}>
					<Tab title="Home" icon="home">
						<div className={homeCss.home}>
							{recommendations[0] ? (
								<HeroBanner
									video={recommendations[0]}
									eyebrow="Zufällige Entdeckung"
									onPlay={() => onSelectVideo(recommendations[0])}
									{...cardProps(recommendations[0])}
								/>
							) : null}
							<MediaRow
								title="Deine Favoriten"
								items={favorites.slice(0, 30)}
								cardProps={cardProps}
								onSelect={onSelectVideo}
								emptyText="Noch keine Favoriten — markiere Videos in der Web-App mit dem Stern."
							/>
							<MediaRow
								title="Zufällige Entdeckungen"
								items={recommendations.slice(1)}
								cardProps={cardProps}
								onSelect={onSelectVideo}
							/>
							<MediaRow
								title="Zuletzt hinzugefügt"
								items={recent.slice(0, 30)}
								cardProps={cardProps}
								onSelect={onSelectVideo}
							/>
						</div>
					</Tab>
					<Tab title="Alle Videos" icon="movies">
						<VirtualGridList
							dataSize={videos.length}
							itemRenderer={makeRenderer(videos)}
							itemSize={GRID_ITEM}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Favoriten" icon="star">
						<VirtualGridList
							dataSize={favorites.length}
							itemRenderer={makeRenderer(favorites)}
							itemSize={GRID_ITEM}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Letzte Importe" icon="history">
						<VirtualGridList
							dataSize={recent.length}
							itemRenderer={makeRenderer(recent)}
							itemSize={GRID_ITEM}
							direction="vertical"
						/>
					</Tab>
					<Tab title="Bilder" icon="picture">
						<VirtualGridList
							dataSize={images.length}
							itemRenderer={makeRenderer(images)}
							itemSize={GRID_ITEM}
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
											itemSize={GRID_ITEM}
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
