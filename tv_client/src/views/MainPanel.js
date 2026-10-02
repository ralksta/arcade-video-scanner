import React, {useState, useEffect, useCallback, useMemo} from 'react';
import {serverUrl, thumbnailUrl} from '../serverConfig';
import {getItem, removeItem} from '../safeStorage';
import PropTypes from 'prop-types';
import {Panel, Header} from '@enact/limestone/Panels';
import TabLayout, {Tab} from '@enact/limestone/TabLayout';
import {VirtualGridList} from '@enact/limestone/VirtualList';
import Button from '@enact/limestone/Button';
import {InputField} from '@enact/limestone/Input';
import Dropdown from '@enact/limestone/Dropdown';
import ri from '@enact/ui/resolution';

import MediaCard from '../components/MediaCard';
import MediaRow from '../components/MediaRow';
import HeroBanner from '../components/HeroBanner';
import DetailView from '../components/DetailView';
import homeCss from '../components/Home.module.less';
import displayName from '../displayName';
import {listProgress, getProgress} from '../watchProgress';
import {matchesCollectionCriteria, videoResolution} from '../collectionMatch';

// Rasterzelle in 4K-Pixeln: 680 breit, 16:9-Bild (382) plus 36 Rand für den
// Fokus. Ergibt auf Full HD fünf Spalten à 340 px.
//
// Eine Funktion, kein Modul-Konstante: Beim Import hat Limestone die
// Bildschirmauflösung noch nicht ermittelt, `ri.scale` rechnet dann mit
// Faktor 1 — auf dem Fernseher standen zwei riesige Spalten statt fünf.
const gridItem = () => ({minWidth: ri.scale(680), minHeight: ri.scale(418)});

// Sortierung als Dropdown statt fünf Emoji-Knöpfen in zwei Zeilen.
const SORT_OPTIONS = [
	{key: 'newest', label: 'Neueste'},
	{key: 'name_az', label: 'Name A–Z'},
	{key: 'name_za', label: 'Name Z–A'},
	{key: 'size_desc', label: 'Größte'},
	{key: 'size_asc', label: 'Kleinste'},
	{key: 'duration_desc', label: 'Längste'}
];

// Filter der Raster-Reiter. Index 0 heißt jeweils „kein Filter“ und trägt
// den Namen des Filters — kurz, damit die schmalen Dropdowns nicht abschneiden.
const RESOLUTION_FILTERS = [
	{label: 'Auflösung'},
	{label: '4K', value: '4k'},
	{label: '1080p', value: '1080p'},
	{label: '720p', value: '720p'},
	{label: 'SD', value: 'sd'}
];
const DURATION_FILTERS = [
	{label: 'Länge'},
	{label: '< 10 Min', max: 600},
	{label: '10–30 Min', min: 600, max: 1800},
	{label: '> 30 Min', min: 1800}
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
		case 'duration_desc':
			return sorted.sort((a, b) => (b.Duration_Sec || 0) - (a.Duration_Sec || 0));
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

const MainPanel = ({onSelectVideo, onAuthFailed, progressVersion, ...props}) => {
	const [allVideos, setAllVideos] = useState([]);
	// Eintrag in der Detailansicht (null = keine offen)
	const [detailPath, setDetailPath] = useState(null);
	const [favoriteBusy, setFavoriteBusy] = useState(false);
	const [smartCollections, setSmartCollections] = useState([]);
	const [recommendations, setRecommendations] = useState([]);
	const [selectedCollectionId, setSelectedCollectionId] = useState(null);
	const [tabIndex, setTabIndex] = useState(0);
	const [loading, setLoading] = useState(true);
	// Ohne die Nutzerdaten fehlen Favoriten, Tags und Sammlungen; die
	// Mediathek wird trotzdem gezeigt (bis Phase 1 verhinderte das der Vault).
	const [userDataFailed, setUserDataFailed] = useState(false);
	const [sortKey, setSortKey] = useState('newest');
	const [resolutionIdx, setResolutionIdx] = useState(0);
	const [durationIdx, setDurationIdx] = useState(0);
	const [tagIdx, setTagIdx] = useState(0);
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
	// Tags, die in der Bibliothek tatsächlich vorkommen — nur die lohnen sich
	// als Filter. Index 0 im Dropdown ist „Alle Tags“.
	const tagOptions = useMemo(() => {
		const seen = new Set();
		allVideos.forEach(v => (v.tags || []).forEach(t => seen.add(t)));
		return [...seen].sort((a, b) => a.localeCompare(b, 'de'));
	}, [allVideos]);

	const filtersActive = Boolean(filterText.trim()) || resolutionIdx > 0 || durationIdx > 0 || tagIdx > 0;

	const resetFilters = useCallback(() => {
		setFilterText('');
		setResolutionIdx(0);
		setDurationIdx(0);
		setTagIdx(0);
	}, []);

	const filterAndSort = useCallback((list) => {
		let result = list;
		if (filterText.trim()) {
			const q = filterText.trim().toLowerCase();
			result = result.filter(v => (v._fileName || '').toLowerCase().includes(q));
		}
		const res = RESOLUTION_FILTERS[resolutionIdx].value;
		if (res) result = result.filter(v => videoResolution(v) === res);
		const dur = DURATION_FILTERS[durationIdx];
		if (dur.min !== undefined) result = result.filter(v => (v.Duration_Sec || 0) >= dur.min);
		if (dur.max !== undefined) result = result.filter(v => (v.Duration_Sec || 0) < dur.max);
		const tag = tagIdx > 0 ? tagOptions[tagIdx - 1] : null;
		if (tag) result = result.filter(v => (v.tags || []).includes(tag));
		return sortVideos(result, sortKey);
	}, [filterText, sortKey, resolutionIdx, durationIdx, tagIdx, tagOptions]);

	// Home ist kuratiert und zeigt keine Filterleiste — also auch keine
	// Filter. Sonst leerte ein in „Alle Videos“ gesetzter Filter unsichtbar
	// die Reihen auf Home.
	const homeFavorites = useMemo(() =>
		sortVideos(allVideos.filter(v => v.favorite), 'newest').slice(0, 30),
	[allVideos]);
	// Weiterschauen: angefangene Videos, zuletzt gesehenes zuerst. Hängt an
	// progressVersion, das App nach jedem Schließen des Players hochzählt.
	const continueWatching = useMemo(() => {
		const byPath = new Map(allVideos.map(v => [v.FilePath, v]));
		return listProgress()
			.map(p => ({video: byPath.get(p.path), progress: p.d ? p.t / p.d : 0}))
			.filter(x => x.video)
			.slice(0, 20);
	}, [allVideos, progressVersion]); // eslint-disable-line react-hooks/exhaustive-deps

	const continueProgress = useMemo(
		() => new Map(continueWatching.map(x => [x.video.FilePath, x.progress])),
		[continueWatching]
	);

	const homeRecent = useMemo(() =>
		sortVideos(allVideos, 'newest').slice(0, 30),
	[allVideos]);

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

	// Übersicht: jede Collection als Reihe, gruppiert nach Kategorie. Die
	// Treffer werden hier einmal berechnet, nicht pro Render jeder Reihe.
	const collectionRows = useMemo(() => {
		return Object.keys(collectionsByCategory).sort().map(category => ({
			category,
			rows: collectionsByCategory[category].map(col => ({
				col,
				items: filterAndSort(allVideos.filter(v => matchesCollectionCriteria(v, col.criteria)))
			}))
		}));
	}, [collectionsByCategory, allVideos, filterAndSort]);

	// Zurück-Taste der Fernbedienung (461, ESC 27): aus einer geöffneten
	// Collection zurück zur Übersicht, statt die App zu verlassen. Capture,
	// damit Panels die Taste nicht zuerst als „App beenden“ deutet.
	useEffect(() => {
		if (!selectedCollectionId) return undefined;
		const onBack = (ev) => {
			if (ev.keyCode !== 461 && ev.keyCode !== 27) return;
			ev.preventDefault();
			ev.stopImmediatePropagation();
			setSelectedCollectionId(null);
		};
		document.addEventListener('keydown', onBack, true);
		return () => document.removeEventListener('keydown', onBack, true);
	}, [selectedCollectionId]);

	// Item Renderer Factory
	// Titel, Vorschaubild und Metazeile einer Kachel — eine Stelle für Home
	// und die Raster-Reiter.
	const cardProps = useCallback((v) => ({
		src: thumbnailUrl(v.thumb),
		title: displayName(v),
		meta: [formatDuration(v.Duration_Sec), resolutionLabel(v), formatSize(v.Size_MB)]
			.filter(Boolean).join('  ·  '),
		favorite: Boolean(v.favorite),
		badge: {'4k': '4K', '1080p': 'HD'}[videoResolution(v)]
	}), []);


	// eslint-disable-next-line no-unused-vars
	const makeRenderer = useCallback((list) => ({index, ...itemProps}) => {
		const v = list[index];
		if (!v) return null;
		return (
			<MediaCard
				{...itemProps}
				{...cardProps(v)}
				onSelect={() => setDetailPath(v.FilePath)}
			/>
		);
	}, [cardProps]);

	// Raster eines Reiters — oder ein Hinweis, warum es leer ist. Vorher
	// blieb die Fläche einfach schwarz (der Bilder-Reiter zeigte nichts, ohne
	// zu sagen, dass es keine Bilder gibt).
	const renderGrid = (list, emptyText) => {
		if (list.length > 0) {
			return (
				<VirtualGridList
					dataSize={list.length}
					itemRenderer={makeRenderer(list)}
					itemSize={gridItem()}
					direction="vertical"
				/>
			);
		}
		return (
			<div className={homeCss.emptyState}>
				<div>{filtersActive ? 'Keine Treffer für diese Filter.' : emptyText}</div>
				{filtersActive ? (
					<Button size="small" icon="closex" onClick={resetFilters}>Filter zurücksetzen</Button>
				) : null}
			</div>
		);
	};

	// Detailansicht: per Pfad, damit sie nach dem Umschalten des Favoriten
	// den aktualisierten Eintrag aus allVideos zeigt.
	const openDetail = useCallback((v) => setDetailPath(v.FilePath), []);
	const closeDetail = useCallback(() => setDetailPath(null), []);
	const detailVideo = useMemo(
		() => (detailPath ? allVideos.find(v => v.FilePath === detailPath) : null),
		[detailPath, allVideos]
	);

	const playDetail = useCallback(() => {
		if (!detailVideo) return;
		setDetailPath(null);
		onSelectVideo(detailVideo);
	}, [detailVideo, onSelectVideo]);

	const playDetailFromStart = useCallback(() => {
		if (!detailVideo) return;
		setDetailPath(null);
		onSelectVideo(detailVideo, {fromStart: true});
	}, [detailVideo, onSelectVideo]);

	// „Fortsetzen bei 12:30“, wenn es eine gemerkte Position gibt
	const detailResume = useMemo(() => {
		if (!detailVideo) return '';
		const t = getProgress(detailVideo.FilePath);
		if (!t) return '';
		const m = Math.floor(t / 60);
		const sec = String(t % 60).padStart(2, '0');
		return `Fortsetzen bei ${m}:${sec}`;
	}, [detailVideo, progressVersion]); // eslint-disable-line react-hooks/exhaustive-deps

	// Favorit umschalten — dieselbe Route wie die Web-App. Erst nach Erfolg
	// lokal übernehmen, damit Stern und Server nicht auseinanderlaufen.
	const toggleFavorite = useCallback(async () => {
		if (!detailVideo || favoriteBusy) return;
		const next = !detailVideo.favorite;
		const path = detailVideo.FilePath;
		setFavoriteBusy(true);
		try {
			const token = getItem('arcade_session_token');
			const res = await fetch(
				serverUrl(`/favorite?path=${encodeURIComponent(path)}&state=${next}`),
				{headers: token ? {Authorization: `Bearer ${token}`} : {}}
			);
			if (res.ok) {
				setAllVideos(prev => prev.map(v => (v.FilePath === path ? {...v, favorite: next} : v)));
			}
		} catch (e) {
			// Netzfehler: Zustand bleibt, der Knopf zeigt weiter den alten Stand.
		} finally {
			setFavoriteBusy(false);
		}
	}, [detailVideo, favoriteBusy]);

	const handleTabSelect = useCallback((ev) => {
		setTabIndex(ev.index);
	}, []);

	// Zählt, was der aktuelle Reiter zeigt — vorher immer „Alle Videos“,
	// auch unter Favoriten.
	const tabList = [null, videos, favorites, recent, images][tabIndex];
	const baseSubtitle = loading
		? 'Lade Mediathek...'
		: tabList && filtersActive
			? `${tabList.length} Treffer`
			: tabList
				? `${tabList.length} Einträge`
				: `${allVideos.length} Einträge`;
	const subtitle = userDataFailed
		? `${baseSubtitle} · Nutzerdaten fehlen (Favoriten, Tags)`
		: baseSubtitle;

	return (
		<Panel {...props}>
			<Header
				type="mini"
				title="Arcade Scanner"
				subtitle={subtitle}
			/>

			{/* Werkzeugleiste der Raster-Reiter: eine Zeile, Limestone-Icons statt
			    Emoji. Home ist kuratiert und hat keine. */}
			{tabIndex !== 0 && (
				<div className={homeCss.toolbar}>
					<InputField
						className={homeCss.search}
						iconBefore="search"
						placeholder="Suchen"
						value={filterText}
						onChange={handleFilterChange}
						size="small"
					/>
					<Dropdown
						size="small"
						width="small"
						selected={SORT_OPTIONS.findIndex(o => o.key === sortKey)}
						onSelect={({selected}) => setSortKey(SORT_OPTIONS[selected].key)}
					>
						{SORT_OPTIONS.map(o => o.label)}
					</Dropdown>
					<Dropdown
						size="small"
						width="small"
						selected={resolutionIdx}
						onSelect={({selected}) => setResolutionIdx(selected)}
					>
						{RESOLUTION_FILTERS.map(o => o.label)}
					</Dropdown>
					<Dropdown
						size="small"
						width="small"
						selected={durationIdx}
						onSelect={({selected}) => setDurationIdx(selected)}
					>
						{DURATION_FILTERS.map(o => o.label)}
					</Dropdown>
					{tagOptions.length > 0 ? (
						<Dropdown
							size="small"
							width="small"
							selected={tagIdx}
							onSelect={({selected}) => setTagIdx(selected)}
						>
							{['Tags', ...tagOptions]}
						</Dropdown>
					) : null}
					{filtersActive ? (
						<Button size="small" icon="closex" onClick={resetFilters}>Zurücksetzen</Button>
					) : null}
				</div>
			)}


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
								title="Weiterschauen"
								items={continueWatching.map(x => x.video)}
								cardProps={v => ({...cardProps(v), progress: continueProgress.get(v.FilePath)})}
								onSelect={openDetail}
							/>
							<MediaRow
								title="Deine Favoriten"
								items={homeFavorites}
								cardProps={cardProps}
								onSelect={openDetail}
								emptyText="Noch keine Favoriten — markiere Videos in der Web-App mit dem Stern."
							/>
							<MediaRow
								title="Zufällige Entdeckungen"
								items={recommendations.slice(1)}
								cardProps={cardProps}
								onSelect={openDetail}
							/>
							<MediaRow
								title="Zuletzt hinzugefügt"
								items={homeRecent}
								cardProps={cardProps}
								onSelect={openDetail}
							/>
						</div>
					</Tab>
					<Tab title="Alle Videos" icon="movies">
						{renderGrid(videos, 'Keine Videos in der Bibliothek.')}
					</Tab>
					<Tab title="Favoriten" icon="star">
						{renderGrid(favorites, 'Noch keine Favoriten. Markiere Videos mit dem Stern — in der Detailansicht oder in der Web-App.')}
					</Tab>
					<Tab title="Zuletzt hinzugefügt" icon="history">
						{renderGrid(recent, 'Noch nichts hinzugefügt.')}
					</Tab>
					<Tab title="Bilder" icon="picture">
						{renderGrid(images, 'Keine Bilder in der Bibliothek. In der Web-App unter Einstellungen „Include Photos“ aktivieren und neu scannen.')}
					</Tab>
					<Tab title="Collections" icon="folder">
						{selectedCollection ? (
							<div className={homeCss.detail}>
								<div className={homeCss.detailBar}>
									<Button icon="arrowlargeleft" onClick={() => setSelectedCollectionId(null)}>
										Collections
									</Button>
									<span className={homeCss.dot} style={{background: selectedCollection.color || '#00f5e4'}} />
									<span className={homeCss.detailTitle}>{selectedCollection.name}</span>
									<span className={homeCss.rowCount}>{collectionVideos.length}</span>
								</div>
								{collectionVideos.length === 0 ? (
									<div className={homeCss.centered}>Keine Medien in dieser Collection.</div>
								) : (
									<VirtualGridList
										className={homeCss.detailGrid}
										dataSize={collectionVideos.length}
										itemRenderer={makeRenderer(collectionVideos)}
										itemSize={gridItem()}
										direction="vertical"
									/>
								)}
							</div>
						) : collectionRows.length === 0 ? (
							<div className={homeCss.centered}>
								Noch keine Collections — in der Web-App unter „Smart Collections“ anlegen.
							</div>
						) : (
							<div className={homeCss.home}>
								{collectionRows.map(({category, rows}) => (
									<div key={category}>
										<div className={homeCss.category}>{category}</div>
										{rows.map(({col, items}) => (
											<MediaRow
												key={col.id}
												title={col.name}
												dotColor={col.color || '#00f5e4'}
												items={items}
												limit={20}
												onMore={() => setSelectedCollectionId(col.id)}
												cardProps={cardProps}
												onSelect={openDetail}
												emptyText="Keine Medien in dieser Collection."
											/>
										))}
									</div>
								))}
							</div>
						)}
					</Tab>
				</TabLayout>
			)}
			{detailVideo ? (
				<DetailView
					{...cardProps(detailVideo)}
					tags={detailVideo.tags || []}
					busy={favoriteBusy}
					resumeLabel={detailResume}
					onPlay={playDetail}
					onPlayFromStart={playDetailFromStart}
					onToggleFavorite={toggleFavorite}
					onClose={closeDetail}
				/>
			) : null}
		</Panel>
	);
};

MainPanel.propTypes = {
	onSelectVideo: PropTypes.func.isRequired,
	onAuthFailed: PropTypes.func,
	progressVersion: PropTypes.number
};

export default MainPanel;
