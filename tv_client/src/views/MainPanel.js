import React, {useState, useEffect, useCallback, useMemo} from 'react';
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
			return sorted.reverse();
	}
};

const MainPanel = ({onSelectVideo, onAuthFailed, ...props}) => {
	const [allVideos, setAllVideos] = useState([]);
	const [loading, setLoading] = useState(true);
	const [sortKey, setSortKey] = useState('newest');
	const [filterText, setFilterText] = useState('');

	// Daten laden
	useEffect(() => {
		const token = localStorage.getItem('arcade_session_token');
		const headers = {
			'Content-Type': 'application/json'
		};
		if (token) {
			headers['Authorization'] = `Bearer ${token}`;
		}

		fetch('http://192.168.2.183:8000/api/videos', {
			headers: headers
		})
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
				// Dateinamen aufbereiten
				data.forEach(v => {
					const path = v.FilePath;
					const lastIdx = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
					v._fileName = path.substring(lastIdx + 1);
				});
				setAllVideos(data);
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

	const recent = useMemo(() =>
		filterAndSort([...allVideos].filter(v => !v.hidden).slice(-48)),
	[allVideos, filterAndSort]);

	const images = useMemo(() =>
		filterAndSort(allVideos.filter(v => v.media_type === 'image' && !v.hidden)),
	[allVideos, filterAndSort]);

	const vault = useMemo(() =>
		filterAndSort(allVideos.filter(v => v.hidden)),
	[allVideos, filterAndSort]);

	// Item Renderer Factory
	const makeRenderer = useCallback((list) => ({index, ...itemProps}) => {
		const v = list[index];
		if (!v) return null;

		const isImage = v.media_type === 'image';
		const labelText = [
			v.Size_MB ? `${v.Size_MB.toFixed(1)} MB` : '',
			v.resolution || ''
		].filter(Boolean).join(' | ');

		return (
			<ImageItem
				{...itemProps}
				src={`http://192.168.2.183:8000/thumbnails/${v.thumb}`}
				label={labelText}
				onClick={() => onSelectVideo(v)}
				wideImage={!isImage}
			>
				{v._fileName}
			</ImageItem>
		);
	}, [onSelectVideo]);

	const subtitle = loading
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

			{!loading && (
				<TabLayout>
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
